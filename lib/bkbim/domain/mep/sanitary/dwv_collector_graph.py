# -*- coding: utf-8 -*-
"""Pure DWV collector graph for the next Sanitary Drainage vertical slice.

This module deliberately does NOT create Revit pipes or fittings. It only
answers the first engineering question for DWV:

    Given a wall-derived corridor, selected fixture drain outlets, and a
    downstream stack point, where should the sloped collector run and where
    should each fixture branch enter it?

The old Sanitary Drainage command still routes each fixture directly to a
clicked stack point. That was an acceptable spike, but not a realistic DWV
network. This graph starts the replacement: one continuous collector main
sloping to the stack, with fixture branches entering through wye-intent
junctions.
"""

import math

from bkbim.domain.mep.models.routing_plan import (
    FittingPlan, PipeSegmentPlan, RoutingPlan,
)
from bkbim.domain.mep.routing.routing_graph import RoutingCorridor, RouteSegment
from bkbim.domain.mep.sanitary import slope_rules


_TOLERANCE_MM = 1e-6
ROUTE_AUTO = u"Auto"
ROUTE_X_THEN_Y = u"XThenY"
ROUTE_Y_THEN_X = u"YThenX"


def _distance(a, b):
    return math.sqrt(
        (b[0] - a[0]) ** 2 +
        (b[1] - a[1]) ** 2 +
        (b[2] - a[2]) ** 2)


def _horizontal_distance(a, b):
    return math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)


def _points_close(a, b, tolerance=_TOLERANCE_MM):
    return _distance(a, b) <= tolerance


def _replace_z(point, z):
    return (point[0], point[1], z)


def _point_at_distance(points, distance_along):
    if distance_along <= 0:
        return points[0]
    cumulative = 0.0
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        segment_length = _distance(a, b)
        if distance_along <= cumulative + segment_length or i == len(points) - 2:
            if segment_length == 0:
                return a
            t = max(0.0, min(1.0, (distance_along - cumulative) / segment_length))
            return (
                a[0] + (b[0] - a[0]) * t,
                a[1] + (b[1] - a[1]) * t,
                a[2] + (b[2] - a[2]) * t)
        cumulative += segment_length
    return points[-1]


def _sub_polyline_between(points, start_distance, end_distance):
    """Returns corridor points from start_distance to end_distance.

    Distances use the input point order. start_distance may be greater than
    end_distance; in that case the returned polyline is reversed so its first
    point is still start_distance. This lets DWV model flow from the upstream
    end toward the downstream stack regardless of how the wall adapter ordered
    the selected walls.
    """
    if abs(start_distance - end_distance) <= _TOLERANCE_MM:
        return [_point_at_distance(points, start_distance)]

    reverse = start_distance > end_distance
    low = min(start_distance, end_distance)
    high = max(start_distance, end_distance)
    result = [_point_at_distance(points, low)]

    cumulative = 0.0
    for i in range(1, len(points)):
        cumulative += _distance(points[i - 1], points[i])
        if low + _TOLERANCE_MM < cumulative < high - _TOLERANCE_MM:
            result.append(points[i])

    result.append(_point_at_distance(points, high))
    if reverse:
        result.reverse()
    return result


def _horizontal_polyline_length(points):
    return sum(
        _horizontal_distance(points[i], points[i + 1])
        for i in range(len(points) - 1))


def _apply_fall_toward_downstream(points, downstream_z_mm, slope_percent):
    """Applies gravity fall so the last point is downstream_z_mm.

    Positive slope_percent means the pipe falls in the direction of the
    ordered polyline, from points[0] toward points[-1].
    """
    total_run = _horizontal_polyline_length(points)
    result = []
    travelled = 0.0
    for i, point in enumerate(points):
        if i > 0:
            travelled += _horizontal_distance(points[i - 1], points[i])
        remaining_to_downstream = total_run - travelled
        z = downstream_z_mm + remaining_to_downstream * (slope_percent / 100.0)
        result.append(_replace_z(point, z))
    return result


