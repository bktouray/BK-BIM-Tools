# -*- coding: utf-8 -*-
__title__ = u"Typical\nBeams"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Cuts one detail section per typical beam (grouped by Mark -
run Auto Mark for Beams first). Reports how many beams share each section,
and cuts a cross-section detail view at each typical beam's mid-span with
a configurable far clip offset.
"""

from pyrevit import revit, DB, forms, script

import sys as _sys
for _m in [_n for _n in list(_sys.modules) if _n.startswith("bkbim.automation")]:
    del _sys.modules[_m]

from bkbim.automation.common import to_feet
from bkbim.automation.typical_views import (
    cut_beam_section, cut_typical_views,
    group_by_mark, pick_section_view_family_type, unmarked_elements,
)
from bkbim.ui.views.typical_section_options import show_typical_section_options

logger = script.get_logger()
doc = revit.doc

_CATEGORY_LABEL = u"Beam"
_DEFAULT_FAR_CLIP_MM = 100.0

MODE_LABEL_GROUP = u"One view per typical section (recommended)"
MODE_LABEL_INSTANCE = u"One view per individual beam"


def _collect_beams():
    collected = (DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_StructuralFraming)
                 .WhereElementIsNotElementType().ToElements())
    return [e for e in collected if isinstance(e, DB.FamilyInstance)]


def main():
    if doc is None:
        forms.alert("No active Revit document.", title=__title__)
        return

    beams = _collect_beams()
    if not beams:
        forms.alert("No beams found in the model.", title=__title__)
        return

    missing = unmarked_elements(beams)
    if missing:
        forms.alert(
            "{0} of {1} beam(s) have no Mark yet.\n\n"
            "Run Auto Mark for Beams first, then try again.".format(len(missing), len(beams)),
            title=__title__)
        return

    groups = group_by_mark(beams)
    summary_lines = [u"{0}: {1} beam(s)".format(mark, len(members)) for mark, members in groups]

    options = show_typical_section_options(
        __title__.replace("\n", " "),
        u"{0} typical beam section(s) found across {1} beam(s).".format(len(groups), len(beams)),
        summary_lines, MODE_LABEL_GROUP, MODE_LABEL_INSTANCE,
        u"Far clip offset beyond mid-span (mm)", _DEFAULT_FAR_CLIP_MM)
    if not options:
        return
    mode = options.mode
    far_clip_ft = to_feet(options.value_mm, "mm")

    vft = pick_section_view_family_type(doc)
    if vft is None:
        forms.alert("No Section view family type found in this project.", title=__title__)
        return

    def cutter(doc, elem, view_name, vft_id=vft.Id, far_clip_ft=far_clip_ft):
        return cut_beam_section(doc, vft_id, elem, far_clip_ft, view_name)

    t = DB.Transaction(doc, "Cut Typical Beam Sections")
    t.Start()
    try:
        res = cut_typical_views(doc, beams, _CATEGORY_LABEL, cutter, mode=mode)
        if res.created == 0:
            t.RollBack()
        else:
            t.Commit()
    except Exception as e:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        logger.error("Typical Beams failed: {0}".format(str(e)))
        forms.alert("Typical Beams failed:\n{0}".format(str(e)), title=__title__)
        return

    if res.created == 0:
        msg = "No detail views were created."
        if res.errors:
            msg += "\n\n" + "\n".join(res.errors[:5])
        forms.alert(msg, title=__title__)
        return

    extra = "\n{0} skipped.".format(res.skipped) if res.skipped else ""
    forms.alert(
        "Typical Beams Complete.\n\n"
        "Created {0} detail section view(s).{1}".format(res.created, extra),
        title=__title__)


if __name__ == "__main__":
    main()
