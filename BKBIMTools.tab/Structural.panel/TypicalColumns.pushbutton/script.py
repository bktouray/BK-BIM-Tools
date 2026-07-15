# -*- coding: utf-8 -*-
__title__ = u"Typical\nColumns"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Cuts one detail section per typical column (grouped by
Mark - run Auto Mark for Columns first). Reports how many columns share
each section, and cuts a horizontal detail view at each typical column's
mid-height with a configurable far clip offset.
"""

from pyrevit import revit, DB, forms, script

import sys as _sys
for _m in [_n for _n in list(_sys.modules) if _n.startswith("bkbim.automation")]:
    del _sys.modules[_m]

from bkbim.automation.common import to_feet
from bkbim.automation.typical_views import (
    cut_column_section, cut_typical_views,
    group_by_mark, pick_section_view_family_type, unmarked_elements,
)
from bkbim.ui.views.typical_section_options import show_typical_section_options

logger = script.get_logger()
doc = revit.doc

_CATEGORY_LABEL = u"Column"
_DEFAULT_FAR_CLIP_MM = 100.0

MODE_LABEL_GROUP = u"One view per typical section (recommended)"
MODE_LABEL_INSTANCE = u"One view per individual column"


def _collect_columns():
    elems = []
    for bic in (DB.BuiltInCategory.OST_StructuralColumns, DB.BuiltInCategory.OST_Columns):
        collected = DB.FilteredElementCollector(doc).OfCategory(bic).WhereElementIsNotElementType().ToElements()
        elems.extend([e for e in collected if isinstance(e, DB.FamilyInstance)])
    return elems


def main():
    if doc is None:
        forms.alert("No active Revit document.", title=__title__)
        return

    columns = _collect_columns()
    if not columns:
        forms.alert("No columns found in the model.", title=__title__)
        return

    missing = unmarked_elements(columns)
    if missing:
        forms.alert(
            "{0} of {1} column(s) have no Mark yet.\n\n"
            "Run Auto Mark for Columns first, then try again.".format(len(missing), len(columns)),
            title=__title__)
        return

    groups = group_by_mark(columns)
    summary_lines = [u"{0}: {1} column(s)".format(mark, len(members)) for mark, members in groups]

    options = show_typical_section_options(
        __title__.replace("\n", " "),
        u"{0} typical column section(s) found across {1} column(s).".format(len(groups), len(columns)),
        summary_lines, MODE_LABEL_GROUP, MODE_LABEL_INSTANCE,
        u"Far clip offset below mid-height (mm)", _DEFAULT_FAR_CLIP_MM)
    if not options:
        return
    mode = options.mode
    far_clip_ft = to_feet(options.value_mm, "mm")

    vft = pick_section_view_family_type(doc)
    if vft is None:
        forms.alert("No Section view family type found in this project.", title=__title__)
        return

    def cutter(doc, elem, view_name, vft_id=vft.Id, far_clip_ft=far_clip_ft):
        return cut_column_section(doc, vft_id, elem, far_clip_ft, view_name)

    t = DB.Transaction(doc, "Cut Typical Column Sections")
    t.Start()
    try:
        res = cut_typical_views(doc, columns, _CATEGORY_LABEL, cutter, mode=mode)
        if res.created == 0:
            t.RollBack()
        else:
            t.Commit()
    except Exception as e:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        logger.error("Typical Columns failed: {0}".format(str(e)))
        forms.alert("Typical Columns failed:\n{0}".format(str(e)), title=__title__)
        return

    if res.created == 0:
        msg = "No detail views were created."
        if res.errors:
            msg += "\n\n" + "\n".join(res.errors[:5])
        forms.alert(msg, title=__title__)
        return

    extra = "\n{0} skipped.".format(res.skipped) if res.skipped else ""
    forms.alert(
        "Typical Columns Complete.\n\n"
        "Created {0} detail section view(s).{1}".format(res.created, extra),
        title=__title__)


if __name__ == "__main__":
    main()
