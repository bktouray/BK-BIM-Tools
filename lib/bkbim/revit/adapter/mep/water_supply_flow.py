# -*- coding: utf-8 -*-
"""Water Supply route: one room, connected straight walls, selected fixtures, picked
incoming-main and valve routing points, and an atomic
graph -> pipes -> fittings/connection pass.

The valve is currently a routing break/position, not an automatically placed
family instance. Automatic valve placement, automatic obstacle avoidance and
a sizing engine remain deferred.
"""

import clr

clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")

from Autodesk.Revit.DB import (
    BuiltInCategory, BuiltInParameter, FailureProcessingResult,
    FailureSeverity, IFailuresPreprocessor,
    Transaction, TransactionStatus)
from Autodesk.Revit.DB.Plumbing import Pipe
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
from pyrevit import forms

from bkbim.app.commands import generate_water_supply_command
from bkbim.domain.geometry.units import ft_to_mm
from bkbim.domain.mep.models.connector_info import ConnectorInfo
from bkbim.revit.adapter.element_naming import type_name
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
from bkbim.revit.adapter.mep.wall_corridor import corridor_points_from_connected_walls
from bkbim.revit.adapter.stable_representation import element_id_token

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
_MIN_FEED_SEGMENT_MM = 10.0
_VALVE_BYPASS_HALF_LENGTH_MM = 250.0


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


def _distance_mm(point_a, point_b):
    return sum(
        (point_b[index] - point_a[index]) ** 2
        for index in range(3)) ** 0.5


def _horizontal_distance_mm(point_a, point_b):
    return (
        (point_b[0] - point_a[0]) ** 2 +
        (point_b[1] - point_a[1]) ** 2) ** 0.5


def _offset_corridor_points(corridor_points, offset_mm):
    if not corridor_points or abs(offset_mm) < 0.001:
        return corridor_points
    first = corridor_points[0]
    second = None
    for point in corridor_points[1:]:
        if _horizontal_distance_mm(first, point) > _MIN_FEED_SEGMENT_MM:
            second = point
            break
    if second is None:
        return corridor_points
    dx = second[0] - first[0]
    dy = second[1] - first[1]
    length = (dx * dx + dy * dy) ** 0.5
    if length <= 0:
        return corridor_points
    normal_x = -dy / length
    normal_y = dx / length
    return [
        (point[0] + normal_x * offset_mm,
         point[1] + normal_y * offset_mm,
         point[2])
        for point in corridor_points
    ]


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
    forms.alert(prompt, title=title)
    try:
        picked = uidoc.Selection.PickPoint(prompt)
    except Exception:
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
    forms.alert(
        u"Select the existing water main pipe to tie into.",
        title=title)
    try:
        picked_ref = uidoc.Selection.PickObject(
            ObjectType.Element, _PipeOnlyFilter(),
            u"{0}: select existing main pipe".format(title))
    except Exception:
        return None
    pipe = doc.GetElement(picked_ref.ElementId)
    if pipe is None:
        return None

    forms.alert(
        u"Click the tie-in point on or near the selected main pipe.",
        title=title)
    try:
        picked_point = uidoc.Selection.PickPoint(
            u"{0}: click tie-in point on selected pipe".format(title))
    except Exception:
        return None

    source_point = _project_point_to_pipe_mm(pipe, picked_point)
    return {
        "pipe": pipe,
        "point": source_point,
        "diameter_mm": _pipe_diameter_mm(pipe),
    }


def _compact_points(points, min_length_mm=_MIN_FEED_SEGMENT_MM):
    compacted = []
    for point in points:
        if not compacted or _distance_mm(compacted[-1], point) >= min_length_mm:
            compacted.append(point)
    return compacted


def _trunk_aligned_approach_point(valve_point, trunk_origin_point,
                                  trunk_next_point=None):
    valve_x, valve_y, _valve_z = valve_point
    trunk_x, trunk_y, trunk_z = trunk_origin_point
    if trunk_next_point is None:
        return (trunk_x, valve_y, trunk_z)

    dx = abs(trunk_next_point[0] - trunk_x)
    dy = abs(trunk_next_point[1] - trunk_y)
    if dx >= dy:
        return (valve_x, trunk_y, trunk_z)
    return (trunk_x, valve_y, trunk_z)


