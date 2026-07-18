# -*- coding: utf-8 -*-
"""Water Supply route: one room, connected straight walls, selected fixtures, picked
incoming-main and valve routing points, and an atomic
graph -> pipes -> fittings/connection pass.

The valve point remains the routing origin, and an optional Phase 4 accessory
pass can now split the valve-height feed pipe and place a selected Pipe
Accessory valve family inline.
"""

import clr

clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")

from Autodesk.Revit.DB import (
    BuiltInCategory, BuiltInParameter, FailureProcessingResult,
    FailureSeverity, FilteredElementCollector, FamilySymbol, IFailuresPreprocessor,
    Transaction, TransactionStatus)
from Autodesk.Revit.DB.Plumbing import Pipe
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
from pyrevit import forms

from bkbim.app.commands import generate_water_supply_command
from bkbim.domain.geometry.units import ft_to_mm
from bkbim.domain.mep.models.connector_info import ConnectorInfo
from bkbim.domain.mep.routing.water_supply_feed import (
    corridor_offset_vector as _corridor_offset_vector,
    feed_points_from_main_to_trunk as _feed_points_from_main_to_trunk,
    offset_corridor_points as _offset_corridor_points,
    offset_point_xy as _offset_point_xy,
    offset_point_z as _offset_point_z,
)
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.mep.accessory_placement_writer import AccessoryPlacementWriter
from bkbim.revit.adapter.mep.fitting_generation_writer import FittingGenerationWriter
from bkbim.revit.adapter.mep.fixture_reader import RevitFixtureReader
from bkbim.revit.adapter.mep.nearby_wall_finder import find_nearest_walls_for_fixtures
from bkbim.revit.adapter.mep.pipe_geometry_writer import PipeGeometryWriter
from bkbim.revit.adapter.mep.room_highlight import highlight_room
from bkbim.revit.adapter.mep.room_reader import RevitRoomReader
from bkbim.revit.adapter.mep.room_selection_prompt import pick_rooms
from bkbim.revit.adapter.mep.selection_retry import ask_retry_selection
from bkbim.revit.adapter.mep.sanitary_drainage_flow import (
    resolve_piping_system_type_id, resolve_pipe_type_id_by_name)
from bkbim.revit.adapter.mep.wall_confirmation_prompt import confirm_walls, highlight_walls
from bkbim.revit.adapter.mep.wall_corridor import corridor_points_from_connected_walls
from bkbim.revit.adapter.stable_representation import element_id_token
from bkbim.ui.views.water_supply_options import (
    show_water_supply_fixture_selection,
    show_water_supply_routing_options)

_TITLE = u"Route Cold Water"

COLD_WATER = u"DomesticColdWater"
HOT_WATER = u"DomesticHotWater"
_SYSTEM_DISPLAY_NAMES = {
    COLD_WATER: u"Cold Water",
    HOT_WATER: u"Hot Water",
}
_PIPE_SYSTEM_NAMES = {
    COLD_WATER: u"Domestic Cold Water",
    HOT_WATER: u"Domestic Hot Water",
}
_COLD_ALLOWED_FLOWS = (
    ConnectorInfo.FLOW_IN, ConnectorInfo.FLOW_BIDIRECTIONAL)
_TRUNK_MODE_CEILING = u"In the ceiling"
_TRUNK_MODE_FLOOR = u"Through the floor"
_TRUNK_MODE_WALL = u"In the walls"
_TRUNK_MODE_CHOICES = (
    _TRUNK_MODE_CEILING,
    _TRUNK_MODE_FLOOR,
    _TRUNK_MODE_WALL,
)
_SOURCE_MODE_POINT = u"Click incoming main point"
_SOURCE_MODE_PIPE = u"Select existing main pipe"
_SOURCE_MODE_CHOICES = (
    _SOURCE_MODE_POINT,
    _SOURCE_MODE_PIPE,
)
_FEED_MODE_WALLS = u"Follow selected walls"
_NO_VALVE_FAMILY = u"No valve family - route pipe only"
_VALVE_PICK_CANCELLED = object()


