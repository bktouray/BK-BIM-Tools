# -*- coding: utf-8 -*-
"""Phase 4 (MEP_Routing_Playbook.md Sec 17): places real accessory family
instances.
A completely separate system from routing - the routing graph never depends
on this; this depends on the routing graph (and on Phase 2/3 geometry
already existing).

Live-verified 2026-07-10 against the real project: `doc.Create.NewFamilyInstance`
(the (XYZ, FamilySymbol, StructuralType) overload - there is no direct
Connector-based overload for this in the API, confirmed via reflection) at
the trunk's own origin point, then `Connector.ConnectTo` joining the valve's
own connector to the trunk's first pipe - worked first try.

The original origin-valve spike is retained for reference, but Water Supply
now uses ``place_inline_valve``: place a selected Pipe Accessory family on
the valve-height feed segment, split that pipe at the valve connector
locations, delete the middle pipe piece, and connect the two remaining pipe
ends to the valve.
"""

import clr
import math

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import Line, XYZ
from Autodesk.Revit.DB.Plumbing import PlumbingUtils
from Autodesk.Revit.DB.Structure import StructuralType

from bkbim.core.logging import get_logger
from bkbim.core.result import Result
from bkbim.domain.geometry.units import mm_to_ft

_logger = get_logger(u"bkbim.revit.adapter.mep.accessory_placement_writer")
_JOIN_TOLERANCE_FT = 5.0 / 304.8
_POINT_TOLERANCE_MM = 5.0
_MIN_BREAK_CLEARANCE_MM = 10.0


def _mm_to_xyz(point_mm):
    return XYZ(mm_to_ft(point_mm[0]), mm_to_ft(point_mm[1]), mm_to_ft(point_mm[2]))


def _xyz_to_mm(xyz):
    return (xyz.X * 304.8, xyz.Y * 304.8, xyz.Z * 304.8)


