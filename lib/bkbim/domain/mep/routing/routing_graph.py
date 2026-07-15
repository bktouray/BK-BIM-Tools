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
    def __init__(self, position):
        self.position = position

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
    routing target; this module never inspects it.
    """
    def __init__(self, target_ref, segments):
        self.target_ref = target_ref
        self.segments = segments

    @property
    def total_length(self):
        return sum(s.length for s in self.segments)

    def __repr__(self):
        return u"<BranchNode {0} ({1} segment(s), {2:.0f}mm)>".format(
            self.target_ref, len(self.segments), float(self.total_length))


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
        """Ordered points along the trunk's own path: origin -> each
        junction's tap point, in order. Consecutive pairs are the trunk's
        real pipe segments (Phase 2, MEP_Routing_Playbook.md Sec 15) - a
        graph with no junctions returns just [origin.position], meaning no
        trunk pipe is needed at all (nothing to route to).
        """
        points = [self.origin.position]
        for junction, _branch in self.junctions:
            points.append(junction.position)
        return points

    def __repr__(self):
        return u"<RoutingGraph {0} junction(s), {1} warning(s)>".format(
            len(self.junctions), len(self.warnings))


def build_routing_graph(corridor_points, targets, wall_penetration_mm,
                         max_branch_length_mm=None):
    """corridor_points: ordered list of (x,y,z) - corridor_points[0] is the
    trunk's origin (e.g. a valve location); the rest describe the corridor's
    path (from wall geometry, never from target positions).
    targets: list of (target_ref, target_point, diameter_mm) - discipline-
    agnostic; a fixture's connector position, or any future routing target.
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
    for target_ref, target_point, diameter_mm in targets:
        proj = corridor.project(target_point)
        projected.append((proj, target_ref, target_point, diameter_mm))

    # Order by distance along the corridor, NOT distance from the origin as
    # the crow flies - this is what "furthest" means now: last along the
    # corridor, which falls out automatically rather than needing its own
    # calculation (the key correction from the first redesign pass).
    projected.sort(key=lambda item: item[0].distance_along)

    junctions = []
    for proj, target_ref, target_point, diameter_mm in projected:
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

        branch = BranchNode(target_ref=target_ref, segments=segments)

        actual_horizontal_distance = _distance(
            (target_point[0], target_point[1], 0), (tap_point[0], tap_point[1], 0))
        if (wall_penetration_mm is not None and
                abs(actual_horizontal_distance - wall_penetration_mm) > wall_penetration_mm):
            warnings.append(
                u"{0}'s real horizontal distance to the corridor ({1:.0f}mm) differs "
                u"substantially from the configured wall penetration ({2:.0f}mm) - "
                u"verify this target is actually on the corridor's own wall.".format(
                    target_ref, float(actual_horizontal_distance), float(wall_penetration_mm)))

        if max_branch_length_mm is not None and branch.total_length > max_branch_length_mm:
            warnings.append(
                u"Branch to {0} is {1:.0f}mm - exceeds the configured max of {2:.0f}mm.".format(
                    target_ref, float(branch.total_length), float(max_branch_length_mm)))

        junctions.append((JunctionNode(position=tap_point), branch))

    end_position = junctions[-1][0].position if junctions else corridor_points[0]

    return RoutingGraph(
        origin=OriginNode(position=corridor_points[0]),
        corridor=corridor,
        junctions=junctions,
        end_node=EndNode(position=end_position),
        warnings=warnings)