class _MepRouteFailurePolicy(IFailuresPreprocessor):
    """Prevent Revit's modal failure dialog from trapping this command.

    Required MEP errors are not ignored; they roll back the active
    transaction and are reported in the command result instead.
    """
    def __init__(self):
        self.errors = []
        self.warnings = []

    def PreprocessFailures(self, failures_accessor):
        has_error = False
        for failure in failures_accessor.GetFailureMessages():
            try:
                description = failure.GetDescriptionText()
                severity = failure.GetSeverity()
                if severity == FailureSeverity.Warning:
                    self.warnings.append(description)
                    failures_accessor.DeleteWarning(failure)
                elif severity == FailureSeverity.Error:
                    has_error = True
                    self.errors.append(description)
            except Exception:
                has_error = True
        if has_error:
            return FailureProcessingResult.ProceedWithRollBack
        return FailureProcessingResult.Continue


def _attach_mep_failure_policy(transaction):
    failure_policy = _MepRouteFailurePolicy()
    opts = transaction.GetFailureHandlingOptions()
    opts.SetFailuresPreprocessor(failure_policy)
    try:
        opts.SetClearAfterRollback(True)
    except Exception:
        pass
    transaction.SetFailureHandlingOptions(opts)
    return failure_policy


def _route_title(system_classification):
    return u"Route {0}".format(_system_display_name(system_classification))


def _system_display_name(system_classification):
    return _SYSTEM_DISPLAY_NAMES.get(system_classification, system_classification)


def _pipe_system_name(system_classification):
    return _PIPE_SYSTEM_NAMES.get(system_classification)


class _PipeOnlyFilter(ISelectionFilter):
    def AllowElement(self, element):
        try:
            category = element.Category
            return category.BuiltInCategory == BuiltInCategory.OST_PipeCurves
        except Exception:
            return isinstance(element, Pipe)

    def AllowReference(self, reference, point):
        return False


def _supply_connectors(fixture, system_classification):
    return fixture.matching_connectors(
        system_classification, allowed_flow_directions=_COLD_ALLOWED_FLOWS)


def _connector_is_connected(connector):
    try:
        return bool(connector.ref.IsConnected)
    except Exception:
        return False


def _coordination_vertical_offset(system_classification, lateral_offset_mm):
    """Hot Water is coordinated both beside and above Cold Water.

    The lateral sign is only a side choice; vertical separation is always
    positive so a user can flip sides without accidentally moving Hot Water
    down into the Cold Water run.
    """
    if system_classification != HOT_WATER:
        return 0.0
    return abs(lateral_offset_mm)


def _pick_parallel_offset(system_classification, standard, title):
    if system_classification != HOT_WATER:
        return 0.0
    offset = _ask_number_mm(
        u"Hot Water offset from Cold Water / wall corridor (mm). Use a negative value to flip side.",
        getattr(standard, "mep_hot_cold_spacing_mm", 50.0),
        title=title,
        allow_zero=True)
    if offset is not None and abs(offset) < 1.0:
        forms.alert(
            u"Hot Water offset must not be 0 mm, otherwise hot and cold "
            u"pipes can overlap at the same elevation.",
            title=title)
        return None
    return offset


def _ask_number_mm(prompt, default_mm, title=_TITLE, allow_zero=True):
    raw = forms.ask_for_string(
        default=u"{0:g}".format(float(default_mm)),
        prompt=prompt,
        title=title)
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        forms.alert(u"Enter a valid number in millimetres.", title=title)
        return None
    if not allow_zero and value <= 0:
        forms.alert(u"Enter a value greater than 0 mm.", title=title)
        return None
    return value


def _pick_plan_point(uidoc, prompt, level_elevation_mm, height_above_level_mm,
                     title=_TITLE):
    while True:
        try:
            picked = uidoc.Selection.PickPoint(prompt)
            break
        except Exception:
            if not ask_retry_selection(title):
                return None
    return (
        ft_to_mm(picked.X),
        ft_to_mm(picked.Y),
        level_elevation_mm + height_above_level_mm)