def _apply_fall_from_upstream(points, upstream_z_mm, slope_percent):
    """Applies gravity fall so the first point is upstream_z_mm."""
    result = []
    travelled = 0.0
    for i, point in enumerate(points):
        if i > 0:
            travelled += _horizontal_distance(points[i - 1], points[i])
        z = upstream_z_mm - travelled * (slope_percent / 100.0)
        result.append(_replace_z(point, z))
    return result


def _dedupe_consecutive_points(points):
    result = []
    for point in points:
        if not result or not _points_close(result[-1], point):
            result.append(point)
    return result


def _wc_backbone_candidates(wc_point, stack_point):
    x_then_y = _dedupe_consecutive_points([
        wc_point,
        (stack_point[0], wc_point[1], wc_point[2]),
        (stack_point[0], stack_point[1], wc_point[2]),
    ])
    y_then_x = _dedupe_consecutive_points([
        wc_point,
        (wc_point[0], stack_point[1], wc_point[2]),
        (stack_point[0], stack_point[1], wc_point[2]),
    ])
    return [(ROUTE_X_THEN_Y, x_then_y), (ROUTE_Y_THEN_X, y_then_x)]


def wc_backbone_corridor(wc_point, stack_point, branch_points=None,
                         route_preference=ROUTE_AUTO):
    """Builds the WC -> stack backbone in plan.

    This is the product-owner DWV correction: in typical bathrooms the WC's
    DN110 drain is the primary run to the stack, not a wall corridor. Other
    drains tie into this backbone or a later secondary branch.
    """
    if _horizontal_distance(wc_point, stack_point) <= _TOLERANCE_MM:
        raise ValueError(u"The WC outlet and stack point are coincident in plan")
    candidates = _wc_backbone_candidates(wc_point, stack_point)
    if route_preference == ROUTE_X_THEN_Y:
        return candidates[0][1]
    if route_preference == ROUTE_Y_THEN_X:
        return candidates[1][1]

    branch_points = branch_points or []

    def score(candidate_points):
        corridor = RoutingCorridor(candidate_points)
        branch_distance = sum(
            corridor.project(point).distance_from_corridor
            for point in branch_points)
        return (branch_distance, len(candidate_points), corridor.total_length)

    return min((points for _name, points in candidates), key=score)


def _distance_from_upstream(points, point):
    corridor = RoutingCorridor(points)
    return corridor.project(point).distance_along


class DwvJunctionNode(object):
    """A fixture branch entering the collector.

    This becomes a sanitary 45-degree wye/combination fitting in a later Revit
    pass. It is intentionally not a Water Supply tee: gravity drainage has a
    different fitting rule.
    """
    def __init__(self, position, distance_from_upstream, distance_to_stack):
        self.position = position
        self.distance_from_upstream = distance_from_upstream
        self.distance_to_stack = distance_to_stack

    def __repr__(self):
        return u"<DwvJunctionNode at {0}>".format(self.position)


class DwvBranchNode(object):
    def __init__(self, target_ref, target_label, segments, slope_percent,
                 warnings=None):
        self.target_ref = target_ref
        self.target_label = target_label
        self.segments = segments
        self.slope_percent = slope_percent
        self.warnings = warnings or []

    @property
    def total_length(self):
        return sum(s.length for s in self.segments)

    def __repr__(self):
        return u"<DwvBranchNode {0} ({1} segment(s))>".format(
            self.target_label, len(self.segments))


class DwvCollectorGraph(object):
    """One sloped DWV collector draining to one stack point."""
    def __init__(self, stack_point, collector_points, junctions,
                 collector_diameter_mm, slope_percent, warnings=None,
                 lead_segments=None):
        self.stack_point = stack_point
        self.collector_points = collector_points
        self.junctions = junctions
        self.collector_diameter_mm = collector_diameter_mm
        self.slope_percent = slope_percent
        self.warnings = warnings or []
        # Segments before the sloped collector begins. Bathroom DWV uses this
        # for the WC drop below slab before the pipe turns toward the stack.
        self.lead_segments = lead_segments or []

    @property
    def upstream_end(self):
        return self.collector_points[0] if self.collector_points else None

    @property
    def downstream_end(self):
        return self.collector_points[-1] if self.collector_points else None

    @property
    def fitting_intents(self):
        return [
            FittingPlan(
                kind=FittingPlan.KIND_WYE_45,
                at_point=junction.position,
                diameter_mm=max(self.collector_diameter_mm,
                                branch.segments[0].diameter_mm if branch.segments else self.collector_diameter_mm),
                angle_deg=45.0)
            for junction, branch in self.junctions
        ]

    def __repr__(self):
        return u"<DwvCollectorGraph {0} junction(s), DN{1}>".format(
            len(self.junctions), self.collector_diameter_mm)