def _valve_bypass_points(incoming_point, valve_point, trunk_z):
    """Creates a ceiling/main-to-valve-height bypass around the valve point.

    When both the incoming main and post-valve trunk are above the valve
    height, routing directly down to the valve point and then directly back
    up creates two opposing vertical pipes sharing the same endpoint. Revit's
    fitting solver can reject that stacked 180-degree condition. This shape
    drops before the valve, runs horizontally through the valve position, and
    rises after it, leaving a real horizontal pipe segment where the valve
    family will eventually be placed.
    """
    valve_x, valve_y, valve_z = valve_point
    incoming_z = incoming_point[2]
    if (incoming_z <= valve_z + _MIN_FEED_SEGMENT_MM or
            trunk_z <= valve_z + _MIN_FEED_SEGMENT_MM):
        return None

    delta_x = valve_x - incoming_point[0]
    delta_y = valve_y - incoming_point[1]
    use_y_axis = abs(delta_y) >= abs(delta_x)
    if use_y_axis:
        sign = 1.0 if delta_y >= 0 else -1.0
        available = abs(delta_y)
        half = min(_VALVE_BYPASS_HALF_LENGTH_MM, max(100.0, available / 3.0))
        pre = (valve_x, valve_y - sign * half, incoming_z)
        pre_low = (valve_x, valve_y - sign * half, valve_z)
        post_low = (valve_x, valve_y + sign * half, valve_z)
        post_high = (valve_x, valve_y + sign * half, trunk_z)
    else:
        sign = 1.0 if delta_x >= 0 else -1.0
        available = abs(delta_x)
        half = min(_VALVE_BYPASS_HALF_LENGTH_MM, max(100.0, available / 3.0))
        pre = (valve_x - sign * half, valve_y, incoming_z)
        pre_low = (valve_x - sign * half, valve_y, valve_z)
        post_low = (valve_x + sign * half, valve_y, valve_z)
        post_high = (valve_x + sign * half, valve_y, trunk_z)
    return pre, pre_low, post_low, post_high


def _feed_points_from_main_to_trunk(incoming_point, valve_point, trunk_origin_point,
                                    trunk_next_point=None):
    """Upstream route: water main -> valve point -> trunk.

    The valve point is preserved as a route break even though a real valve
    family is not placed yet. A later accessory pass can replace that plain
    generated connection with an actual valve component. The final point is
    the wall-projected trunk origin, not the raw valve click point; Revit
    fittings need those endpoints coincident.
    """
    valve_x, valve_y, _valve_z = valve_point
    _trunk_x, _trunk_y, trunk_z = trunk_origin_point
    approach_point = _trunk_aligned_approach_point(
        valve_point, trunk_origin_point, trunk_next_point)
    bypass = _valve_bypass_points(incoming_point, valve_point, trunk_z)
    if bypass is not None:
        pre, pre_low, post_low, post_high = bypass
        return _compact_points([
            incoming_point,
            (pre[0], incoming_point[1], incoming_point[2]),
            pre,
            pre_low,
            post_low,
            post_high,
            (valve_x, valve_y, trunk_z),
            approach_point,
            trunk_origin_point,
        ])

    points = [
        incoming_point,
        (valve_x, incoming_point[1], incoming_point[2]),
        (valve_x, valve_y, incoming_point[2]),
        valve_point,
        (valve_x, valve_y, trunk_z),
        approach_point,
        trunk_origin_point,
    ]
    return _compact_points(points)


def _pick_routing_layout(uidoc, level_elevation_mm, standard, title=_TITLE):
    source_mode = forms.CommandSwitchWindow.show(
        list(_SOURCE_MODE_CHOICES),
        message=u"Where is the incoming water main?")
    if not source_mode:
        return None

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
        incoming_height = _ask_number_mm(
            u"Incoming water main height above this level (mm)",
            standard.mep_valve_height_mm,
            title=title,
            allow_zero=True)
        if incoming_height is None:
            return None
        incoming_point = _pick_plan_point(
            uidoc,
            u"Click the incoming water-main position in plan.",
            level_elevation_mm,
            incoming_height,
            title=title)
        if incoming_point is None:
            return None

    valve_height = _ask_number_mm(
        u"Valve height above this level (mm)",
        standard.mep_valve_height_mm,
        title=title,
        allow_zero=True)
    if valve_height is None:
        return None
    valve_point = _pick_plan_point(
        uidoc,
        u"Click the valve position in plan. This is the post-valve routing origin.",
        level_elevation_mm,
        valve_height,
        title=title)
    if valve_point is None:
        return None

    mode = forms.CommandSwitchWindow.show(
        list(_TRUNK_MODE_CHOICES),
        message=u"Where should the main trunk run?")
    if not mode:
        return None

    if mode == _TRUNK_MODE_CEILING:
        ceiling_height = _ask_number_mm(
            u"Ceiling height above this level (mm)",
            2700.0,
            title=title,
            allow_zero=False)
        if ceiling_height is None:
            return None
        ceiling_offset = _ask_number_mm(
            u"Offset above that ceiling height (mm)",
            150.0,
            title=title,
            allow_zero=True)
        if ceiling_offset is None:
            return None
        trunk_z = level_elevation_mm + ceiling_height + abs(ceiling_offset)
    elif mode == _TRUNK_MODE_FLOOR:
        floor_offset = _ask_number_mm(
            u"Trunk offset below finish floor level (mm)",
            70.0,
            title=title,
            allow_zero=True)
        if floor_offset is None:
            return None
        trunk_z = level_elevation_mm - abs(floor_offset)
    else:
        wall_height = _ask_number_mm(
            u"In-wall trunk elevation above this level (mm)",
            valve_height,
            title=title,
            allow_zero=True)
        if wall_height is None:
            return None
        trunk_z = level_elevation_mm + wall_height

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