def _distance_mm(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def _dot_xy(point_mm, origin_mm, axis_xy):
    return ((point_mm[0] - origin_mm[0]) * axis_xy[0] +
            (point_mm[1] - origin_mm[1]) * axis_xy[1])


def _horizontal_axis(start_mm, end_mm):
    dx = end_mm[0] - start_mm[0]
    dy = end_mm[1] - start_mm[1]
    length = (dx ** 2 + dy ** 2) ** 0.5
    if length < _MIN_BREAK_CLEARANCE_MM:
        return None
    return (dx / length, dy / length, length)


def _point_on_segment_mm(point_mm, start_mm, end_mm, tolerance_mm=_POINT_TOLERANCE_MM):
    if abs(point_mm[2] - start_mm[2]) > tolerance_mm:
        return False
    if abs(point_mm[2] - end_mm[2]) > tolerance_mm:
        return False
    axis = _horizontal_axis(start_mm, end_mm)
    if axis is None:
        return False
    ux, uy, length = axis
    t = _dot_xy(point_mm, start_mm, (ux, uy))
    if t < -tolerance_mm or t > length + tolerance_mm:
        return False
    projected = (start_mm[0] + ux * t, start_mm[1] + uy * t, start_mm[2])
    return _distance_mm(point_mm, projected) <= tolerance_mm


def _point_on_pipe_curve(pipe, xyz, tolerance_ft=_JOIN_TOLERANCE_FT):
    try:
        curve = pipe.Location.Curve
        projection = curve.Project(xyz)
        if projection is None:
            return False
        return projection.XYZPoint.DistanceTo(xyz) <= tolerance_ft
    except Exception:
        return False


def _connector_near(pipe, xyz, tolerance_ft=_JOIN_TOLERANCE_FT):
    if pipe is None:
        return None
    try:
        for c in pipe.ConnectorManager.Connectors:
            if c.Origin.DistanceTo(xyz) < tolerance_ft:
                return c
    except Exception:
        pass
    return None


def _piping_connectors(owner):
    connectors = []
    manager = None
    try:
        manager = owner.ConnectorManager
    except Exception:
        pass
    if manager is None:
        try:
            manager = owner.MEPModel.ConnectorManager
        except Exception:
            manager = None
    if manager is None:
        return connectors
    try:
        for connector in manager.Connectors:
            try:
                domain = str(connector.Domain).lower()
                if u"piping" in domain or u"pipe" in domain:
                    connectors.append(connector)
            except Exception:
                connectors.append(connector)
    except Exception:
        pass
    return connectors


def _farthest_connector_pair(connectors):
    best_pair = None
    best_distance = -1.0
    for i in range(len(connectors)):
        for j in range(i + 1, len(connectors)):
            try:
                distance = connectors[i].Origin.DistanceTo(connectors[j].Origin)
            except Exception:
                continue
            if distance > best_distance:
                best_distance = distance
                best_pair = (connectors[i], connectors[j])
    return best_pair


def _connector_midpoint(pair):
    return XYZ(
        (pair[0].Origin.X + pair[1].Origin.X) / 2.0,
        (pair[0].Origin.Y + pair[1].Origin.Y) / 2.0,
        (pair[0].Origin.Z + pair[1].Origin.Z) / 2.0)


def _move_location_to(instance, current_xyz, target_xyz):
    try:
        delta = XYZ(
            target_xyz.X - current_xyz.X,
            target_xyz.Y - current_xyz.Y,
            target_xyz.Z - current_xyz.Z)
        return instance.Location.Move(delta)
    except Exception:
        return False


def _pipe_containing_point(pipes, xyz):
    for pipe in pipes:
        if pipe is not None and _point_on_pipe_curve(pipe, xyz):
            return pipe
    return None


class AccessoryPlacementWriter(object):
    def __init__(self, doc):
        self._doc = doc

    def place_inline_valve(self, valve_symbol, valve_point_mm, feed_entries):
        """Places a selected Pipe Accessory inline on the valve feed segment.

        The current Water Supply slice deliberately supports the horizontal
        valve-height feed segment first. That is the segment created by the
        ceiling-bypass valve geometry: drop from the incoming main, 200mm
        horizontal valve run, then rise on the post-valve side before
        continuing to the trunk.

        :rtype: Result wrapping {"valve": FamilyInstance or None}
        """
        entry = self._find_valve_feed_entry(valve_point_mm, feed_entries)
        if entry is None:
            return Result.fail(
                u"No horizontal valve-height feed pipe was found at the selected "
                u"valve point. Valve placement currently requires the valve point "
                u"to lie on a horizontal feed segment.")

        start_mm, end_mm, pipe = entry
        axis = _horizontal_axis(start_mm, end_mm)
        if axis is None:
            return Result.fail(u"The valve feed segment is too short for inline valve placement.")

        try:
            if not valve_symbol.IsActive:
                valve_symbol.Activate()
                self._doc.Regenerate()

            valve_xyz = _mm_to_xyz(valve_point_mm)
            valve_instance = self._doc.Create.NewFamilyInstance(
                valve_xyz, valve_symbol, StructuralType.NonStructural)
            self._doc.Regenerate()

            align_result = self._align_valve_to_segment(
                valve_instance, valve_xyz, axis)
            if not align_result.success:
                return align_result

            pair = align_result.value["connector_pair"]
            sorted_connectors = self._connectors_sorted_on_segment(
                pair, start_mm, (axis[0], axis[1]))
            if sorted_connectors is None:
                return Result.fail(
                    u"The selected valve family's pipe connectors are not aligned "
                    u"with the valve feed segment.")

            connector_a, connector_b = sorted_connectors
            point_a_mm = _xyz_to_mm(connector_a.Origin)
            point_b_mm = _xyz_to_mm(connector_b.Origin)
            segment_length = axis[2]
            t_a = _dot_xy(point_a_mm, start_mm, (axis[0], axis[1]))
            t_b = _dot_xy(point_b_mm, start_mm, (axis[0], axis[1]))
            if (t_a < _MIN_BREAK_CLEARANCE_MM or
                    t_b > segment_length - _MIN_BREAK_CLEARANCE_MM or
                    t_b - t_a < _MIN_BREAK_CLEARANCE_MM):
                return Result.fail(
                    u"The selected valve family is too long for the available "
                    u"valve segment. Increase the valve horizontal run or choose "
                    u"a shorter valve type.")

            split_result = self._split_pipe_for_valve(
                pipe, connector_a, connector_b)
            if not split_result.success:
                return split_result

            return Result.ok(value={"valve": valve_instance})
        except Exception as e:
            _logger.warning(u"Inline valve placement failed: {0}", str(e))
            return Result.fail(u"Inline valve placement failed: {0}".format(str(e)))

    def _find_valve_feed_entry(self, valve_point_mm, feed_entries):
        candidates = []
        for entry in feed_entries or []:
            try:
                start_mm, end_mm, pipe = entry
            except Exception:
                continue
            if pipe is None:
                continue
            if _point_on_segment_mm(valve_point_mm, start_mm, end_mm):
                candidates.append(entry)
        if not candidates:
            return None
        candidates.sort(key=lambda e: _distance_mm(e[0], e[1]))
        return candidates[0]

    def _align_valve_to_segment(self, valve_instance, valve_xyz, axis):
        connectors = _piping_connectors(valve_instance)
        if len(connectors) < 2:
            return Result.fail(
                u"The selected valve family has fewer than two pipe connectors.")

        pair = _farthest_connector_pair(connectors)
        if pair is None:
            return Result.fail(u"Could not identify the selected valve family's pipe connectors.")

        current_vector = XYZ(
            pair[1].Origin.X - pair[0].Origin.X,
            pair[1].Origin.Y - pair[0].Origin.Y,
            pair[1].Origin.Z - pair[0].Origin.Z)
        current_xy_length = (current_vector.X ** 2 + current_vector.Y ** 2) ** 0.5
        if current_xy_length < (10.0 / 304.8):
            return Result.fail(
                u"The selected valve family's primary connectors are vertical. "
                u"This slice needs a horizontal inline valve family.")

        target_angle = math.atan2(axis[1], axis[0])
        current_angle = math.atan2(current_vector.Y, current_vector.X)
        rotation = target_angle - current_angle
        if abs(rotation) > 0.000001:
            try:
                rotation_axis = Line.CreateBound(
                    valve_xyz, XYZ(valve_xyz.X, valve_xyz.Y, valve_xyz.Z + 1.0))
                valve_instance.Location.Rotate(rotation_axis, rotation)
                self._doc.Regenerate()
            except Exception as e:
                return Result.fail(
                    u"Could not rotate the selected valve family onto the pipe "
                    u"axis: {0}".format(str(e)))

        connectors = _piping_connectors(valve_instance)
        pair = _farthest_connector_pair(connectors)
        if pair is None:
            return Result.fail(u"Could not read the valve connectors after rotation.")

        midpoint = _connector_midpoint(pair)
        if midpoint.DistanceTo(valve_xyz) > (1.0 / 304.8):
            if not _move_location_to(valve_instance, midpoint, valve_xyz):
                return Result.fail(u"Could not move the valve family onto the selected valve point.")
            self._doc.Regenerate()
            connectors = _piping_connectors(valve_instance)
            pair = _farthest_connector_pair(connectors)
            if pair is None:
                return Result.fail(u"Could not read the valve connectors after placement.")

        return Result.ok(value={"connector_pair": pair})

    def _connectors_sorted_on_segment(self, pair, start_mm, axis_xy):
        points = []
        for connector in pair:
            point_mm = _xyz_to_mm(connector.Origin)
            points.append((_dot_xy(point_mm, start_mm, axis_xy), connector))
        points.sort(key=lambda x: x[0])
        return (points[0][1], points[1][1])

    def _split_pipe_for_valve(self, pipe, connector_a, connector_b):
        point_a = connector_a.Origin
        point_b = connector_b.Origin

        try:
            new_id = PlumbingUtils.BreakCurve(self._doc, pipe.Id, point_a)
            self._doc.Regenerate()
            first_candidates = [pipe, self._doc.GetElement(new_id)]

            second_pipe = _pipe_containing_point(first_candidates, point_b)
            if second_pipe is None:
                return Result.fail(
                    u"Could not find the pipe piece that should receive the "
                    u"second valve split.")

            new_id_2 = PlumbingUtils.BreakCurve(self._doc, second_pipe.Id, point_b)
            self._doc.Regenerate()

            candidates = []
            seen = set()
            for candidate in [pipe, self._doc.GetElement(new_id), second_pipe,
                              self._doc.GetElement(new_id_2)]:
                if candidate is None:
                    continue
                try:
                    candidate_id = candidate.Id.IntegerValue
                except Exception:
                    candidate_id = candidate.Id.Value
                if candidate_id in seen:
                    continue
                seen.add(candidate_id)
                candidates.append(candidate)

            middle_pipe = None
            side_a_pipe = None
            side_b_pipe = None
            for candidate in candidates:
                has_a = _connector_near(candidate, point_a) is not None
                has_b = _connector_near(candidate, point_b) is not None
                if has_a and has_b:
                    middle_pipe = candidate
                elif has_a:
                    side_a_pipe = candidate
                elif has_b:
                    side_b_pipe = candidate

            if middle_pipe is None or side_a_pipe is None or side_b_pipe is None:
                return Result.fail(
                    u"Valve pipe split did not produce two open pipe ends and "
                    u"one removable middle pipe.")

            self._doc.Delete(middle_pipe.Id)
            self._doc.Regenerate()

            pipe_connector_a = _connector_near(side_a_pipe, point_a)
            pipe_connector_b = _connector_near(side_b_pipe, point_b)
            if pipe_connector_a is None or pipe_connector_b is None:
                return Result.fail(u"Could not find the split pipe connectors for the valve.")

            pipe_connector_a.ConnectTo(connector_a)
            pipe_connector_b.ConnectTo(connector_b)
            self._doc.Regenerate()
            return Result.ok(value={})
        except Exception as e:
            _logger.warning(u"Valve pipe split/connect failed: {0}", str(e))
            return Result.fail(
                u"Valve pipe split/connect failed: {0}".format(str(e)))

    def place_origin_valve(self, routing_graph, valve_symbol, trunk_pipes):
        """valve_symbol: a real Revit FamilySymbol (Pipe Accessory category) -
        an open input the caller must resolve, same class of requirement as
        PipeType (MEP_Routing_Playbook.md Sec 9/§19). Activated automatically
        if not already active.
        trunk_pipes: list[Pipe] from PipeGeometryWriter, in trunk order - the
        valve joins to trunk_pipes[0]'s connector at the origin point.

        :rtype: Result wrapping {"valve": FamilyInstance or None}
        """
        if not trunk_pipes:
            return Result.fail(u"No trunk pipes to attach a valve to.")

        try:
            if not valve_symbol.IsActive:
                valve_symbol.Activate()
                self._doc.Regenerate()

            origin_xyz = _mm_to_xyz(routing_graph.origin.position)
            trunk_connector = _connector_near(trunk_pipes[0], origin_xyz)
            if trunk_connector is None:
                return Result.fail(u"Could not find the trunk's origin connector to attach the valve to.")

            valve_instance = self._doc.Create.NewFamilyInstance(
                origin_xyz, valve_symbol, StructuralType.NonStructural)
            self._doc.Regenerate()

            mep_model = getattr(valve_instance, u"MEPModel", None)
            if mep_model is None:
                return Result.fail(u"Placed valve has no MEPModel - cannot connect it.")

            valve_connectors = list(mep_model.ConnectorManager.Connectors)
            if not valve_connectors:
                return Result.fail(u"Placed valve has no connectors.")

            closest = min(valve_connectors, key=lambda vc: vc.Origin.DistanceTo(trunk_connector.Origin))
            trunk_connector.ConnectTo(closest)
            self._doc.Regenerate()

            return Result.ok(value={"valve": valve_instance})
        except Exception as e:
            _logger.warning(u"Valve placement failed: {0}", str(e))
            return Result.fail(u"Valve placement failed: {0}".format(str(e)))