def dwv_routing_plan_from_graph(graph, material):
    """Converts a DWV collector graph into pipe segment plans only.

    This is Stage 2's pure hand-off: create collector and branch pipe
    segments, but do not include wyes/elbows/connections yet. The wye intents
    remain available on ``graph.fitting_intents`` for the later Stage 3 pass.
    """
    segments = []
    for lead_segment in graph.lead_segments:
        segments.append(PipeSegmentPlan(
            start_point=lead_segment.start_point,
            end_point=lead_segment.end_point,
            diameter_mm=lead_segment.diameter_mm,
            material=material,
            slope_percent=None))

    for i in range(len(graph.collector_points) - 1):
        segments.append(PipeSegmentPlan(
            start_point=graph.collector_points[i],
            end_point=graph.collector_points[i + 1],
            diameter_mm=graph.collector_diameter_mm,
            material=material,
            slope_percent=graph.slope_percent))

    for _junction, branch in graph.junctions:
        for branch_segment in branch.segments:
            segments.append(PipeSegmentPlan(
                start_point=branch_segment.start_point,
                end_point=branch_segment.end_point,
                diameter_mm=branch_segment.diameter_mm,
                material=material,
                slope_percent=branch.slope_percent))

    return RoutingPlan(
        segments=segments,
        fittings=[],
        warnings=list(graph.warnings))


def orient_collector_corridor(corridor_points, stack_point, target_points,
                              tolerance_mm=1.0):
    """Returns the wall-corridor slice that drains toward the stack.

    The returned points are ordered upstream -> downstream. The downstream
    endpoint is the stack point projected onto the corridor. Fixtures must be
    on one side of the stack for this first slice; fixtures on both sides
    require a two-way collector/manifold and are explicitly deferred.
    """
    if not target_points:
        raise ValueError(u"At least one DWV target is required")

    corridor = RoutingCorridor(corridor_points)
    stack_projection = corridor.project(stack_point)
    stack_distance = stack_projection.distance_along
    target_distances = [
        corridor.project(point).distance_along for point in target_points
    ]

    has_before = any(d < stack_distance - tolerance_mm for d in target_distances)
    has_after = any(d > stack_distance + tolerance_mm for d in target_distances)
    if has_before and has_after:
        raise ValueError(
            u"Selected DWV fixtures lie on both sides of the stack point. "
            u"This slice supports one collector direction; pick a stack at "
            u"one end of the fixture run.")
    if not has_before and not has_after:
        raise ValueError(
            u"Every selected DWV fixture projects onto the stack point. "
            u"No collector direction can be established.")

    upstream_distance = min(target_distances) if has_before else max(target_distances)
    return _sub_polyline_between(corridor_points, upstream_distance, stack_distance)