def _project_point_to_pipe_mm(pipe, picked_xyz):
    curve = pipe.Location.Curve
    try:
        projection = curve.Project(picked_xyz)
        xyz = projection.XYZPoint
    except Exception:
        xyz = picked_xyz
    return (ft_to_mm(xyz.X), ft_to_mm(xyz.Y), ft_to_mm(xyz.Z))


def _pipe_diameter_mm(pipe):
    try:
        param = pipe.get_Parameter(BuiltInParameter.RBS_PIPE_DIAMETER_PARAM)
        if param is None:
            return None
        value = param.AsDouble()
        if value <= 0:
            return None
        return ft_to_mm(value)
    except Exception:
        return None


def _pick_source_pipe(uidoc, doc, title=_TITLE):
    while True:
        try:
            picked_ref = uidoc.Selection.PickObject(
                ObjectType.Element, _PipeOnlyFilter(),
                u"{0}: select existing main pipe".format(title))
            break
        except Exception:
            if not ask_retry_selection(title):
                return None
    pipe = doc.GetElement(picked_ref.ElementId)
    if pipe is None:
        return None

    while True:
        try:
            picked_point = uidoc.Selection.PickPoint(
                u"{0}: click tie-in point on selected pipe".format(title))
            break
        except Exception:
            if not ask_retry_selection(title):
                return None

    source_point = _project_point_to_pipe_mm(pipe, picked_point)
    return {
        "pipe": pipe,
        "point": source_point,
        "diameter_mm": _pipe_diameter_mm(pipe),
    }


def _pick_routing_layout(uidoc, level_elevation_mm, settings, title=_TITLE):
    source_mode = settings.source_mode
    source_pipe = None
    source_diameter_mm = None
    if source_mode == _SOURCE_MODE_PIPE:
        source_info = _pick_source_pipe(uidoc, uidoc.Document, title=title)
        if source_info is None:
            return None
        incoming_point = source_info["point"]
        incoming_height = incoming_point[2] - level_elevation_mm
        source_pipe = source_info["pipe"]
        source_diameter_mm = source_info["diameter_mm"]
    else:
        incoming_height = settings.incoming_height_mm
        incoming_point = _pick_plan_point(
            uidoc,
            u"Click the incoming water-main position in plan.",
            level_elevation_mm,
            incoming_height,
            title=title)
        if incoming_point is None:
            return None

    valve_height = settings.valve_height_mm
    valve_point = _pick_plan_point(
        uidoc,
        u"Click the valve position in plan. This is the post-valve routing origin.",
        level_elevation_mm,
        valve_height,
        title=title)
    if valve_point is None:
        return None

    mode = settings.trunk_mode
    if mode == _TRUNK_MODE_CEILING:
        trunk_z = (
            level_elevation_mm +
            settings.ceiling_height_mm +
            abs(settings.ceiling_offset_mm))
    elif mode == _TRUNK_MODE_FLOOR:
        trunk_z = level_elevation_mm - abs(settings.floor_offset_mm)
    else:
        trunk_z = level_elevation_mm + settings.wall_trunk_height_mm

    return {
        "mode": mode,
        "feed_mode": _FEED_MODE_WALLS,
        "source_mode": source_mode,
        "incoming_height_mm": incoming_height,
        "valve_height_mm": valve_height,
        "incoming_point": incoming_point,
        "valve_point": valve_point,
        "trunk_z_mm": trunk_z,
        "source_pipe": source_pipe,
        "source_diameter_mm": source_diameter_mm,
    }


def _valve_options(doc):
    options = [(_NO_VALVE_FAMILY, None)]
    for symbol in _pipe_accessory_symbols(doc):
        label = u"{0}  [id {1}]".format(
            type_name(symbol), element_id_token(symbol.Id))
        options.append((label, symbol))
    return options


