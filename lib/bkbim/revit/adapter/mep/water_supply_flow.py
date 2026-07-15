# -*- coding: utf-8 -*-
"""Runs the Water Supply generation flow (ADR-0004 update, 2026-07-10:
Sanitary Drainage paused, Water Supply is the active MEP slice). Mirrors
sanitary_drainage_flow.py's shape - room pick/highlight -> fixture read ->
wall detect/confirm -> routing-style pick -> supply point pick -> execute ->
cleanup - reusing every proven piece (room_reader, room_selection_prompt,
room_highlight, nearby_wall_finder, wall_confirmation_prompt,
resolve_piping_system_type_id/resolve_pipe_type_id_by_name) rather than
duplicating them (ADR-0002 second-consumer rule).

Rebuilt 2026-07-10 (same day) onto the corridor-based trunk-and-branch
RoutingGraph engine (MEP_Routing_Playbook.md) - the product owner tried the
original per-fixture independent-elbow-route model live and rejected it (a
diagonal fan of pipes, not how real water supply is installed). Runs all
four phases in one Transaction: Phase 1 (build the graph, via
generate_water_supply_command) -> Phase 2 (PipeGeometryWriter) -> Phase 3
(FittingGenerationWriter) -> Phase 4 (AccessoryPlacementWriter, only if a
valve symbol was picked).

No sizing engine (ADR-0004's "don't guess a standard" rule) - each branch is
sized from the fixture's own connector diameter; the trunk uses the largest
connector diameter among the routed fixtures as a simple, disclosed default
pending a real sizing method.
"""

import clr

clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")

from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector, Transaction
from pyrevit import forms

from bkbim.app.commands import generate_water_supply_command
from bkbim.domain.geometry.units import ft_to_mm
from bkbim.domain.mep.routing.path_planner import RoutingStyle
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.mep.accessory_placement_writer import AccessoryPlacementWriter
from bkbim.revit.adapter.mep.fitting_generation_writer import FittingGenerationWriter
from bkbim.revit.adapter.mep.fixture_reader import RevitFixtureReader
from bkbim.revit.adapter.mep.nearby_wall_finder import find_nearest_walls_for_fixtures
from bkbim.revit.adapter.mep.pipe_geometry_writer import PipeGeometryWriter
from bkbim.revit.adapter.mep.room_highlight import highlight_room
from bkbim.revit.adapter.mep.room_reader import RevitRoomReader
from bkbim.revit.adapter.mep.room_selection_prompt import pick_rooms
from bkbim.revit.adapter.mep.sanitary_drainage_flow import (
    resolve_piping_system_type_id, resolve_pipe_type_id_by_name)
from bkbim.revit.adapter.mep.wall_confirmation_prompt import confirm_walls, highlight_walls
from bkbim.revit.adapter.mep.wall_corridor import corridor_points_from_walls
from bkbim.revit.adapter.stable_representation import element_id_token
from bkbim.ui.views.category_picker import show_category_picker

_TITLE = u"Generate Water Supply"

COLD_WATER = u"DomesticColdWater"
HOT_WATER = u"DomesticHotWater"

_SYSTEM_CHOICES = [
    (u"Cold Water only", [COLD_WATER]),
    (u"Hot Water only", [HOT_WATER]),
    (u"Both (Cold + Hot)", [COLD_WATER, HOT_WATER]),
]

_ROUTING_STYLE_CHOICES = [
    (u"Through the ceiling (drops down through the wall)", RoutingStyle.CEILING_DROP),
    (u"Under the floor (rises up through the wall)", RoutingStyle.FLOOR_RISE),
    (u"Inside the wall (horizontal + vertical, at valve height)", RoutingStyle.IN_WALL),
]

_NO_VALVE = u"No valve - just route the pipes"
_WALL_PENETRATION_MM = 80.0  # product owner's own confirmed default


def _pipe_system_name(system_classification):
    return u"Domestic Cold Water" if system_classification == COLD_WATER else u"Domestic Hot Water"


