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

from Autodesk.Revit.DB import BuiltInParameter, FilteredElementCollector, TransactionGroup
from Autodesk.Revit.DB.Plumbing import Pipe, PipeType

from bkbim.core.tool_memory import recall, remember
from bkbim.domain.geometry.units import ft_to_mm
from bkbim.domain.mep.routing.water_supply_clash import detect_hot_cold_clashes
from bkbim.domain.standards.standard import load_office_standard
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.mep.water_supply_flow import COLD_WATER, HOT_WATER, run_wizard
from bkbim.ui.views.water_supply_options import show_water_supply_options, show_water_supply_result

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


def _element_id_value(element):
    try:
        return element.Id.Value
    except Exception:
        return element.Id.IntegerValue


def _pipe_ids():
    return set(
        _element_id_value(pipe)
        for pipe in FilteredElementCollector(doc).OfClass(Pipe).ToElements())


def _pipe_diameter_mm(pipe):
    try:
        param = pipe.get_Parameter(BuiltInParameter.RBS_PIPE_DIAMETER_PARAM)
        if param is not None:
            return ft_to_mm(param.AsDouble())
    except Exception:
        pass
    return None


def _new_pipe_segments(before_ids, system_name):
    segments = []
    for pipe in FilteredElementCollector(doc).OfClass(Pipe).ToElements():
        pipe_id = _element_id_value(pipe)
        if pipe_id in before_ids:
            continue
        try:
            curve = pipe.Location.Curve
            start = curve.GetEndPoint(0)
            end = curve.GetEndPoint(1)
        except Exception:
            continue
        segments.append({
            "system": system_name,
            "kind": u"generated",
            "label": u"pipe {0}".format(pipe_id),
            "start": (ft_to_mm(start.X), ft_to_mm(start.Y), ft_to_mm(start.Z)),
            "end": (ft_to_mm(end.X), ft_to_mm(end.Y), ft_to_mm(end.Z)),
            "diameter_mm": _pipe_diameter_mm(pipe),
        })
    return segments


def _rollback_group(group):
    if group is not None:
        try:
            group.RollBack()
        except Exception:
            pass


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
    cold_segments = []
    hot_segments = []
    group = None
    if options.run_cold and options.run_hot:
        group = TransactionGroup(doc, u"Route Water Supply")
        group.Start()

    if options.run_cold:
        before_pipe_ids = _pipe_ids()
        routed_count, message = _run_one(COLD_WATER, options.cold_pipe_type_name)
        if message:
            messages.append(u"Cold Water:\n{0}".format(message))
        if routed_count is None and message is None:
            _rollback_group(group)
            return
        if routed_count:
            total_routed += routed_count
            cold_segments = _new_pipe_segments(before_pipe_ids, u"Cold Water")
            remember(_COLD_PIPE_TYPE_KEY, options.cold_pipe_type_name, doc=doc)
        else:
            _rollback_group(group)
            show_water_supply_result(__title__, u"\n\n".join(messages))
            return

    if options.run_hot:
        before_pipe_ids = _pipe_ids()
        routed_count, message = _run_one(HOT_WATER, options.hot_pipe_type_name)
        if message:
            messages.append(u"Hot Water:\n{0}".format(message))
        if routed_count is None and message is None:
            _rollback_group(group)
            return
        if routed_count:
            total_routed += routed_count
            hot_segments = _new_pipe_segments(before_pipe_ids, u"Hot Water")
            remember(_HOT_PIPE_TYPE_KEY, options.hot_pipe_type_name, doc=doc)
        else:
            _rollback_group(group)
            show_water_supply_result(__title__, u"\n\n".join(messages))
            return

    if group is not None:
        clashes = detect_hot_cold_clashes(cold_segments, hot_segments)
        if clashes:
            _rollback_group(group)
            show_water_supply_result(
                __title__,
                u"Water Supply was rolled back because Hot and Cold routes "
                u"clash.\n\nDetails:\n- {0}\n\nIncrease the hot/cold offset "
                u"or adjust the valve/main positions.".format(
                    u"\n- ".join(clashes)))
            return
        group.Assimilate()

    if messages:
        header = u"Water Supply complete: {0} fixture route(s) created.".format(total_routed)
        show_water_supply_result(
            __title__, u"{0}\n\n{1}".format(header, u"\n\n".join(messages)))


if __name__ == "__main__":
    main()