def _pick_fixtures(fixtures, system_classification):
    display_name = _system_display_name(system_classification)
    by_label = {}
    for fixture in fixtures:
        label = u"{0} : {1}  [id {2}]".format(
            fixture.family_name, fixture.type_name,
            element_id_token(fixture.ref))
        by_label[label] = fixture
    picked = forms.SelectFromList.show(
        sorted(by_label.keys()),
        title=u"Pick the fixtures to connect to {0}".format(display_name),
        multiselect=True)
    if not picked:
        return None
    return [by_label[label] for label in picked]


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


def run_water_supply_flow(doc, fixtures, system_classification, corridor_points,
                           trunk_diameter_mm, level_id, pipe_type_name,
                           wall_penetration_mm=80.0, max_branch_length_mm=None,
                           source_connector=None, feed_points=None,
                           source_pipe=None, source_point=None, title=None):
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

    picked_rooms = pick_rooms(rooms, title=title)
    if not picked_rooms:
        return None, None
    if len(picked_rooms) != 1:
        forms.alert(
            u"This first {0} slice routes one room at a time. "
            u"Select exactly one room.".format(display_name), title=title)
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
            forms.alert(
                u"No plumbing fixtures were found in the selected room.",
                title=title)
            return None, None

        eligible = []
        missing = 0
        ambiguous = 0
        connected = 0
        for fixture in fixtures:
            matches = _supply_connectors(fixture, system_classification)
            if not matches:
                missing += 1
            elif len(matches) > 1:
                ambiguous += 1
            elif _connector_is_connected(matches[0]):
                connected += 1
            else:
                eligible.append(fixture)

        if not eligible:
            forms.alert(
                u"No unconnected fixture with exactly one {0} inlet was "
                u"found in this room.\n\n"
                u"Missing inlet: {1}\nAmbiguous inlet: {2}\n"
                u"Already connected: {3}".format(
                    display_name, missing, ambiguous, connected),
                title=title)
            return None, None

        selected_fixtures = _pick_fixtures(eligible, system_classification)
        if not selected_fixtures:
            return None, None

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
        layout = _pick_routing_layout(uidoc, level_elevation_mm, standard,
                                      title=title)
        if layout is None:
            return None, None
        origin_mm = (
            layout["valve_point"][0],
            layout["valve_point"][1],
            layout["trunk_z_mm"])

        horizontal_z_mm = layout["trunk_z_mm"]
        selected_connectors = [
            _supply_connectors(fixture, system_classification)[0]
            for fixture in selected_fixtures]
        target_points = [
            connector.position for connector in selected_connectors]
        try:
            corridor_points = corridor_points_from_connected_walls(
                confirmed_walls, horizontal_z_mm, origin_mm, target_points)
        except ValueError as e:
            forms.alert(str(e), title=title)
            return None, None
        parallel_offset_mm = _pick_parallel_offset(
            system_classification, standard, title)
        if parallel_offset_mm is None:
            return None, None
        corridor_points = _offset_corridor_points(
            corridor_points, parallel_offset_mm)
        feed_points = _feed_points_from_main_to_trunk(
            layout["incoming_point"], layout["valve_point"], corridor_points[0],
            trunk_next_point=(corridor_points[1] if len(corridor_points) > 1 else None))

        default_trunk_diameter_mm = max(
            connector.diameter_mm for connector in selected_connectors)
        trunk_diameter_mm = _pick_trunk_diameter(
            default_trunk_diameter_mm,
            source_diameter_mm=layout["source_diameter_mm"],
            system_classification=system_classification,
            title=title)
        if trunk_diameter_mm is None:
            return None, None

        result, message = run_water_supply_flow(
            doc, selected_fixtures, system_classification, corridor_points,
            trunk_diameter_mm, level_id, pipe_type_name,
            wall_penetration_mm=standard.mep_wall_penetration_mm,
            max_branch_length_mm=standard.mep_max_branch_length_mm,
            feed_points=feed_points,
            source_pipe=layout["source_pipe"],
            source_point=layout["incoming_point"] if layout["source_pipe"] is not None else None,
            title=title)
        if result is None or not result.success:
            return 0, message

        valve_note = (
            u"Note: the valve is a routing point in this slice; no valve "
            u"family is placed yet.")
        message = (
            u"{0}\n\nRouting mode: {1}\n"
            u"Feed route: {2}\n"
            u"Incoming/source: {3}\n"
            u"Incoming main height: {4:g} mm above level\n"
            u"Valve height: {5:g} mm above level\n"
            u"Trunk elevation: {6:g} mm above level\n"
            u"Parallel offset: {7:g} mm\n"
            u"Corridor wall(s): {8}\n\n{9}".format(
                message, layout["mode"], layout["feed_mode"],
                layout["source_mode"],
                float(layout["incoming_height_mm"]),
                float(layout["valve_height_mm"]),
                float(layout["trunk_z_mm"] - level_elevation_mm),
                float(parallel_offset_mm),
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