def pick_valve_symbol(doc):
    """Lists real Pipe Accessory family symbols in the project, plus a
    "no valve" option (Phase 4 is optional - MEP_Routing_Playbook.md Sec 17).
    Returns a FamilySymbol, or None if skipped/cancelled.
    """
    symbols = list(FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_PipeAccessory)
                   .WhereElementIsElementType().ToElements())
    if not symbols:
        return None

    names = {}
    for s in symbols:
        try:
            fam_name = s.Family.Name
        except Exception:
            fam_name = u"?"
        label = u"{0} - {1}".format(fam_name, type_name(s))
        names[label] = s

    choice = forms.SelectFromList.show(
        [_NO_VALVE] + sorted(names.keys()), title=u"Pick an isolation valve (or skip)", multiselect=False)
    if not choice or choice == _NO_VALVE:
        return None
    return names[choice]


def run_water_supply_flow(doc, fixtures, system_classification, corridor_points,
                           trunk_diameter_mm, level_id, pipe_type_name, valve_symbol=None):
    """Runs Phases 1-4 for one system (Cold or Hot) inside one Transaction.
    Returns (result, message) - result is None if a required project element
    couldn't be resolved.
    """
    system_type_id = resolve_piping_system_type_id(doc, _pipe_system_name(system_classification))
    if system_type_id is None:
        return None, u"No '{0}' Piping System Type found in this project.".format(
            _pipe_system_name(system_classification))

    pipe_type_id = resolve_pipe_type_id_by_name(doc, pipe_type_name)
    if pipe_type_id is None:
        return None, u"Pipe type '{0}' not found in this project.".format(pipe_type_name)

    t = Transaction(doc, _TITLE)
    t.Start()
    try:
        cmd_result = generate_water_supply_command.run(
            fixtures, system_classification, corridor_points, _WALL_PENETRATION_MM)
        if not cmd_result.success:
            t.RollBack()
            return cmd_result, cmd_result.message

        graph = cmd_result.value["graph"]

        geometry_writer = PipeGeometryWriter(doc, system_type_id, pipe_type_id, level_id)
        geo_result = geometry_writer.write(graph, trunk_diameter_mm)
        if not geo_result.success:
            t.RollBack()
            return geo_result, geo_result.message

        fitting_writer = FittingGenerationWriter(doc)
        fit_result = fitting_writer.write(
            graph, geo_result.value["trunk_pipes"], geo_result.value["branch_pipes"])

        valve_note = u""
        if valve_symbol is not None:
            accessory_writer = AccessoryPlacementWriter(doc)
            acc_result = accessory_writer.place_origin_valve(
                graph, valve_symbol, geo_result.value["trunk_pipes"])
            valve_note = u" Valve: {0}.".format(
                u"placed" if acc_result.success else u"not placed ({0})".format(acc_result.message))
    except Exception as e:
        t.RollBack()
        return None, u"Error:\n{0}".format(str(e))

    t.Commit()

    message = u"{0} fixture(s) routed. {1} tee(s), {2} elbow(s), {3} direct connection(s).{4}".format(
        cmd_result.value["routed"], fit_result.value["tees_created"] if fit_result.success else 0,
        fit_result.value["elbows_created"] if fit_result.success else 0,
        fit_result.value["connections_made"] if fit_result.success else 0, valve_note)

    return cmd_result, message


