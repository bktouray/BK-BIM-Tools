# -*- coding: utf-8 -*-
__title__ = u"PCC\nBlinding"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Generates a PCC blinding pad under every isolated footing.
Scan a level automatically or pick footings manually, set the blinding
depth and side offset, choose a footing family and material, and run.
"""

from pyrevit import revit, DB, forms, script
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType

# Dev reload: always pick up the latest bkbim.automation lib code on each click.
import sys as _sys
for _m in [_n for _n in list(_sys.modules) if _n.startswith("bkbim.automation")]:
    del _sys.modules[_m]

from bkbim.automation.common import to_feet
from bkbim.automation.failures import swallow_warnings
from bkbim.automation.familyutils import pick_family_symbol
from bkbim.automation.blinding import (
    group_footings_by_blinding_size, get_or_create_sized_blinding_type, place_blinding,
)
from bkbim.ui.views.element_scope_options import show_element_scope_options, MODE_AUTO
from bkbim.ui.views.pcc_blinding_options import show_pcc_blinding_options

logger = script.get_logger()
output = script.get_output()
doc = revit.doc
uidoc = revit.uidoc

_SNAP = 5.0  # mm rounding for size grouping

AUTO_DETECT = u"Auto-detect from a level"
PICK_MANUALLY = u"Manually select footings"


def _name(el):
    try:
        return el.Name
    except Exception:
        return DB.Element.Name.__get__(el)


class _FootingOnlyFilter(ISelectionFilter):
    def AllowElement(self, elem):
        return (isinstance(elem, DB.FamilyInstance)
                and elem.Category is not None
                and elem.Category.Id == DB.ElementId(DB.BuiltInCategory.OST_StructuralFoundation))

    def AllowReference(self, reference, point):
        return False


def _collect_footings_on_level(level):
    elems = (DB.FilteredElementCollector(doc)
             .OfCategory(DB.BuiltInCategory.OST_StructuralFoundation)
             .WhereElementIsNotElementType().ToElements())
    return [e for e in elems if isinstance(e, DB.FamilyInstance) and e.LevelId == level.Id]


def _pick_footings_manually():
    try:
        picked_refs = uidoc.Selection.PickObjects(
            ObjectType.Element, _FootingOnlyFilter(),
            "{0}: click footings, then Finish".format(__title__.replace("\n", " ")))
    except Exception:
        return []
    return [doc.GetElement(ref.ElementId) for ref in picked_refs]


def main():
    if doc is None:
        forms.alert("No active Revit document.", title=__title__)
        return

    levels = sorted(
        DB.FilteredElementCollector(doc).OfClass(DB.Level).ToElements(),
        key=lambda lv: lv.Elevation)
    if not levels:
        forms.alert("No levels in the model.", title=__title__)
        return

    scope = show_element_scope_options(
        __title__.replace("\n", " "),
        u"Choose which footings to add blinding under.",
        AUTO_DETECT, PICK_MANUALLY,
        u"Click each footing in the view (Ctrl+click or drag a box for more "
        u"than one), then click Finish on the ribbon/status bar. Press "
        u"Escape instead to cancel.",
        levels, _name)
    if not scope:
        return

    if scope.mode == MODE_AUTO:
        footings = _collect_footings_on_level(scope.level)
        if not footings:
            forms.alert("No isolated footings found on level '{0}'.".format(_name(scope.level)), title=__title__)
            return
    else:
        footings = _pick_footings_manually()
        if not footings:
            return

    materials = sorted(
        DB.FilteredElementCollector(doc).OfClass(DB.Material).ToElements(), key=_name)

    subtitle = u"{0} footing(s) detected.".format(len(footings))

    options = show_pcc_blinding_options(
        subtitle, materials, _name,
        lambda: pick_family_symbol(
            doc, [DB.BuiltInCategory.OST_StructuralFoundation],
            "Base family for blinding pads (used for auto-sizing)"))
    if not options:
        return

    depth_ft = to_feet(options.depth_mm, "mm")
    offset_ft = to_feet(options.offset_mm, "mm")

    # SCAN.
    groups = group_footings_by_blinding_size(footings, offset_ft, snap=_SNAP)
    matched_count = sum(len(fs) for _key, fs in groups)
    if matched_count == 0:
        forms.alert("None of the selected footings have a usable footprint.", title=__title__)
        return

    skipped_scan = len(footings) - matched_count
    output.print_md(u"**Detected blinding pad sizes:**")
    for (l, w), fs in groups:
        output.print_md(u"- {0} x {1} mm pad -> {2} footing(s)".format(l, w, len(fs)))
    if skipped_scan:
        output.print_md(u"{0} footing(s) had a degenerate footprint and were skipped.".format(skipped_scan))

    # Base blinding pad family already chosen in the options window.
    base_symbol = options.base_symbol

    # Build symbol -> footings mapping (one type per blinding footprint size,
    # all sharing the single chosen depth).
    footings_by_type = []
    t = DB.Transaction(doc, "Generate PCC Blinding")
    t.Start()
    swallow_warnings(t)
    try:
        cache = {}
        for (l_mm, w_mm), fs in groups:
            sym = get_or_create_sized_blinding_type(
                doc, base_symbol, l_mm / 304.8, w_mm / 304.8, depth_ft, _SNAP, cache)
            footings_by_type.append((sym, fs))

        res = place_blinding(doc, footings_by_type, offset_ft, material_id=options.material_id)
        if res.placed == 0:
            t.RollBack()
        else:
            t.Commit()
    except Exception as e:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        logger.error("PCC Blinding failed: {0}".format(str(e)))
        forms.alert("PCC Blinding failed:\n{0}".format(str(e)), title=__title__)
        return

    if res.placed == 0:
        msg = "No blinding pads were placed."
        if res.errors:
            msg += "\n\n" + "\n".join(res.errors[:5])
        forms.alert(msg, title=__title__)
        return

    extra = "\n{0} skipped (degenerate footprint or missing level).".format(res.skipped) if res.skipped else ""
    forms.alert(
        "PCC Blinding Complete.\n\n"
        "Successfully placed {0} blinding pad(s).{1}".format(res.placed, extra),
        title=__title__)
    if res.errors:
        output.print_md("**Notes:** " + "; ".join(res.errors[:5]))


if __name__ == "__main__":
    main()
