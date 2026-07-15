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
each section, and cuts a horizontal detail view 200mm above each typical
footing's top with the far clip extended past its bottom.
"""

from pyrevit import revit, DB, forms, script

import sys as _sys
for _m in [_n for _n in list(_sys.modules) if _n.startswith("bkbim.automation")]:
    del _sys.modules[_m]

from bkbim.automation.common import to_feet
from bkbim.automation.typical_views import (
    cut_footing_section, cut_typical_views,
    group_by_mark, pick_section_view_family_type, unmarked_elements,
)
from bkbim.ui.views.typical_section_options import show_typical_section_options

logger = script.get_logger()
doc = revit.doc

_CATEGORY_LABEL = u"Footing"
_ABOVE_TOP_MM = 200.0  # fixed, per product owner's spec - not user-adjustable
_DEFAULT_FAR_CLIP_MARGIN_MM = 100.0

MODE_LABEL_GROUP = u"One view per typical section (recommended)"
MODE_LABEL_INSTANCE = u"One view per individual footing"


def _collect_footings():
    collected = (DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_StructuralFoundation)
                 .WhereElementIsNotElementType().ToElements())
    return [e for e in collected if isinstance(e, DB.FamilyInstance)]


def main():
    if doc is None:
        forms.alert("No active Revit document.", title=__title__)
        return

    footings = _collect_footings()
    if not footings:
        forms.alert("No isolated footings found in the model.", title=__title__)
        return

    missing = unmarked_elements(footings)
    if missing:
        forms.alert(
            "{0} of {1} footing(s) have no Mark yet.\n\n"
            "Run Auto Mark for Footings first, then try again.".format(len(missing), len(footings)),
            title=__title__)
        return

    groups = group_by_mark(footings)
    summary_lines = [u"{0}: {1} footing(s)".format(mark, len(members)) for mark, members in groups]

    options = show_typical_section_options(
        __title__.replace("\n", " "),
        u"{0} typical footing section(s) found across {1} footing(s).".format(len(groups), len(footings)),
        summary_lines, MODE_LABEL_GROUP, MODE_LABEL_INSTANCE,
        u"Margin below the footing's bottom, far clip (mm)", _DEFAULT_FAR_CLIP_MARGIN_MM)
    if not options:
        return
    mode = options.mode
    margin_ft = to_feet(options.value_mm, "mm")
    above_top_ft = to_feet(_ABOVE_TOP_MM, "mm")

    vft = pick_section_view_family_type(doc)
    if vft is None:
        forms.alert("No Section view family type found in this project.", title=__title__)
        return

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
        forms.alert("Typical Footings failed:\n{0}".format(str(e)), title=__title__)
        return

    if res.created == 0:
        msg = "No detail views were created."
        if res.errors:
            msg += "\n\n" + "\n".join(res.errors[:5])
        forms.alert(msg, title=__title__)
        return

    extra = "\n{0} skipped.".format(res.skipped) if res.skipped else ""
    forms.alert(
        "Typical Footings Complete.\n\n"
        "Created {0} detail section view(s).{1}".format(res.created, extra),
        title=__title__)


if __name__ == "__main__":
    main()
