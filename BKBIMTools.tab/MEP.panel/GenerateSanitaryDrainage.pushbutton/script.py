# -*- coding: utf-8 -*-
__title__ = u"Generate\nSanitary Drainage"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval).
# __authors__ (plural) is the one this pyRevit build actually applies.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Detects plumbing fixtures in the room(s) you pick and routes
Sanitary Drainage pipes to a point you click. Highlights the room in green
and the nearby wall(s) in blue so you can confirm or reselect before
anything is created.
"""

from pyrevit import forms

from Autodesk.Revit.DB import FilteredElementCollector
from Autodesk.Revit.DB.Plumbing import PipeType

from bkbim.core.tool_memory import recall, remember
from bkbim.domain.standards.standard import load_office_standard
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.mep.sanitary_drainage_flow import run_wizard

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

_PIPE_TYPE_KEY = u"mep.sanitary_drainage.pipe_type_name"


def _pick_pipe_type():
    pipe_types = list(FilteredElementCollector(doc).OfClass(PipeType).ToElements())
    if not pipe_types:
        forms.alert(u"No Pipe Types found in this project.", title=__title__)
        return None
    names = sorted(set(type_name(pt) for pt in pipe_types))

    # Surface last run's pick at the top of the list (Tool Memory, PROJECT
    # layer - this project's loaded PipeTypes are project-specific) - a real
    # pre-selected default isn't available through forms.SelectFromList, so
    # this is the cheap, honest equivalent: still one click, but the
    # remembered choice is immediately visible instead of buried
    # alphabetically.
    remembered = recall(_PIPE_TYPE_KEY, doc=doc)
    if remembered in names:
        names = [remembered] + [n for n in names if n != remembered]

    return forms.SelectFromList.show(
        names, title=u"Pick the pipe type to route Sanitary Drainage with", multiselect=False)


def main():
    pipe_type_name = _pick_pipe_type()
    if not pipe_type_name:
        return

    standard = load_office_standard()
    result, message = run_wizard(uidoc, doc, standard, u"intermittent", pipe_type_name)
    if message:
        forms.alert(message, title=__title__)
    if result is not None and result.success:
        remember(_PIPE_TYPE_KEY, pipe_type_name, doc=doc)


if __name__ == "__main__":
    main()
