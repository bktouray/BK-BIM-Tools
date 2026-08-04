# -*- coding: utf-8 -*-
__title__ = u"Generate\nSanitary Drainage"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval).
# __authors__ (plural) is the one this pyRevit build actually applies.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Detects plumbing fixtures in the room(s) you pick and creates
the first pipe-only DWV collector slice: a sloped collector main toward a
clicked stack/riser point with fixture branches projected onto a confirmed
wall corridor. Fittings and connector joins are intentionally deferred to
the next DWV validation pass.
"""

from Autodesk.Revit.DB import FilteredElementCollector
from Autodesk.Revit.DB.Plumbing import PipeType

from bkbim.core.tool_memory import recall, remember
from bkbim.domain.standards.standard import load_office_standard
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.mep.dwv_collector_flow import run_wizard
from bkbim.ui.views.list_picker import show_list_picker
from bkbim.ui.views.result_dialog import show_result

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

_PIPE_TYPE_KEY = u"mep.sanitary_drainage.pipe_type_name"


def _pick_pipe_type():
    pipe_types = list(FilteredElementCollector(doc).OfClass(PipeType).ToElements())
    if not pipe_types:
        show_result(__title__, u"No Pipe Types found in this project.")
        return None
    names = sorted(set(type_name(pt) for pt in pipe_types))

    remembered = recall(_PIPE_TYPE_KEY, doc=doc)
    if remembered in names:
        names = [remembered] + [n for n in names if n != remembered]

    return show_list_picker(
        __title__, u"Pick the pipe type to route Sanitary Drainage with.",
        names, default_label=remembered if remembered in names else None)


def main():
    pipe_type_name = _pick_pipe_type()
    if not pipe_type_name:
        return

    standard = load_office_standard()
    result, message = run_wizard(uidoc, doc, standard, u"intermittent", pipe_type_name)
    if message:
        show_result(__title__, message)
    if result is not None and result.success:
        remember(_PIPE_TYPE_KEY, pipe_type_name, doc=doc)


if __name__ == "__main__":
    main()
