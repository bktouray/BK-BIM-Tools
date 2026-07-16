# -*- coding: utf-8 -*-
"""Discipline-independent routing graph (MEP_SAD.md Sec 5A,
MEP_Routing_Playbook.md). Pure domain, no Revit types anywhere (ADR-0001) -
Phase 1 of the inside-out build order the product owner specified
2026-07-10: this graph must exist and be fully unit-tested before any Revit
geometry/fitting/accessory work starts.

Naming is deliberately generic (RoutingGraph/RouteSegment/JunctionNode/...),
not Water-Supply-specific - the shape is meant to serve any pipe-flow-with-
connectors discipline (Sanitary, Vent, Storm, Fire Protection, Gas are all
plausible future consumers). Genuinely different physical systems (Cable
Trays, Conduits, Ductwork) are NOT proven by this - the naming doesn't
promise they'll fit without changes, only that nothing here actively
precludes trying.

Core idea (the key correction from the first redesign pass): the trunk's
path comes from a `RoutingCorridor` - built from wall geometry the caller
supplies, independent of where any routing target sits - never from
chaining targets nearest-to-furthest. Each target is projected onto the
corridor to find its own tap point; a target's position along the corridor
is what determines branch order, not a separate distance-from-origin
calculation.
"""

import math


def _distance(a, b):
    return math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 + (b[2] - a[2]) ** 2)