def _pick_routing_settings(doc, standard, minimum_trunk_diameter_mm,
                           system_classification, title):
    default_hot_offset_mm = None
    if system_classification == HOT_WATER:
        default_hot_offset_mm = getattr(
            standard, "mep_hot_cold_spacing_mm", 50.0)
    return show_water_supply_routing_options(
        title=title,
        system_display_name=_system_display_name(system_classification),
        source_modes=_SOURCE_MODE_CHOICES,
        trunk_modes=_TRUNK_MODE_CHOICES,
        valve_options=_valve_options(doc),
        default_incoming_height_mm=standard.mep_valve_height_mm,
        default_valve_height_mm=standard.mep_valve_height_mm,
        default_trunk_diameter_mm=minimum_trunk_diameter_mm,
        minimum_trunk_diameter_mm=minimum_trunk_diameter_mm,
        default_hot_offset_mm=default_hot_offset_mm)


def _pick_fixtures(fixtures, system_classification):
    display_name = _system_display_name(system_classification)
    by_label = {}
    for fixture in fixtures:
        label = _fixture_label(fixture)
        by_label[label] = fixture
    picked = forms.SelectFromList.show(
        sorted(by_label.keys()),
        title=u"Pick the fixtures to connect to {0}".format(display_name),
        multiselect=True)
    if not picked:
        return None
    return [by_label[label] for label in picked]


def _fixture_label(fixture):
    return u"{0} : {1}  [id {2}]".format(
        fixture.family_name, fixture.type_name,
        element_id_token(fixture.ref))


def _fixture_limit_list(fixtures, limit=8):
    labels = [_fixture_label(fixture) for fixture in fixtures[:limit]]
    if len(fixtures) > limit:
        labels.append(u"...and {0} more".format(len(fixtures) - limit))
    return labels


def _show_fixture_eligibility_summary(title, display_name, total, eligible,
                                      missing, ambiguous, connected):
    if not (missing or ambiguous or connected):
        return
    message = (
        u"Found {0} plumbing fixture(s) in the selected room.\n"
        u"{1} fixture(s) are eligible for {2} and will be shown next.\n\n"
        u"Skipped:\n"
        u"- Missing {2} inlet: {3}\n"
        u"- More than one {2} inlet: {4}\n"
        u"- Already connected: {5}".format(
            total, eligible, display_name,
            len(missing), len(ambiguous), len(connected)))
    details = []
    if missing:
        details.append(
            u"Missing {0} inlet:\n- {1}".format(
                display_name, u"\n- ".join(_fixture_limit_list(missing))))
    if ambiguous:
        details.append(
            u"Ambiguous {0} inlet:\n- {1}".format(
                display_name, u"\n- ".join(_fixture_limit_list(ambiguous))))
    if connected:
        details.append(
            u"Already connected:\n- {0}".format(
                u"\n- ".join(_fixture_limit_list(connected))))
    if details:
        message += u"\n\n" + u"\n\n".join(details)
    message += (
        u"\n\nNote: a fixture can look like a water fixture but still be "
        u"skipped if its family connector is authored as another Revit system "
        u"type, such as Sanitary.")
    forms.alert(message, title=title)


def _room_label(room):
    return u"{0} - {1}".format(room.number, room.name)


def _classify_room_fixtures(fixtures, system_classification):
    eligible = []
    missing = []
    ambiguous = []
    connected = []
    for fixture in fixtures:
        matches = _supply_connectors(fixture, system_classification)
        if not matches:
            missing.append(fixture)
        elif len(matches) > 1:
            ambiguous.append(fixture)
        elif _connector_is_connected(matches[0]):
            connected.append(fixture)
        else:
            eligible.append(fixture)
    return eligible, missing, ambiguous, connected


def _fixture_selection_entries(rooms, fixtures, system_classification):
    fixtures_by_room = {}
    for fixture in fixtures:
        key = element_id_token(fixture.room_ref) if fixture.room_ref is not None else None
        fixtures_by_room.setdefault(key, []).append(fixture)

    entries = []
    for room in rooms:
        key = element_id_token(room.ref)
        room_fixtures = fixtures_by_room.get(key, [])
        eligible, missing, ambiguous, connected = _classify_room_fixtures(
            room_fixtures, system_classification)
        entries.append({
            "label": u"{0}  ({1} eligible / {2} total)".format(
                _room_label(room), len(eligible), len(room_fixtures)),
            "room": room,
            "total": len(room_fixtures),
            "eligible": eligible,
            "missing": missing,
            "ambiguous": ambiguous,
            "connected": connected,
            "fixture_label_fn": _fixture_label,
        })
    return entries