def build_dwv_collector_graph(corridor_points, stack_point, targets,
                              collector_diameter_mm, slope_percent,
                              standard=None, max_branch_length_mm=None):
    """Builds a DWV collector graph.

    corridor_points: wall-derived corridor in millimetres. The order does not
        need to match flow direction; this function orients it toward the
        stack.
    stack_point: downstream stack/riser connection point in millimetres.
    targets: list of (target_ref, outlet_point, diameter_mm), optionally with
        a fourth human-readable label.
    collector_diameter_mm: explicit collector size for this first slice.
    slope_percent: positive gravity fall toward the stack.
    standard: optional Standard; when supplied, slope rules validate collector
        and branch slopes.
    max_branch_length_mm: optional warning threshold.
    """
    if slope_percent <= 0:
        raise ValueError(u"DWV collector slope must be greater than zero")

    target_points = [target[1] for target in targets]
    collector_base = orient_collector_corridor(
        corridor_points, stack_point, target_points)
    downstream_xy = collector_base[-1]
    stack_projection = (downstream_xy[0], downstream_xy[1], stack_point[2])
    collector_points = _apply_fall_toward_downstream(
        collector_base, downstream_z_mm=stack_point[2],
        slope_percent=slope_percent)

    collector_corridor = RoutingCorridor(collector_points)
    warnings = []
    if not _points_close(collector_points[-1], stack_projection, tolerance=1e-3):
        warnings.append(
            u"Stack point was projected onto the selected corridor at {0}.".format(
                stack_projection))

    if standard is not None:
        warnings.extend(slope_rules.check_slope(
            slope_percent, collector_diameter_mm, standard))

    projected = []
    for target in targets:
        target_ref, target_point, diameter_mm = target[:3]
        target_label = target[3] if len(target) > 3 else target_ref
        proj = collector_corridor.project(target_point)
        projected.append((proj, target_ref, target_point, diameter_mm, target_label))

    # Flow is upstream -> downstream, so fixtures are ordered by their
    # location along the sloped collector.
    projected.sort(key=lambda item: item[0].distance_along)

    junctions = []
    for proj, target_ref, target_point, diameter_mm, target_label in projected:
        tap_point = proj.nearest_point
        branch_warnings = []
        horizontal_run = _horizontal_distance(target_point, tap_point)
        branch_slope = None
        if horizontal_run <= _TOLERANCE_MM:
            branch_warnings.append(
                u"{0} branch is vertical/coincident in plan - verify manually.".format(
                    target_label))
        else:
            branch_slope = ((target_point[2] - tap_point[2]) / horizontal_run) * 100.0
            if branch_slope <= 0:
                branch_warnings.append(
                    u"{0} branch rises toward the collector - fixture outlet must be "
                    u"above its collector tap.".format(target_label))
            elif standard is not None:
                branch_warnings.extend(slope_rules.check_slope(
                    branch_slope, diameter_mm, standard))

        segment = RouteSegment(target_point, tap_point, diameter_mm)
        branch = DwvBranchNode(
            target_ref=target_ref,
            target_label=target_label,
            segments=[segment],
            slope_percent=branch_slope,
            warnings=branch_warnings)

        if max_branch_length_mm is not None and branch.total_length > max_branch_length_mm:
            branch_warnings.append(
                u"Branch to {0} is {1:.0f}mm - exceeds the configured max of {2:.0f}mm.".format(
                    target_label, float(branch.total_length), float(max_branch_length_mm)))

        warnings.extend(branch_warnings)
        distance_from_upstream = proj.distance_along
        distance_to_stack = (
            collector_corridor.total_length - distance_from_upstream)
        junctions.append((
            DwvJunctionNode(
                position=tap_point,
                distance_from_upstream=distance_from_upstream,
                distance_to_stack=distance_to_stack),
            branch))

    return DwvCollectorGraph(
        stack_point=stack_projection,
        collector_points=collector_points,
        junctions=junctions,
        collector_diameter_mm=collector_diameter_mm,
        slope_percent=slope_percent,
        warnings=warnings)


