# -*- coding: utf-8 -*-
__title__ = u"Route\nHot Water"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval).
# __authors__ (plural) is the one this pyRevit build actually applies.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Routes one selected room's unconnected Domestic Hot Water
fixture inlets from a picked or existing incoming main and valve routing
point along one confirmed connected wall path.
Creates the feed, wall-derived trunk, fixture branches and fittings.
Any required pipe, fitting or connector failure rolls back the whole route.
"""

from pyrevit import forms

from Autodesk.Revit.DB import FilteredElementCollector
from Autodesk.Revit.DB.Plumbing import PipeType

from bkbim.core.tool_memory import recall, remember
from bkbim.domain.standards.standard import load_office_standard
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.mep.water_supply_flow import HOT_WATER, run_wizard

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

_PIPE_TYPE_KEY = u"mep.hot_water.pipe_type_name"


def _pick_pipe_type():
    pipe_types = list(FilteredElementCollector(doc).OfClass(PipeType).ToElements())
    if not pipe_types:
        forms.alert(u"No Pipe Types found in this project.", title=__title__)
        return None
    names = sorted(set(type_name(pt) for pt in pipe_types))

    remembered = recall(_PIPE_TYPE_KEY, doc=doc)
    if remembered in names:
        names = [remembered] + [n for n in names if n != remembered]

    return forms.SelectFromList.show(
        names, title=u"Pick the pipe type for Hot Water", multiselect=False)


def main():
    pipe_type_name = _pick_pipe_type()
    if not pipe_type_name:
        return

    standard = load_office_standard()
    routed_count, message = run_wizard(
        uidoc, doc, standard, pipe_type_name, system_classification=HOT_WATER)
    if message:
        forms.alert(message, title=__title__)
    if routed_count:
        remember(_PIPE_TYPE_KEY, pipe_type_name, doc=doc)


if __name__ == "__main__":
    main()