def _subtract(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(v, factor):
    return (v[0] * factor, v[1] * factor, v[2] * factor)


def _normalize(v):
    length = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
    if length == 0:
        return (0.0, 0.0, 0.0)
    return (v[0] / length, v[1] / length, v[2] / length)


def _points_close(a, b, tolerance=1e-6):
    return _distance(a, b) <= tolerance


def _closest_point_on_segment(p, a, b):
    """Returns (closest_point, t) - t in [0,1] is the fraction along a->b."""
    d = _subtract(b, a)
    length_sq = d[0] ** 2 + d[1] ** 2 + d[2] ** 2
    if length_sq == 0:
        return a, 0.0
    ap = _subtract(p, a)
    t = (ap[0] * d[0] + ap[1] * d[1] + ap[2] * d[2]) / length_sq
    t = max(0.0, min(1.0, t))
    return _add(a, _scale(d, t)), t


def _closest_point_on_segment_horizontal(p, a, b):
    """Same as _closest_point_on_segment, but computes `t` using HORIZONTAL
    (X,Y) distance only - Z never influences which point along the segment
    is "closest". The returned point's Z is interpolated from a/b's own Z
    (the corridor's real installation height), never from `p`'s Z.

    Real bug fixed 2026-07-10: projecting in full 3D let a target's own
    elevation dominate which corridor point it tapped into - a wash basin
    connector 400mm above the trunk projected onto a point that made its
    "wall entry" stub travel almost entirely vertically instead of
    horizontally, producing a diagonal-looking branch. Same root cause and
    same fix as nearby_wall_finder.py's "flatten Z before projecting"
    lesson from the room/wall-highlight work earlier this session.
    """
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return a, 0.0
    px, py = p[0] - a[0], p[1] - a[1]
    t = (px * dx + py * dy) / length_sq
    t = max(0.0, min(1.0, t))
    return _add(a, _scale(_subtract(b, a), t)), t


class ProjectionResult(object):
    def __init__(self, nearest_point, distance_along, distance_from_corridor):
        self.nearest_point = nearest_point
        # Distance along the corridor from its own start (points[0]) to
        # nearest_point - this is what determines branch order; "furthest"
        # falls out of this automatically, no separate calculation needed.
        self.distance_along = distance_along
        self.distance_from_corridor = distance_from_corridor

    def __repr__(self):
        return u"<ProjectionResult at {0}, along={1:.1f}, off={2:.1f}>".format(
            self.nearest_point, float(self.distance_along), float(self.distance_from_corridor))


class RoutingCorridor(object):
    """An ordered polyline describing where the trunk runs - derived from
    wall geometry by the caller (e.g. the confirmed wall(s)' centerlines,
    offset by the in-wall convention), never from routing targets.
    """
    def __init__(self, points):
        if len(points) < 2:
            raise ValueError(u"A corridor needs at least 2 points")
        self.points = list(points)

    @property
    def total_length(self):
        return sum(_distance(self.points[i], self.points[i + 1])
                    for i in range(len(self.points) - 1))

    def project(self, point):
        """Finds the closest point on the whole corridor to `point`, using
        HORIZONTAL (X,Y) distance only - a corridor represents a trunk
        running at its own fixed installation height, and a target's own
        elevation must never influence which point along the corridor it
        taps into (see `_closest_point_on_segment_horizontal`'s docstring
        for the real bug this fixes). The returned point's Z comes from the
        corridor itself, never from `point`.

        :rtype: ProjectionResult
        """
        best = None
        cumulative = 0.0
        for i in range(len(self.points) - 1):
            a, b = self.points[i], self.points[i + 1]
            seg_length = _distance(a, b)
            closest, t = _closest_point_on_segment_horizontal(point, a, b)
            dist = _distance(point, closest)
            along = cumulative + t * seg_length
            if best is None or dist < best.distance_from_corridor:
                best = ProjectionResult(nearest_point=closest, distance_along=along,
                                         distance_from_corridor=dist)
            cumulative += seg_length
        return best

    def direction_at(self, distance_along):
        """Unit direction vector of the corridor segment containing this
        distance-along value - used to know which way "parallel to the
        wall" points for a branch's run.
        """
        cumulative = 0.0
        for i in range(len(self.points) - 1):
            a, b = self.points[i], self.points[i + 1]
            seg_length = _distance(a, b)
            if distance_along <= cumulative + seg_length or i == len(self.points) - 2:
                return _normalize(_subtract(b, a))
            cumulative += seg_length
        return (0.0, 0.0, 0.0)


def orient_single_segment_corridor(segment_start, segment_end, origin_point,
                                   target_points, tolerance=1e-6):
    """Builds the supported slice's corridor from one straight wall segment.

    The user may click the origin slightly off the wall; it is projected onto
    the segment. All targets must lie on one side of that projected origin so
    the trunk has one unambiguous direction. A target set on both sides would
    require a two-direction main/manifold, which is intentionally outside this
    first Cold Water slice.
    """
    if _points_close(segment_start, segment_end, tolerance=tolerance):
        raise ValueError(u"The selected wall segment has no usable length")
    if not target_points:
        raise ValueError(u"At least one routing target is required")

    segment_length = _distance(segment_start, segment_end)
    projected_origin, origin_t = _closest_point_on_segment_horizontal(
        origin_point, segment_start, segment_end)
    target_ts = [
        _closest_point_on_segment_horizontal(point, segment_start, segment_end)[1]
        for point in target_points
    ]
    deltas = [target_t - origin_t for target_t in target_ts]
    has_before = any(
        delta * segment_length < -tolerance for delta in deltas)
    has_after = any(
        delta * segment_length > tolerance for delta in deltas)
    if has_before and has_after:
        raise ValueError(
            u"Selected fixtures lie on both sides of the supply origin. "
            u"Pick an origin at one end of the fixture run.")
    if not has_before and not has_after:
        raise ValueError(
            u"Every selected fixture projects onto the supply origin. "
            u"No trunk direction can be established.")

    endpoint = segment_end if has_after else segment_start
    return [projected_origin, endpoint]


def _point_at_distance(points, distance_along):
    if distance_along <= 0:
        return points[0]
    cumulative = 0.0
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        seg_length = _distance(a, b)
        if distance_along <= cumulative + seg_length or i == len(points) - 2:
            if seg_length == 0:
                return a
            t = (distance_along - cumulative) / seg_length
            t = max(0.0, min(1.0, t))
            return _add(a, _scale(_subtract(b, a), t))
        cumulative += seg_length
    return points[-1]


def _sub_polyline_from_distance(points, distance_along, toward_end=True,
                                tolerance=1e-6):
    origin = _point_at_distance(points, distance_along)
    if toward_end:
        result = [origin]
        cumulative = 0.0
        for i in range(1, len(points)):
            cumulative += _distance(points[i - 1], points[i])
            if cumulative > distance_along + tolerance:
                if not _points_close(result[-1], points[i], tolerance=tolerance):
                    result.append(points[i])
        return result

    reversed_points = list(reversed(points))
    reversed_distance = (
        RoutingCorridor(points).total_length - distance_along)
    return _sub_polyline_from_distance(
        reversed_points, reversed_distance, toward_end=True,
        tolerance=tolerance)


def orient_polyline_corridor(corridor_points, origin_point, target_points,
                             tolerance=1e-6):
    """Orients a connected multi-leg corridor from a picked origin toward
    all targets on one side of that origin.

    The input polyline is already a connected wall chain. This function
    snaps the origin onto it, keeps the corridor vertices in order, and
    returns only the side of the chain that contains the selected targets.
    Targets on both sides mean the user picked a manifold-style origin,
    which is still outside the active Cold Water slice.
    """
    corridor = RoutingCorridor(corridor_points)
    origin_projection = corridor.project(origin_point)
    target_distances = [
        corridor.project(point).distance_along for point in target_points
    ]
    origin_distance = origin_projection.distance_along
    has_before = any(
        target_distance < origin_distance - tolerance
        for target_distance in target_distances)
    has_after = any(
        target_distance > origin_distance + tolerance
        for target_distance in target_distances)
    if has_before and has_after:
        raise ValueError(
            u"Selected fixtures lie on both sides of the supply origin. "
            u"Pick a valve/origin at one end of the wall corridor.")
    if not has_before and not has_after:
        raise ValueError(
            u"Every selected fixture projects onto the supply origin. "
            u"No trunk direction can be established.")

    return _sub_polyline_from_distance(
        corridor_points, origin_distance, toward_end=has_after,
        tolerance=tolerance)


class OriginNode(object):
    """Where the trunk starts - e.g. a valve location for Water Supply.
    Purely a graph concept: a point plus an opaque, optional real-world ref
    (a placed valve, once that becomes a real capability - MEP_SAD.md Sec
    5A treats placement as a separate later layer, not a routing concern).
    """
    def __init__(self, position, ref=None):
        self.position = position
        self.ref = ref

    def __repr__(self):
        return u"<OriginNode at {0}>".format(self.position)


class EndNode(object):
    """Where the trunk terminates - the furthest target's tap point. Nothing
    continues past this; no Tee here, just a plain elbow once geometry is
    generated (Phase 2).
    """
    def __init__(self, position):
        self.position = position

    def __repr__(self):
        return u"<EndNode at {0}>".format(self.position)


class JunctionNode(object):
    """A point where the trunk continues AND a branch splits off - becomes
    a Tee once fittings are generated (Phase 3). The trunk itself is never
    broken here - "continues" is what distinguishes this from EndNode.
    """
    def __init__(self, position, distance_along=None):
        self.position = position
        self.distance_along = distance_along

    def __repr__(self):
        return u"<JunctionNode at {0}>".format(self.position)


class RouteSegment(object):
    """One straight run between two points - the base geometric unit
    everything else in the graph is built from.
    """
    def __init__(self, start_point, end_point, diameter_mm):
        self.start_point = start_point
        self.end_point = end_point
        self.diameter_mm = diameter_mm

    @property
    def length(self):
        return _distance(self.start_point, self.end_point)

    def __repr__(self):
        return u"<RouteSegment dn{0} {1}->{2}>".format(
            self.diameter_mm, self.start_point, self.end_point)


class BranchNode(object):
    """One routing target's own path back to its JunctionNode on the trunk.

    Shape (2 segments, fixed 2026-07-10 - see the routing_graph module
    docstring and MEP_Routing_Playbook.md's Decision Log for the full
    story): a horizontal segment aligning with the tap point's plan
    position at the TARGET's own elevation, then a vertical segment
    reaching the corridor's own elevation. This is the correct shape when
    the target sits on the same wall the corridor runs along (confirmed
    live against real WC/wash-basin connectors at different heights on the
    same wall). A target on a genuinely DIFFERENT wall than the corridor
    (needing a corner turn to reach it) is NOT handled by this shape yet -
    a known, disclosed limitation, not silently guessed at.

    `target_ref` is opaque (ADR-0001) - a fixture connector, or any future
    routing target; this module never inspects it. `target_label` is optional
    human-readable diagnostic text supplied by the caller. Keeping it separate
    lets Revit adapters retain the real connector handle without leaking its
    implementation-specific representation into user-facing warnings.
    """
    def __init__(self, target_ref, segments, target_label=None):
        self.target_ref = target_ref
        self.segments = segments
        self.target_label = target_label if target_label is not None else target_ref

    @property
    def total_length(self):
        return sum(s.length for s in self.segments)

    def __repr__(self):
        return u"<BranchNode {0} ({1} segment(s), {2:.0f}mm)>".format(
            self.target_label, len(self.segments), float(self.total_length))


class RoutingGraph(object):
    """The whole abstract routing graph for one trunk (MEP_SAD.md Sec 5A):
    an OriginNode, the RoutingCorridor it runs along, an ordered list of
    (JunctionNode, BranchNode) pairs (nearest-to-furthest along the
    corridor), and one EndNode. No Revit geometry exists yet at this stage -
    that's Phase 2's job.
    """
    def __init__(self, origin, corridor, junctions, end_node, warnings=None):
        self.origin = origin
        self.corridor = corridor
        self.junctions = junctions
        self.end_node = end_node
        self.warnings = warnings or []

    @property
    def trunk_points(self):
        """Ordered points along the corridor to the furthest junction.

        Corridor vertices are retained. The previous implementation returned
        only origin + junctions, which cut diagonally across every multi-leg
        wall corridor instead of following its geometry.
        """
        if not self.junctions:
            return [self.origin.position]

        end_distance = self.junctions[-1][0].distance_along
        items = [(0.0, self.origin.position)]

        cumulative = 0.0
        for i, point in enumerate(self.corridor.points):
            if i > 0:
                cumulative += _distance(
                    self.corridor.points[i - 1], self.corridor.points[i])
            if cumulative <= end_distance + 1e-6:
                items.append((cumulative, point))

        for junction, _branch in self.junctions:
            items.append((junction.distance_along, junction.position))

        items.sort(key=lambda item: item[0])
        points = []
        for _distance_along, point in items:
            if not points or not _points_close(points[-1], point):
                points.append(point)
        return points

    def __repr__(self):
        return u"<RoutingGraph {0} junction(s), {1} warning(s)>".format(
            len(self.junctions), len(self.warnings))


def build_routing_graph(corridor_points, targets, wall_penetration_mm,
                         max_branch_length_mm=None):
    """corridor_points: ordered list of (x,y,z) - corridor_points[0] is the
    trunk's origin (e.g. a valve location); the rest describe the corridor's
    path (from wall geometry, never from target positions).
    targets: list of (target_ref, target_point, diameter_mm), optionally with
    a fourth human-readable target_label - discipline-agnostic; a fixture's
    connector position, or any future routing target.
    wall_penetration_mm: the EXPECTED horizontal rough-in distance from a
    target to the wall it's mounted on - used as a validation reference (warn
    if a target's real horizontal distance to the corridor differs a lot from
    this), not as a literal segment length. Real geometry always wins over
    the configured expectation - see BranchNode's docstring for the live-
    tested reasoning behind this.
    max_branch_length_mm: optional - branches longer than this get a
    warning, never a hard failure (this suite's standing "surface problems,
    don't silently block" rule).

    :rtype: RoutingGraph
    """
    corridor = RoutingCorridor(corridor_points)
    warnings = []

    projected = []
    for target in targets:
        target_ref, target_point, diameter_mm = target[:3]
        target_label = target[3] if len(target) > 3 else target_ref
        proj = corridor.project(target_point)
        projected.append((proj, target_ref, target_point, diameter_mm, target_label))

    # Order by distance along the corridor, NOT distance from the origin as
    # the crow flies - this is what "furthest" means now: last along the
    # corridor, which falls out automatically rather than needing its own
    # calculation (the key correction from the first redesign pass).
    projected.sort(key=lambda item: item[0].distance_along)

    junctions = []
    for proj, target_ref, target_point, diameter_mm, target_label in projected:
        tap_point = proj.nearest_point

        # Horizontal segment: align with the tap point's plan position,
        # staying at the TARGET's own elevation. Real horizontal distance,
        # not the configured wall_penetration_mm - see BranchNode's
        # docstring for why a fixed penetration depth doesn't generally
        # apply here (it only matches reality when the target's true
        # rough-in distance happens to equal it).
        horizontal_point = (tap_point[0], tap_point[1], target_point[2])

        # Vertical segment: from there, reach the corridor's own elevation.
        segments = []
        if horizontal_point != target_point:
            segments.append(RouteSegment(target_point, horizontal_point, diameter_mm))
        if horizontal_point != tap_point:
            segments.append(RouteSegment(horizontal_point, tap_point, diameter_mm))

        branch = BranchNode(
            target_ref=target_ref, segments=segments, target_label=target_label)

        actual_horizontal_distance = _distance(
            (target_point[0], target_point[1], 0), (tap_point[0], tap_point[1], 0))
        if (wall_penetration_mm is not None and
                abs(actual_horizontal_distance - wall_penetration_mm) > wall_penetration_mm):
            warnings.append(
                u"{0}'s real horizontal distance to the corridor ({1:.0f}mm) differs "
                u"substantially from the configured wall penetration ({2:.0f}mm) - "
                u"verify this target is actually on the corridor's own wall.".format(
                    target_label, float(actual_horizontal_distance), float(wall_penetration_mm)))

        if max_branch_length_mm is not None and branch.total_length > max_branch_length_mm:
            warnings.append(
                u"Branch to {0} is {1:.0f}mm - exceeds the configured max of {2:.0f}mm.".format(
                    target_label, float(branch.total_length), float(max_branch_length_mm)))

        junctions.append((
            JunctionNode(position=tap_point, distance_along=proj.distance_along),
            branch))

    end_position = junctions[-1][0].position if junctions else corridor_points[0]

    return RoutingGraph(
        origin=OriginNode(position=corridor_points[0]),
        corridor=corridor,
        junctions=junctions,
        end_node=EndNode(position=end_position),
        warnings=warnings)
