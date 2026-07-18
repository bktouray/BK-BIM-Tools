# -*- coding: utf-8 -*-
__title__ = u"Floors to\nFootings"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Converts Floor elements into isolated structural foundations
(e.g. pad footings that came in as floors from another program). Scan a
level automatically or pick floors manually, choose a footing family and
material, and run.
"""

from pyrevit import revit, DB, script
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType

# Dev reload: always pick up the latest bkbim.automation lib code on each click.
import sys as _sys
for _m in [_n for _n in list(_sys.modules) if _n.startswith("bkbim.automation")]:
    del _sys.modules[_m]

from bkbim.automation.failures import swallow_warnings
from bkbim.automation.familyutils import pick_family_symbol
from bkbim.automation.footings import (
    group_floors_by_size, get_or_create_sized_footing_type, place_footings,
)
from bkbim.ui.views.element_scope_options import show_element_scope_options, MODE_AUTO
from bkbim.ui.views.floors_to_footings_options import show_floors_to_footings_options
from bkbim.ui.views.result_dialog import show_result

logger = script.get_logger()
output = script.get_output()
doc = revit.doc
uidoc = revit.uidoc

_SNAP = 5.0  # mm rounding for size grouping

AUTO_DETECT = u"Auto-detect from a level"
PICK_MANUALLY = u"Manually select floors"


def _name(el):
    try:
        return el.Name
    except Exception:
        return DB.Element.Name.__get__(el)


class _FloorOnlyFilter(ISelectionFilter):
    def AllowElement(self, elem):
        return isinstance(elem, DB.Floor)

    def AllowReference(self, reference, point):
        return False


def _collect_floors_on_level(level):
    floors = (DB.FilteredElementCollector(doc)
              .OfCategory(DB.BuiltInCategory.OST_Floors)
              .WhereElementIsNotElementType().ToElements())
    return [f for f in floors if isinstance(f, DB.Floor) and f.LevelId == level.Id]


def _pick_floors_manually():
    try:
        picked_refs = uidoc.Selection.PickObjects(
            ObjectType.Element, _FloorOnlyFilter(),
            "{0}: click floors, then Finish".format(__title__.replace("\n", " ")))
    except Exception:
        return []
    return [doc.GetElement(ref.ElementId) for ref in picked_refs]


def main():
    if doc is None:
        show_result(__title__, "No active Revit document.")
        return

    levels = sorted(
        DB.FilteredElementCollector(doc).OfClass(DB.Level).ToElements(),
        key=lambda lv: lv.Elevation)
    if not levels:
        show_result(__title__, "No levels in the model.")
        return

    scope = show_element_scope_options(
        __title__.replace("\n", " "),
        u"Choose which floors to convert into isolated footings.",
        AUTO_DETECT, PICK_MANUALLY,
        u"Click each floor in the view (Ctrl+click or drag a box for more "
        u"than one), then click Finish on the ribbon/status bar. Press "
        u"Escape instead to cancel.",
        levels, _name)
    if not scope:
        return

    if scope.mode == MODE_AUTO:
        floors = _collect_floors_on_level(scope.level)
        if not floors:
            show_result(
                __title__,
                "No floors found on level '{0}'.".format(_name(scope.level)))
            return
    else:
        floors = _pick_floors_manually()
        if not floors:
            return

    # SCAN.
    groups = group_floors_by_size(floors, snap=_SNAP)
    matched_count = sum(len(fs) for _key, fs in groups)
    if matched_count == 0:
        show_result(__title__, "None of the selected floors have a usable footprint.")
        return

    skipped_scan = len(floors) - matched_count
    subtitle = u"{0} floor(s) detected in {1} size(s).".format(matched_count, len(groups))
    if skipped_scan:
        subtitle += u" {0} had a degenerate footprint and will be skipped.".format(skipped_scan)

    materials = sorted(
        DB.FilteredElementCollector(doc).OfClass(DB.Material).ToElements(), key=_name)

    options = show_floors_to_footings_options(
        subtitle, materials, _name,
        lambda: pick_family_symbol(
            doc, [DB.BuiltInCategory.OST_StructuralFoundation],
            "Base isolated footing family (used for auto-sizing)"))
    if not options:
        return

    output.print_md(u"**Detected sizes:**")
    for (l, w, t), fs in groups:
        output.print_md(u"- {0} x {1} x {2} mm -> {3} floor(s)".format(l, w, t, len(fs)))

    # Build symbol -> floors mapping.
    floors_by_type = []
    t = DB.Transaction(doc, "Convert Floors to Footings")
    t.Start()
    swallow_warnings(t)
    try:
        if options.auto_size:
            cache = {}
            for (l_mm, w_mm, t_mm), fs in groups:
                sym = get_or_create_sized_footing_type(
                    doc, options.base_symbol, l_mm / 304.8, w_mm / 304.8, t_mm / 304.8, _SNAP, cache)
                floors_by_type.append((sym, fs))
        else:
            floors_by_type.append((options.base_symbol, [f for _key, fs in groups for f in fs]))

        res = place_footings(doc, floors_by_type, material_id=options.material_id,
                             delete_source_floors=options.delete_source)
        if res.placed == 0:
            t.RollBack()
        else:
            t.Commit()
    except Exception as e:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        logger.error("Floors to Footings failed: {0}".format(str(e)))
        show_result(__title__, "Floors to Footings failed:\n{0}".format(str(e)))
        return

    if res.placed == 0:
        msg = "No footings were placed."
        if res.errors:
            msg += "\n\n" + "\n".join(res.errors[:5])
        show_result(__title__, msg)
        return

    extra = "\n{0} skipped (degenerate footprint or missing level).".format(res.skipped) if res.skipped else ""
    show_result(
        __title__,
        "Floors to Footings Complete.\n\n"
        "Successfully placed {0} footing(s).{1}".format(res.placed, extra))
    if res.errors:
        output.print_md("**Notes:** " + "; ".join(res.errors[:5]))


if __name__ == "__main__":
    main()