def _pick_trunk_diameter(minimum_mm, source_diameter_mm=None,
                         system_classification=COLD_WATER, title=_TITLE):
    display_name = _system_display_name(system_classification)
    default_diameter_mm = source_diameter_mm or minimum_mm
    raw = forms.ask_for_string(
        default=u"{0:g}".format(float(default_diameter_mm)),
        prompt=u"{0} trunk diameter (mm)".format(display_name),
        title=title)
    if raw is None:
        return None
    try:
        diameter = float(raw)
    except (TypeError, ValueError):
        diameter = 0.0
    if diameter <= 0:
        forms.alert(
            u"Enter a trunk diameter greater than 0 mm.", title=title)
        return None
    if diameter < minimum_mm:
        forms.alert(
            u"The trunk must be at least {0:g} mm, the largest selected "
            u"fixture connector. Smaller trunks would require reducers, "
            u"which this slice does not support.".format(float(minimum_mm)),
            title=title)
        return None
    if (source_diameter_mm is not None and
            abs(diameter - source_diameter_mm) > 0.5):
        forms.alert(
            u"The trunk must match the selected source outlet ({0:g} mm). "
            u"This slice does not place source reducers.".format(
                float(source_diameter_mm)), title=title)
        return None
    return diameter


def _pipe_accessory_symbols(doc):
    try:
        symbols = list(
            FilteredElementCollector(doc)
            .OfClass(FamilySymbol)
            .OfCategory(BuiltInCategory.OST_PipeAccessory)
            .ToElements())
    except Exception:
        symbols = []
    return sorted(symbols, key=lambda symbol: type_name(symbol))


def _pick_valve_symbol(doc, system_classification=COLD_WATER, title=_TITLE):
    display_name = _system_display_name(system_classification)
    symbols = _pipe_accessory_symbols(doc)
    if not symbols:
        forms.alert(
            u"No Pipe Accessory family types were found in this project.\n\n"
            u"The route can still be created, but no physical valve family "
            u"can be inserted until a valve family/type is loaded.",
            title=title)
        return None

    labels = [_NO_VALVE_FAMILY]
    by_label = {_NO_VALVE_FAMILY: None}
    for symbol in symbols:
        label = u"{0}  [id {1}]".format(type_name(symbol), element_id_token(symbol.Id))
        labels.append(label)
        by_label[label] = symbol

    picked = forms.SelectFromList.show(
        labels,
        title=u"{0} valve family/type".format(display_name),
        multiselect=False)
    if not picked:
        return _VALVE_PICK_CANCELLED
    return by_label.get(picked)


def _created_segments(system_classification, geo_value, trunk_diameter_mm):
    display_name = _system_display_name(system_classification)
    segments = []
    for index, entry in enumerate(geo_value.get("feed_entries", [])):
        start, end, _pipe = entry
        segments.append({
            "system": display_name,
            "kind": u"feed",
            "label": u"feed segment {0}".format(index + 1),
            "start": start,
            "end": end,
            "diameter_mm": trunk_diameter_mm,
        })
    for index, entry in enumerate(geo_value.get("trunk_entries", [])):
        start, end, _pipe = entry
        segments.append({
            "system": display_name,
            "kind": u"trunk",
            "label": u"trunk segment {0}".format(index + 1),
            "start": start,
            "end": end,
            "diameter_mm": trunk_diameter_mm,
        })
    for index, entry in enumerate(geo_value.get("branch_entries", [])):
        start, end, _pipe, target_label, diameter_mm = entry
        segments.append({
            "system": display_name,
            "kind": u"branch",
            "label": u"branch segment {0} to {1}".format(index + 1, target_label),
            "start": start,
            "end": end,
            "diameter_mm": diameter_mm,
        })
    return segments


