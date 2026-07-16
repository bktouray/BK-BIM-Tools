# -*- coding: utf-8 -*-
__title__ = u"Route\nWater Supply"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval).
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Combined Water Supply launcher.

Lets the user route Domestic Cold Water, Domestic Hot Water, or both from one
branded start window while retaining the separate Cold/Hot pushbuttons. The
actual routing is delegated to the same proven water_supply_flow.run_wizard()
used by the individual buttons.
"""

from pyrevit import forms

from Autodesk.Revit.DB import FilteredElementCollector
from Autodesk.Revit.DB.Plumbing import PipeType

from bkbim.core.tool_memory import recall, remember
from bkbim.domain.standards.standard import load_office_standard
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.mep.water_supply_flow import COLD_WATER, HOT_WATER, run_wizard
from bkbim.ui.views.water_supply_options import show_water_supply_options

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

_COLD_PIPE_TYPE_KEY = u"mep.water_supply.pipe_type_name"
_HOT_PIPE_TYPE_KEY = u"mep.hot_water.pipe_type_name"


def _pipe_type_names():
    pipe_types = list(FilteredElementCollector(doc).OfClass(PipeType).ToElements())
    if not pipe_types:
        forms.alert(u"No Pipe Types found in this project.", title=__title__)
        return []
    return sorted(set(type_name(pt) for pt in pipe_types))


def _run_one(system_classification, pipe_type_name):
    standard = load_office_standard()
    return run_wizard(
        uidoc, doc, standard, pipe_type_name,
        system_classification=system_classification)


def main():
    names = _pipe_type_names()
    if not names:
        return

    options = show_water_supply_options(
        names,
        remembered_cold=recall(_COLD_PIPE_TYPE_KEY, doc=doc),
        remembered_hot=recall(_HOT_PIPE_TYPE_KEY, doc=doc))
    if options is None:
        return

    messages = []
    total_routed = 0

    if options.run_cold:
        routed_count, message = _run_one(COLD_WATER, options.cold_pipe_type_name)
        if message:
            messages.append(u"Cold Water:\n{0}".format(message))
        if routed_count is None and message is None:
            return
        if routed_count:
            total_routed += routed_count
            remember(_COLD_PIPE_TYPE_KEY, options.cold_pipe_type_name, doc=doc)
        else:
            forms.alert(u"\n\n".join(messages), title=__title__)
            return

    if options.run_hot:
        routed_count, message = _run_one(HOT_WATER, options.hot_pipe_type_name)
        if message:
            messages.append(u"Hot Water:\n{0}".format(message))
        if routed_count is None and message is None:
            return
        if routed_count:
            total_routed += routed_count
            remember(_HOT_PIPE_TYPE_KEY, options.hot_pipe_type_name, doc=doc)
        else:
            forms.alert(u"\n\n".join(messages), title=__title__)
            return

    if messages:
        header = u"Water Supply complete: {0} fixture route(s) created.".format(total_routed)
        forms.alert(u"{0}\n\n{1}".format(header, u"\n\n".join(messages)), title=__title__)


if __name__ == "__main__":
    main()
