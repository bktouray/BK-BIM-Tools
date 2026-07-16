# -*- coding: utf-8 -*-
"""Turns confirmed wall(s) (wall_confirmation_prompt.py) into corridor
points for build_routing_graph (MEP_Routing_Playbook.md Sec 6/14).

Known simplification, disclosed: uses the wall's own location CENTERLINE
directly, at the caller-supplied Z, rather than offsetting perpendicular
into the wall cavity by `Standard.mep_in_wall_offset_mm` - that offset still
doesn't have a product-owner-confirmed value (MEP_SAD.md Sec 5A), and
computing the correct perpendicular offset direction for an arbitrary wall
needs its own verification before being trusted. The trunk currently runs
along the wall's centerline; a real in-wall offset is a disclosed follow-up,
not silently assumed to be zero forever.
"""

import clr
import math

clr.AddReference("RevitAPI")

_CONNECT_TOLERANCE_MM = 50.0
_INTERSECTION_TOLERANCE_MM = 1.0


def _distance_xy(a, b):
    return ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5


def _point_close_xy(a, b, tolerance_mm=_CONNECT_TOLERANCE_MM):
    return _distance_xy(a, b) <= tolerance_mm


def _cluster_index(clusters, point, tolerance_mm=_CONNECT_TOLERANCE_MM):
    for index, cluster in enumerate(clusters):
        if _distance_xy(cluster, point) <= tolerance_mm:
            return index
    clusters.append(point)
    return len(clusters) - 1