def run_water_supply_flow(doc, fixtures, system_classification, corridor_points,
                           trunk_diameter_mm, level_id, pipe_type_name,
                           wall_penetration_mm=80.0, max_branch_length_mm=None,
                           source_connector=None, feed_points=None,
                           source_pipe=None, source_point=None,
                           valve_symbol=None, valve_point=None, title=None):
    """Runs graph, geometry and fittings for one Water Supply system.

    Any required pipe, fitting or connector failure rolls back the complete
    route. Partial plumbing systems are not a successful outcome.

    Returns (result, message) - result is None if a required project element
    couldn't be resolved.
    """
    title = title or _route_title(system_classification)
    pipe_system_name = _pipe_system_name(system_classification)
    if pipe_system_name is None:
        return None, u"Unsupported Water Supply system: {0}".format(
            system_classification)

    system_type_id = resolve_piping_system_type_id(doc, pipe_system_name)
    if system_type_id is None:
        return None, u"No '{0}' Piping System Type found in this project.".format(
            pipe_system_name)

    pipe_type_id = resolve_pipe_type_id_by_name(doc, pipe_type_name)
    if pipe_type_id is None:
        return None, u"Pipe type '{0}' not found in this project.".format(pipe_type_name)

    t = Transaction(doc, title)
    t.Start()
    failure_policy = _attach_mep_failure_policy(t)
    try:
        cmd_result = generate_water_supply_command.run(
            fixtures, system_classification, corridor_points,
            wall_penetration_mm=wall_penetration_mm,
            max_branch_length_mm=max_branch_length_mm)
        if not cmd_result.success:
            t.RollBack()
            return cmd_result, cmd_result.message

        graph = cmd_result.value["graph"]

        geometry_writer = PipeGeometryWriter(doc, system_type_id, pipe_type_id, level_id)
        geo_result = geometry_writer.write(
            graph, trunk_diameter_mm, feed_points=feed_points,
            feed_diameter_mm=trunk_diameter_mm)
        if not geo_result.success:
            t.RollBack()
            return geo_result, geo_result.message
        created_segments = _created_segments(
            system_classification, geo_result.value, trunk_diameter_mm)

        fitting_writer = FittingGenerationWriter(doc)
        fit_result = fitting_writer.write(
            graph, geo_result.value["trunk_pipes"], geo_result.value["branch_pipes"],
            source_connector=source_connector,
            feed_pipes=geo_result.value.get("feed_pipes", []),
            source_pipe=source_pipe, source_point=source_point)
        if not fit_result.success:
            t.RollBack()
            message = fit_result.message
            if fit_result.diagnostics:
                message += u"\n\nDetails:\n- " + u"\n- ".join(fit_result.diagnostics)
            return fit_result, message
        valve_placed = False
        valve_type_name = None
        if valve_symbol is not None:
            accessory_result = AccessoryPlacementWriter(doc).place_inline_valve(
                valve_symbol, valve_point, geo_result.value.get("feed_entries", []))
            if not accessory_result.success:
                t.RollBack()
                message = accessory_result.message
                if accessory_result.diagnostics:
                    message += u"\n\nDetails:\n- " + u"\n- ".join(accessory_result.diagnostics)
                return accessory_result, message
            valve_placed = True
            valve_type_name = type_name(valve_symbol)
        cmd_result.value["created_pipe_segments"] = created_segments
        cmd_result.value["valve_placed"] = valve_placed
        cmd_result.value["valve_type_name"] = valve_type_name
    except Exception as e:
        t.RollBack()
        return None, u"Error:\n{0}".format(str(e))

    status = t.Commit()
    if status != TransactionStatus.Committed:
        message = u"Revit rejected the MEP route and rolled it back."
        if failure_policy.errors:
            message += u"\n\nDetails:\n- " + u"\n- ".join(failure_policy.errors)
        return None, message

    message = (
        u"{0} fixture(s) routed and connected. {1} tee(s), {2} elbow(s), "
        u"{3} fixture connection(s), {4} direct trunk/feed connection(s), "
        u"{5} source/feed connection(s).".format(
            cmd_result.value["routed"], fit_result.value["tees_created"],
            fit_result.value["elbows_created"],
            fit_result.value["fixture_connections_made"],
            fit_result.value["connections_made"],
            fit_result.value["source_connections_made"]))
    warnings = cmd_result.value.get("warnings", [])
    if warnings:
        message += u"\n\nWarnings:\n- " + u"\n- ".join(warnings)
    if cmd_result.value.get("valve_placed"):
        message += u"\n\nValve placed: {0}.".format(
            cmd_result.value.get("valve_type_name") or u"selected valve")

    return cmd_result, message