def build_bathroom_dwv_backbone_graph(wc_target, stack_point, branch_targets,
                                      collector_diameter_mm, slope_percent,
                                      standard=None, max_branch_length_mm=None,
                                      route_preference=ROUTE_AUTO,
                                      wc_drop_z_mm=None):
    """Builds the preferred bathroom DWV topology.

    WC target -> DN110-ish main drain/backbone -> stack. Other fixtures project
    into that WC backbone. This reflects the product owner's normal bathroom
    practice and intentionally does not route the collector in the wall.

    wc_target: (target_ref, wc_outlet_point, diameter_mm[, label])
    stack_point: clicked downstream stack/riser plan point. Its Z is treated as
        a reference only; the generated stack tie-in Z is computed from the WC
        outlet and selected slope.
    branch_targets: sinks, floor drains, shower pans, etc.
    """
    if slope_percent <= 0:
        raise ValueError(u"DWV collector slope must be greater than zero")

    wc_ref, wc_point, wc_diameter_mm = wc_target[:3]
    drop_z = wc_drop_z_mm if wc_drop_z_mm is not None else wc_point[2]
    wc_backbone_start = (wc_point[0], wc_point[1], drop_z)
    branch_points = [target[1] for target in branch_targets]
    backbone_base = wc_backbone_corridor(
        wc_backbone_start, stack_point, branch_points=branch_points,
        route_preference=route_preference)
    collector_points = _apply_fall_from_upstream(
        backbone_base, upstream_z_mm=drop_z, slope_percent=slope_percent)

    collector_diameter = max(collector_diameter_mm, wc_diameter_mm, 110.0)
    collector_corridor = RoutingCorridor(collector_points)
    warnings = []
    computed_stack_point = collector_points[-1]
    if abs(computed_stack_point[2] - stack_point[2]) > 50.0:
        warnings.append(
            u"Stack tie-in elevation was computed from the WC outlet and slope "
            u"({0:.0f}mm). The clicked stack point Z was {1:.0f}mm.".format(
                float(computed_stack_point[2]), float(stack_point[2])))

    if standard is not None:
        warnings.extend(slope_rules.check_slope(
            slope_percent, collector_diameter, standard))
    lead_segments = []
    if not _points_close(wc_point, wc_backbone_start):
        lead_segments.append(RouteSegment(
            wc_point, wc_backbone_start, collector_diameter))

    projected = []
    for target in branch_targets:
        target_ref, target_point, diameter_mm = target[:3]
        target_label = target[3] if len(target) > 3 else target_ref
        proj = collector_corridor.project(target_point)
        projected.append((proj, target_ref, target_point, diameter_mm, target_label))
    projected.sort(key=lambda item: item[0].distance_along)

    junctions = []
    for proj, target_ref, target_point, diameter_mm, target_label in projected:
        tap_point = proj.nearest_point
        branch_warnings = []
        horizontal_run = _horizontal_distance(target_point, tap_point)
        branch_slope = None
        if horizontal_run <= _TOLERANCE_MM:
            branch_warnings.append(
                u"{0} branch is vertical/coincident in plan - verify manually.".format(
                    target_label))
        else:
            branch_slope = ((target_point[2] - tap_point[2]) / horizontal_run) * 100.0
            if branch_slope <= 0:
                branch_warnings.append(
                    u"{0} branch rises toward the WC drain backbone - fixture "
                    u"outlet must be above its tap.".format(target_label))
            elif standard is not None:
                branch_warnings.extend(slope_rules.check_slope(
                    branch_slope, diameter_mm, standard))

        segment = RouteSegment(target_point, tap_point, diameter_mm)
        branch = DwvBranchNode(
            target_ref=target_ref,
            target_label=target_label,
            segments=[segment],
            slope_percent=branch_slope,
            warnings=branch_warnings)
        if max_branch_length_mm is not None and branch.total_length > max_branch_length_mm:
            branch_warnings.append(
                u"Branch to {0} is {1:.0f}mm - exceeds the configured max of {2:.0f}mm.".format(
                    target_label, float(branch.total_length), float(max_branch_length_mm)))
        warnings.extend(branch_warnings)
        distance_from_upstream = proj.distance_along
        distance_to_stack = (
            collector_corridor.total_length - distance_from_upstream)
        junctions.append((
            DwvJunctionNode(
                position=tap_point,
                distance_from_upstream=distance_from_upstream,
                distance_to_stack=distance_to_stack),
            branch))

    graph = DwvCollectorGraph(
        stack_point=computed_stack_point,
        collector_points=collector_points,
        junctions=junctions,
        collector_diameter_mm=collector_diameter,
        slope_percent=slope_percent,
        warnings=warnings,
        lead_segments=lead_segments)
    graph.primary_fixture_ref = wc_ref
    graph.primary_fixture_point = wc_point
    graph.routing_topology = u"WCBackbone"
    return graph
