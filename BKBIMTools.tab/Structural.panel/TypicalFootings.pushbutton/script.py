# -*- coding: utf-8 -*-
__title__ = u"Typical\nFootings"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Cuts one detail section per typical footing (grouped by
Mark - run Auto Mark for Footings first). Reports how many footings share
each section, and cuts a horizontal detail view above each typical footing's
top with the far clip extended below its bottom.
"""

from pyrevit import revit, DB, script

import sys as _sys
for _m in [_n for _n in list(_sys.modules)
           if _n.startswith("bkbim.automation")
           or _n == "bkbim.ui.views.typical_section_options"]:
    del _sys.modules[_m]

from bkbim.automation.common import to_feet
from bkbim.automation.typical_views import (
    cut_footing_section, cut_typical_views,
    group_by_mark, list_typical_view_family_types, unmarked_elements,
)
from bkbim.ui.views.result_dialog import show_result
from bkbim.ui.views.typical_section_options import show_typical_section_options

logger = script.get_logger()
doc = revit.doc

_CATEGORY_LABEL = u"Footing"
_DEFAULT_ABOVE_TOP_MM = 150.0
_DEFAULT_FAR_CLIP_MARGIN_MM = 150.0

MODE_LABEL_GROUP = u"One view per typical section (recommended)"
MODE_LABEL_INSTANCE = u"One view per individual footing"


def _name(el):
    try:
        return el.Name
    except Exception:
        return DB.Element.Name.__get__(el)


def _collect_footings():
    collected = (DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_StructuralFoundation)
                 .WhereElementIsNotElementType().ToElements())
    return [e for e in collected if isinstance(e, DB.FamilyInstance)]


def main():
    if doc is None:
        show_result(__title__, "No active Revit document.")
        return

    footings = _collect_footings()
    if not footings:
        show_result(__title__, "No isolated footings found in the model.")
        return

    missing = unmarked_elements(footings)
    if missing:
        show_result(
            __title__,
            "{0} of {1} footing(s) have no Mark yet.\n\n"
            "Run Auto Mark for Footings first, then try again.".format(len(missing), len(footings)))
        return

    groups = group_by_mark(footings)
    summary_lines = [u"{0}: {1} footing(s)".format(mark, len(members)) for mark, members in groups]

    view_types = list_typical_view_family_types(doc)
    if not view_types:
        show_result(__title__, "No Detail or Section view family type found in this project.")
        return

    options = show_typical_section_options(
        __title__.replace("\n", " "),
        u"{0} typical footing section(s) found across {1} footing(s).".format(len(groups), len(footings)),
        summary_lines, MODE_LABEL_GROUP, MODE_LABEL_INSTANCE,
        u"Cut height above footing top (mm)", _DEFAULT_ABOVE_TOP_MM,
        u"Far clip below footing bottom (mm)", _DEFAULT_FAR_CLIP_MARGIN_MM,
        view_family_types=view_types, view_family_type_name_fn=_name, default_view_family_type=view_types[0])
    if not options:
        return
    mode = options.mode
    above_top_ft = to_feet(options.value_mm, "mm")
    margin_mm = options.secondary_value_mm
    if margin_mm is None:
        margin_mm = _DEFAULT_FAR_CLIP_MARGIN_MM
    margin_ft = to_feet(margin_mm, "mm")

    vft = options.view_family_type or view_types[0]

    def cutter(doc, elem, view_name, vft_id=vft.Id, above_top_ft=above_top_ft, margin_ft=margin_ft):
        return cut_footing_section(doc, vft_id, elem, above_top_ft, margin_ft, view_name)

    t = DB.Transaction(doc, "Cut Typical Footing Sections")
    t.Start()
    try:
        res = cut_typical_views(doc, footings, _CATEGORY_LABEL, cutter, mode=mode)
        if res.created == 0:
            t.RollBack()
        else:
            t.Commit()
    except Exception as e:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        logger.error("Typical Footings failed: {0}".format(str(e)))
        show_result(__title__, "Typical Footings failed:\n{0}".format(str(e)))
        return

    if res.created == 0:
        msg = "No detail views were created."
        if res.errors:
            msg += "\n\n" + "\n".join(res.errors[:5])
        show_result(__title__, msg)
        return

    extra = "\n{0} skipped.".format(res.skipped) if res.skipped else ""
    show_result(
        __title__,
        "Typical Footings Complete.\n\n"
        "Created {0} detail section view(s).{1}".format(res.created, extra))


if __name__ == "__main__":
    main()