def run_wizard(uidoc, doc, standard, pipe_type_name):
    """Full Tier-1/2 flow. Returns (routed_count, message) - routed_count is
    None if the user cancelled at any step (normal, not an error).
    """
    view = doc.ActiveView

    rooms = RevitRoomReader(doc).read_rooms()
    if not rooms:
        return None, u"No rooms found in this project."

    picked_rooms = pick_rooms(rooms, title=_TITLE)
    if not picked_rooms:
        return None, None

    highlight_t = Transaction(doc, u"Highlight selected rooms")
    highlight_t.Start()
    for room_info in picked_rooms:
        room_elem = doc.GetElement(room_info.ref)
        if room_elem is not None:
            highlight_room(doc, view, room_elem)
    highlight_t.Commit()

    try:
        fixtures = RevitFixtureReader(doc).read_fixtures(rooms=picked_rooms)
        if not fixtures:
            forms.alert(u"No plumbing fixtures found in the selected room(s).", title=_TITLE)
            return None, None

        wall_map = find_nearest_walls_for_fixtures(doc, fixtures)
        candidate_walls = []
        seen_ids = set()
        for fixture in fixtures:
            nearest = wall_map.get(element_id_token(fixture.ref))
            if nearest is not None and element_id_token(nearest.wall_ref) not in seen_ids:
                seen_ids.add(element_id_token(nearest.wall_ref))
                wall_elem = doc.GetElement(nearest.wall_ref)
                if wall_elem is not None:
                    candidate_walls.append(wall_elem)

        wall_highlight_t = Transaction(doc, u"Highlight candidate walls")
        wall_highlight_t.Start()
        if candidate_walls:
            highlight_walls(doc, view, candidate_walls)
        wall_highlight_t.Commit()

        try:
            confirmed_walls = confirm_walls(uidoc, doc, candidate_walls, title=_TITLE)
        finally:
            clear_t = Transaction(doc, u"Clear wall highlight")
            clear_t.Start()
            if candidate_walls:
                highlight_walls(doc, view, candidate_walls, clear=True)
            if confirmed_walls:
                highlight_walls(doc, view, confirmed_walls, clear=True)
            clear_t.Commit()

        if not confirmed_walls:
            forms.alert(
                u"No wall confirmed - the trunk needs a wall corridor to run along, "
                u"so there's nothing to route. Try again and confirm at least one wall.",
                title=_TITLE)
            return None, None

        system_choice = show_category_picker(
            _TITLE, u"Which system(s) to route?", [label for label, _ in _SYSTEM_CHOICES])
        if system_choice is None:
            return None, None
        system_classifications = dict(_SYSTEM_CHOICES)[system_choice]

        style_choice = show_category_picker(
            _TITLE, u"How does the supply pipe reach each fixture?",
            [label for label, _ in _ROUTING_STYLE_CHOICES])
        if style_choice is None:
            return None, None
        routing_style = dict(_ROUTING_STYLE_CHOICES)[style_choice]

        forms.alert(
            u"Click the point the supply main enters this room (the trunk's origin).",
            title=_TITLE)
        try:
            picked_point = uidoc.Selection.PickPoint(u"{0}: click the supply origin point".format(_TITLE))
        except Exception:
            return None, None
        origin_mm = (ft_to_mm(picked_point.X), ft_to_mm(picked_point.Y), ft_to_mm(picked_point.Z))

        # IN_WALL uses the fixed valve-height convention (product owner,
        # 2026-07-10: "all of my valves are at 1.8m from the level") instead
        # of whatever Z the user happened to click at.
        if routing_style == RoutingStyle.IN_WALL:
            horizontal_z_mm = standard.mep_valve_height_mm
        else:
            horizontal_z_mm = origin_mm[2]

        corridor_points = ([(origin_mm[0], origin_mm[1], horizontal_z_mm)] +
                            corridor_points_from_walls(confirmed_walls, horizontal_z_mm))

        valve_symbol = pick_valve_symbol(doc)

        level_id = fixtures[0].level_ref

        messages = []
        total_routed = 0
        for system_classification in system_classifications:
            targets_diam = [
                f.primary_connector(system_classification).diameter_mm
                for f in fixtures if f.primary_connector(system_classification) is not None]
            trunk_diameter_mm = max(targets_diam) if targets_diam else 20.0

            result, message = run_water_supply_flow(
                doc, fixtures, system_classification, corridor_points, trunk_diameter_mm,
                level_id, pipe_type_name, valve_symbol=valve_symbol)
            if result is not None and result.value:
                total_routed += result.value.get("routed", 0)
            messages.append(u"{0}: {1}".format(system_classification, message))

        combined_message = u"\n".join(messages)
        wall_names = u", ".join(type_name(w) for w in confirmed_walls)
        combined_message = u"{0}\n\nCorridor followed: {1}".format(combined_message, wall_names)

        return total_routed, combined_message
    finally:
        room_clear_t = Transaction(doc, u"Clear room highlight")
        room_clear_t.Start()
        for room_info in picked_rooms:
            room_elem = doc.GetElement(room_info.ref)
            if room_elem is not None:
                highlight_room(doc, view, room_elem, clear=True)
        room_clear_t.Commit()