def run_wizard(uidoc, doc, standard, pipe_type_name,
               system_classification=COLD_WATER):
    """Approved Water Supply slice.

    Returns (routed_count, message). ``routed_count`` is None if the user
    cancelled at any step (normal, not an error).
    """
    title = _route_title(system_classification)
    display_name = _system_display_name(system_classification)
    view = doc.ActiveView

    rooms = RevitRoomReader(doc).read_rooms()
    if not rooms:
        return None, u"No rooms found in this project."

    all_fixtures = RevitFixtureReader(doc).read_fixtures()
    selection_entries = _fixture_selection_entries(
        rooms, all_fixtures, system_classification)
    selection = show_water_supply_fixture_selection(
        title, display_name, selection_entries)
    if selection is None:
        return None, None
    picked_rooms = [selection.room]
    selected_fixtures = selection.fixtures

    highlight_t = Transaction(doc, u"Highlight selected rooms")
    highlight_t.Start()
    for room_info in picked_rooms:
        room_elem = doc.GetElement(room_info.ref)
        if room_elem is not None:
            highlight_room(doc, view, room_elem)
    highlight_t.Commit()

    try:
        # This slice is explicitly one selected room, so the room's level is
        # authoritative. Hosted fixture families often expose InvalidElementId
        # from FamilyInstance.LevelId even though they are inside this room.
        level_id = picked_rooms[0].level_ref
        level = doc.GetElement(level_id)
        if level is None:
            forms.alert(
                u"The selected fixtures do not have a usable Revit level.",
                title=title)
            return None, None

        wall_map = find_nearest_walls_for_fixtures(
            doc, selected_fixtures,
            system_classification=system_classification,
            allowed_flow_directions=_COLD_ALLOWED_FLOWS)
        candidate_walls = []
        seen_ids = set()
        for fixture in selected_fixtures:
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

        confirmed_walls = []
        try:
            confirmed_walls = confirm_walls(uidoc, doc, candidate_walls, title=title)
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
                u"No wall was confirmed, so no {0} route was created.".format(
                    display_name),
                title=title)
            return None, None
        level_elevation_mm = ft_to_mm(level.Elevation)
        selected_connectors = [
            _supply_connectors(fixture, system_classification)[0]
            for fixture in selected_fixtures]
        default_trunk_diameter_mm = max(
            connector.diameter_mm for connector in selected_connectors)
        settings = _pick_routing_settings(
            doc, standard, default_trunk_diameter_mm,
            system_classification, title)
        if settings is None:
            return None, None

        layout = _pick_routing_layout(uidoc, level_elevation_mm, settings,
                                      title=title)
        if layout is None:
            return None, None
        trunk_diameter_mm = settings.trunk_diameter_mm
        if (layout["source_diameter_mm"] is not None and
                abs(trunk_diameter_mm - layout["source_diameter_mm"]) > 0.5):
            forms.alert(
                u"The trunk diameter in the settings window ({0:g} mm) must "
                u"match the selected source pipe ({1:g} mm). This slice does "
                u"not place source reducers yet.".format(
                    float(trunk_diameter_mm),
                    float(layout["source_diameter_mm"])),
                title=title)
            return None, None

        parallel_offset_mm = settings.parallel_offset_mm
        vertical_offset_mm = _coordination_vertical_offset(
            system_classification, parallel_offset_mm)
        route_incoming_point = layout["incoming_point"]
        route_valve_point = layout["valve_point"]
        route_trunk_z_mm = layout["trunk_z_mm"] + vertical_offset_mm
        if vertical_offset_mm:
            route_valve_point = _offset_point_z(
                route_valve_point, vertical_offset_mm)
            # A clicked point source is only a routing origin, so Hot Water can
            # be coordinated vertically from the first generated feed segment.
            # A selected existing pipe source must remain on the real pipe for
            # the connector/split tee pass to work.
            if layout["source_pipe"] is None:
                route_incoming_point = _offset_point_z(
                    route_incoming_point, vertical_offset_mm)
        origin_mm = (
            route_valve_point[0],
            route_valve_point[1],
            route_trunk_z_mm)

        horizontal_z_mm = route_trunk_z_mm
        target_points = [
            connector.position for connector in selected_connectors]
        try:
            corridor_points = corridor_points_from_connected_walls(
                confirmed_walls, horizontal_z_mm, origin_mm, target_points)
        except ValueError as e:
            forms.alert(str(e), title=title)
            return None, None
        offset_xy = _corridor_offset_vector(
            corridor_points, parallel_offset_mm)
        if system_classification == HOT_WATER:
            route_valve_point = _offset_point_xy(route_valve_point, offset_xy)
            if layout["source_pipe"] is None:
                # A clicked source is a routing point, so it should move with
                # the coordinated Hot Water main. A selected source pipe is a
                # real model element and must remain anchored at its true
                # tie-in point.
                route_incoming_point = _offset_point_xy(
                    route_incoming_point, offset_xy)
        corridor_points = _offset_corridor_points(
            corridor_points, parallel_offset_mm)
        feed_points = _feed_points_from_main_to_trunk(
            route_incoming_point, route_valve_point, corridor_points[0],
            trunk_next_point=(corridor_points[1] if len(corridor_points) > 1 else None))
        valve_symbol = settings.valve_symbol

        result, message = run_water_supply_flow(
            doc, selected_fixtures, system_classification, corridor_points,
            trunk_diameter_mm, level_id, pipe_type_name,
            wall_penetration_mm=standard.mep_wall_penetration_mm,
            max_branch_length_mm=standard.mep_max_branch_length_mm,
            feed_points=feed_points,
            source_pipe=layout["source_pipe"],
            source_point=layout["incoming_point"] if layout["source_pipe"] is not None else None,
            valve_symbol=valve_symbol,
            valve_point=route_valve_point,
            title=title)
        if result is None or not result.success:
            return 0, message

        if valve_symbol is None:
            valve_note = (
                u"Valve: no valve family selected; the valve remains a "
                u"routing point only.")
        else:
            valve_note = u"Valve: placed {0} inline on the valve feed segment.".format(
                type_name(valve_symbol))
        message = (
            u"{0}\n\nRouting mode: {1}\n"
            u"Feed route: {2}\n"
            u"Incoming/source: {3}\n"
            u"Incoming main height: {4:g} mm above level\n"
            u"Valve height: {5:g} mm above level\n"
            u"Trunk elevation: {6:g} mm above level\n"
            u"Parallel offset: {7:g} mm\n"
            u"Vertical offset: {8:g} mm\n"
            u"Corridor wall(s): {9}\n\n{10}".format(
                message, layout["mode"], layout["feed_mode"],
                layout["source_mode"],
                float(route_incoming_point[2] - level_elevation_mm),
                float(layout["valve_height_mm"] + vertical_offset_mm),
                float(route_trunk_z_mm - level_elevation_mm),
                float(parallel_offset_mm),
                float(vertical_offset_mm),
                u", ".join(type_name(wall) for wall in confirmed_walls),
                valve_note))
        return result.value.get("routed", 0), message
    finally:
        room_clear_t = Transaction(doc, u"Clear room highlight")
        room_clear_t.Start()
        for room_info in picked_rooms:
            room_elem = doc.GetElement(room_info.ref)
            if room_elem is not None:
                highlight_room(doc, view, room_elem, clear=True)
        room_clear_t.Commit()