def _subtract_xy(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _dot_xy(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _cross_xy(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _point_on_segment_xy(point, start, end, tolerance_mm=_CONNECT_TOLERANCE_MM):
    seg = _subtract_xy(end, start)
    length = _distance_xy(start, end)
    if length <= tolerance_mm:
        return False
    off = _subtract_xy(point, start)
    if abs(_cross_xy(seg, off)) > tolerance_mm * length:
        return False
    dot = _dot_xy(off, seg)
    return -tolerance_mm <= dot <= (length * length) + tolerance_mm


def _project_point_to_segment_xy(point, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return start, 0.0, _distance_xy(point, start)
    px, py = point[0] - start[0], point[1] - start[1]
    t = (px * dx + py * dy) / length_sq
    t = max(0.0, min(1.0, t))
    projected = (
        start[0] + dx * t,
        start[1] + dy * t,
        start[2] + (end[2] - start[2]) * t)
    return projected, t, _distance_xy(point, projected)


def _segment_intersection_xy(a, b, c, d,
                             tolerance_mm=_INTERSECTION_TOLERANCE_MM):
    r = _subtract_xy(b, a)
    s = _subtract_xy(d, c)
    denom = _cross_xy(r, s)
    c_minus_a = _subtract_xy(c, a)
    if abs(denom) <= tolerance_mm:
        return None
    t = _cross_xy(c_minus_a, s) / denom
    u = _cross_xy(c_minus_a, r) / denom
    margin = tolerance_mm / max(_distance_xy(a, b), _distance_xy(c, d), 1.0)
    if -margin <= t <= 1.0 + margin and -margin <= u <= 1.0 + margin:
        t = max(0.0, min(1.0, t))
        return (
            a[0] + r[0] * t,
            a[1] + r[1] * t,
            a[2] + (b[2] - a[2]) * t)
    return None


def _add_unique_point(points, point, tolerance_mm=_CONNECT_TOLERANCE_MM):
    for existing in points:
        if _point_close_xy(existing, point, tolerance_mm=tolerance_mm):
            return existing
    points.append(point)
    return point


def _segment_parameter(point, start, end):
    projected, t, _distance = _project_point_to_segment_xy(point, start, end)
    return t


def _nearest_segment_index(point, segments):
    best = None
    for index, (start, end) in enumerate(segments):
        projected, t, distance = _project_point_to_segment_xy(point, start, end)
        candidate = (distance, index, projected)
        if best is None or candidate[0] < best[0]:
            best = candidate
    return best[1], best[2], best[0]


def _build_wall_network(segments, origin_point, target_points,
                        tolerance_mm=_CONNECT_TOLERANCE_MM):
    split_points = [[start, end] for start, end in segments]

    for i in range(len(segments)):
        a, b = segments[i]
        for j in range(i + 1, len(segments)):
            c, d = segments[j]
            intersection = _segment_intersection_xy(a, b, c, d)
            if intersection is not None:
                _add_unique_point(split_points[i], intersection, tolerance_mm)
                _add_unique_point(split_points[j], intersection, tolerance_mm)
                continue

            # Collinear/overlapping or endpoint-on-long-wall cases. This is
            # what removes the "split the wall first" requirement for most
            # ordinary Revit wall layouts.
            for point in (a, b):
                if _point_on_segment_xy(point, c, d, tolerance_mm):
                    _add_unique_point(split_points[j], point, tolerance_mm)
            for point in (c, d):
                if _point_on_segment_xy(point, a, b, tolerance_mm):
                    _add_unique_point(split_points[i], point, tolerance_mm)

    projected_targets = []
    origin_segment_index, projected_origin, origin_distance = _nearest_segment_index(
        origin_point, segments)
    # The valve is allowed to sit away from the selected fixture-wall
    # corridor. It is projected to the nearest corridor point, and the feed
    # route bridges from the picked valve point to that projected trunk
    # origin. Only fixture targets need to be near the selected walls.
    _add_unique_point(split_points[origin_segment_index], projected_origin, tolerance_mm)

    for target in target_points:
        segment_index, projected, distance = _nearest_segment_index(target, segments)
        if distance > tolerance_mm * 8:
            raise ValueError(
                u"A selected fixture is too far from the selected wall corridor.")
        projected_targets.append(projected)
        _add_unique_point(split_points[segment_index], projected, tolerance_mm)

    clusters = []
    adjacency = {}
    for segment_index, (start, end) in enumerate(segments):
        points = sorted(
            split_points[segment_index],
            key=lambda point: _segment_parameter(point, start, end))
        unique_points = []
        for point in points:
            if not unique_points or not _point_close_xy(unique_points[-1], point, tolerance_mm):
                unique_points.append(point)
        for i in range(len(unique_points) - 1):
            a, b = unique_points[i], unique_points[i + 1]
            if _distance_xy(a, b) <= tolerance_mm:
                continue
            node_a = _cluster_index(clusters, a, tolerance_mm)
            node_b = _cluster_index(clusters, b, tolerance_mm)
            if node_a == node_b:
                continue
            weight = _distance_xy(clusters[node_a], clusters[node_b])
            adjacency.setdefault(node_a, {})[node_b] = min(
                weight, adjacency.setdefault(node_a, {}).get(node_b, weight))
            adjacency.setdefault(node_b, {})[node_a] = min(
                weight, adjacency.setdefault(node_b, {}).get(node_a, weight))

    origin_node = _cluster_index(clusters, projected_origin, tolerance_mm)
    target_nodes = [
        _cluster_index(clusters, projected, tolerance_mm)
        for projected in projected_targets
    ]
    return clusters, adjacency, origin_node, target_nodes


def _build_wall_network_for_targets(segments, target_points,
                                    tolerance_mm=_CONNECT_TOLERANCE_MM):
    split_points = [[start, end] for start, end in segments]

    for i in range(len(segments)):
        a, b = segments[i]
        for j in range(i + 1, len(segments)):
            c, d = segments[j]
            intersection = _segment_intersection_xy(a, b, c, d)
            if intersection is not None:
                _add_unique_point(split_points[i], intersection, tolerance_mm)
                _add_unique_point(split_points[j], intersection, tolerance_mm)
                continue
            for point in (a, b):
                if _point_on_segment_xy(point, c, d, tolerance_mm):
                    _add_unique_point(split_points[j], point, tolerance_mm)
            for point in (c, d):
                if _point_on_segment_xy(point, a, b, tolerance_mm):
                    _add_unique_point(split_points[i], point, tolerance_mm)

    projected_targets = []
    for target in target_points:
        segment_index, projected, distance = _nearest_segment_index(target, segments)
        if distance > tolerance_mm * 8:
            raise ValueError(
                u"A selected fixture is too far from the selected wall corridor.")
        projected_targets.append(projected)
        _add_unique_point(split_points[segment_index], projected, tolerance_mm)

    clusters = []
    adjacency = {}
    for segment_index, (start, end) in enumerate(segments):
        points = sorted(
            split_points[segment_index],
            key=lambda point: _segment_parameter(point, start, end))
        unique_points = []
        for point in points:
            if not unique_points or not _point_close_xy(unique_points[-1], point, tolerance_mm):
                unique_points.append(point)
        for i in range(len(unique_points) - 1):
            a, b = unique_points[i], unique_points[i + 1]
            if _distance_xy(a, b) <= tolerance_mm:
                continue
            node_a = _cluster_index(clusters, a, tolerance_mm)
            node_b = _cluster_index(clusters, b, tolerance_mm)
            if node_a == node_b:
                continue
            weight = _distance_xy(clusters[node_a], clusters[node_b])
            adjacency.setdefault(node_a, {})[node_b] = min(
                weight, adjacency.setdefault(node_a, {}).get(node_b, weight))
            adjacency.setdefault(node_b, {})[node_a] = min(
                weight, adjacency.setdefault(node_b, {}).get(node_a, weight))

    target_nodes = [
        _cluster_index(clusters, projected, tolerance_mm)
        for projected in projected_targets
    ]
    return clusters, adjacency, target_nodes


def _shortest_paths(adjacency, start_node):
    unvisited = set(adjacency.keys())
    distances = {start_node: 0.0}
    previous = {}
    while unvisited:
        current = None
        current_distance = None
        for node in unvisited:
            distance = distances.get(node)
            if distance is not None and (
                    current_distance is None or distance < current_distance):
                current = node
                current_distance = distance
        if current is None:
            break
        unvisited.remove(current)
        for neighbor, weight in adjacency.get(current, {}).items():
            candidate = current_distance + weight
            if neighbor not in distances or candidate < distances[neighbor]:
                distances[neighbor] = candidate
                previous[neighbor] = current
    return distances, previous


def _path_to(previous, start_node, end_node):
    path = [end_node]
    current = end_node
    while current != start_node:
        current = previous.get(current)
        if current is None:
            return []
        path.append(current)
    path.reverse()
    return path


def _ordered_connected_polyline(segments, tolerance_mm=_CONNECT_TOLERANCE_MM):
    """Orders straight wall segments into one connected non-branching chain.

    Returns polyline points. Raises ValueError when walls are disconnected,
    branching, or looped, because the active Water Supply slice needs one
    unambiguous trunk direction.
    """
    if not segments:
        raise ValueError(u"At least one wall is required for a routing corridor.")
    if len(segments) == 1:
        return [segments[0][0], segments[0][1]]

    clusters = []
    edges = []
    for start, end in segments:
        a = _cluster_index(clusters, start, tolerance_mm=tolerance_mm)
        b = _cluster_index(clusters, end, tolerance_mm=tolerance_mm)
        if a == b:
            raise ValueError(u"A selected wall segment is too short to route along.")
        edges.append((a, b))

    adjacency = {}
    for a, b in edges:
        adjacency.setdefault(a, []).append(b)
        adjacency.setdefault(b, []).append(a)

    if any(len(neighbors) > 2 for neighbors in adjacency.values()):
        raise ValueError(
            u"The selected walls form a branch. Select one continuous wall path.")

    endpoints = [node for node, neighbors in adjacency.items() if len(neighbors) == 1]
    if len(endpoints) != 2:
        raise ValueError(
            u"The selected walls must form one open continuous path, not a loop.")

    visited_edges = set()
    path_nodes = [endpoints[0]]
    previous = None
    current = endpoints[0]
    while current != endpoints[1]:
        next_nodes = [
            node for node in adjacency[current]
            if node != previous and tuple(sorted((current, node))) not in visited_edges
        ]
        if len(next_nodes) != 1:
            raise ValueError(
                u"The selected walls are not one clean continuous path.")
        nxt = next_nodes[0]
        visited_edges.add(tuple(sorted((current, nxt))))
        path_nodes.append(nxt)
        previous, current = current, nxt

    if len(visited_edges) != len(edges):
        raise ValueError(
            u"The selected walls are disconnected. Select touching walls only.")

    return [clusters[node] for node in path_nodes]


def _corridor_path_from_wall_network(segments, origin_point, target_points,
                                     tolerance_mm=_CONNECT_TOLERANCE_MM):
    if not segments:
        raise ValueError(u"At least one wall is required for a routing corridor.")
    if not target_points:
        raise ValueError(u"At least one routing target is required.")

    clusters, adjacency, origin_node, target_nodes = _build_wall_network(
        segments, origin_point, target_points, tolerance_mm=tolerance_mm)
    distances, previous = _shortest_paths(adjacency, origin_node)
    missing = [node for node in target_nodes if node not in distances]
    if missing:
        raise ValueError(
            u"The selected walls do not form a connected corridor to every fixture.")

    farthest_target = max(target_nodes, key=lambda node: distances[node])
    path_nodes = _path_to(previous, origin_node, farthest_target)
    if not path_nodes:
        raise ValueError(
            u"No continuous wall path could be found from the valve to the fixtures.")

    path_node_set = set(path_nodes)
    if any(node not in path_node_set for node in target_nodes):
        raise ValueError(
            u"Selected fixtures require branching wall paths. Select one "
            u"continuous route at a time.")

    return [clusters[node] for node in path_nodes]


def _fixture_corridor_path_from_wall_network(segments, feed_point, target_points,
                                             tolerance_mm=_CONNECT_TOLERANCE_MM):
    """Returns the selected-wall path that serves the fixtures only.

    Used when the water-main/feed leg is allowed to cut directly through a
    ceiling/floor to the fixture corridor. The feed point chooses which end
    of the fixture corridor to connect to; it does not force the trunk to
    follow the walls all the way from the valve.
    """
    if not segments:
        raise ValueError(u"At least one wall is required for a routing corridor.")
    if not target_points:
        raise ValueError(u"At least one routing target is required.")

    clusters, adjacency, target_nodes = _build_wall_network_for_targets(
        segments, target_points, tolerance_mm=tolerance_mm)
    if not target_nodes:
        raise ValueError(u"At least one routing target is required.")

    start_node = min(
        target_nodes,
        key=lambda node: _distance_xy(clusters[node], feed_point))
    distances, previous = _shortest_paths(adjacency, start_node)
    missing = [node for node in target_nodes if node not in distances]
    if missing:
        raise ValueError(
            u"The selected walls do not form a connected corridor to every fixture.")

    farthest_target = max(target_nodes, key=lambda node: distances[node])
    path_nodes = _path_to(previous, start_node, farthest_target)
    if not path_nodes:
        raise ValueError(
            u"No continuous wall path could be found for the selected fixtures.")

    path_node_set = set(path_nodes)
    if any(node not in path_node_set for node in target_nodes):
        raise ValueError(
            u"Selected fixtures require branching wall paths. Select one "
            u"continuous route at a time.")

    return [clusters[node] for node in path_nodes]


def corridor_points_from_walls(walls, z_mm):
    """walls: list[Wall], in the order the trunk should traverse them.
    This older helper does no connectivity/origin validation; the active
    Cold Water flow uses corridor_points_from_connected_walls instead.
    z_mm: the elevation the corridor runs at (the routing style's own
    horizontal_z_mm - ceiling void, floor void, or the fixed valve-height
    convention for in-wall routing).

    :rtype: list[(x, y, z)] - ready for build_routing_graph.
    """
    from bkbim.domain.geometry.units import ft_to_mm

    points = []
    for wall in walls:
        curve = wall.Location.Curve
        p0 = curve.GetEndPoint(0)
        p1 = curve.GetEndPoint(1)
        points.append((ft_to_mm(p0.X), ft_to_mm(p0.Y), z_mm))
        points.append((ft_to_mm(p1.X), ft_to_mm(p1.Y), z_mm))
    return points


def corridor_points_from_connected_walls(walls, z_mm, origin_mm, target_points_mm):
    """Returns a deterministic corridor from one or more connected walls.

    All walls must be straight. They may touch end-to-end or intersect in
    plan; they do not need to be split at the intersection. The final
    corridor is oriented from the valve/origin toward the selected fixtures,
    preserving corners along the way.
    """
    from Autodesk.Revit.DB import Line
    from bkbim.domain.geometry.units import ft_to_mm
    from bkbim.domain.mep.routing.routing_graph import orient_polyline_corridor

    segments = []
    for wall in walls:
        curve = wall.Location.Curve
        if not isinstance(curve, Line):
            raise ValueError(
                u"Cold Water multi-wall routing supports straight walls only.")
        p0 = curve.GetEndPoint(0)
        p1 = curve.GetEndPoint(1)
        segments.append((
            (ft_to_mm(p0.X), ft_to_mm(p0.Y), z_mm),
            (ft_to_mm(p1.X), ft_to_mm(p1.Y), z_mm)))

    polyline = _corridor_path_from_wall_network(
        segments, origin_mm, target_points_mm)
    origin = (origin_mm[0], origin_mm[1], z_mm)
    return orient_polyline_corridor(polyline, origin, target_points_mm,
                                    tolerance=_CONNECT_TOLERANCE_MM)


def corridor_points_for_fixture_wall_path(walls, z_mm, feed_point_mm,
                                          target_points_mm):
    """Returns only the fixture-serving wall corridor.

    The feed/main leg may cut directly from the picked water-main/valve path
    to the first point of this corridor.
    """
    from Autodesk.Revit.DB import Line
    from bkbim.domain.geometry.units import ft_to_mm

    segments = []
    for wall in walls:
        curve = wall.Location.Curve
        if not isinstance(curve, Line):
            raise ValueError(
                u"Cold Water multi-wall routing supports straight walls only.")
        p0 = curve.GetEndPoint(0)
        p1 = curve.GetEndPoint(1)
        segments.append((
            (ft_to_mm(p0.X), ft_to_mm(p0.Y), z_mm),
            (ft_to_mm(p1.X), ft_to_mm(p1.Y), z_mm)))

    feed_point = (feed_point_mm[0], feed_point_mm[1], z_mm)
    return _fixture_corridor_path_from_wall_network(
        segments, feed_point, target_points_mm)


def corridor_points_from_single_wall(wall, z_mm, origin_mm, target_points_mm):
    """Returns one deterministic corridor for the approved Cold Water slice.

    The selected wall must be straight. The origin is snapped to its location
    line, and every target must lie on the same side of that snapped origin.
    Kept for targeted single-wall tests/backward compatibility; the active
    Cold Water flow now uses corridor_points_from_connected_walls.
    """
    from Autodesk.Revit.DB import Line
    from bkbim.domain.geometry.units import ft_to_mm
    from bkbim.domain.mep.routing.routing_graph import orient_single_segment_corridor

    curve = wall.Location.Curve
    if not isinstance(curve, Line):
        raise ValueError(
            u"The single-wall corridor helper supports straight walls only.")

    p0 = curve.GetEndPoint(0)
    p1 = curve.GetEndPoint(1)
    start = (ft_to_mm(p0.X), ft_to_mm(p0.Y), z_mm)
    end = (ft_to_mm(p1.X), ft_to_mm(p1.Y), z_mm)
    origin = (origin_mm[0], origin_mm[1], z_mm)
    return orient_single_segment_corridor(
        start, end, origin, target_points_mm)
