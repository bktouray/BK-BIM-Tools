# -*- coding: utf-8 -*-
"""Classifies which walls sit on a building's exterior envelope, without
relying on Revit's own Wall.Function tag (confirmed unreliable in this
project's models - every wall reports "Interior" regardless of role, see
wall_context_builder.py). Two independent methods, both pure geometry
(ADR-0001) - no Revit types:

- classify_by_room_adjacency: when Room elements are placed in the view, a
  wall bounded by a Room on BOTH sides is interior; bounded on only one side
  (or neither) is exterior.
- classify_by_boundary_trace: when no Rooms exist, rasterizes the wall
  network onto a grid and flood-fills from the grid's border inward. A wall
  is exterior if either of its own offset sample points ends up in
  flood-filled ("reachable from outside") space.

  A plain ray-cast (crossing-number point-in-polygon test) was tried first
  and is WRONG here: it only works against a single closed polygon loop, but
  a real wall network also includes interior partitions that cross the same
  ray - each such partition flips the inside/outside parity for every point
  beyond it, misclassifying rooms on the far side. Caught live via
  test_classify_by_boundary_trace_interior_partition_is_excluded (a simple
  rectangle plus one partition wall) before this shipped. Flood-fill doesn't
  have this problem: reachability from outside is unaffected by extra
  interior walls, since they can only ever block reachability, never
  fake-open a path back out.

Product owner, 2026-07-08: "is it possible to just autodetect the building
boundary, or do I have to differentiate exterior and interior walls?"
"""

import math

_GRID_MARGIN_FT = 6.0
_DEFAULT_CELL_SIZE_FT = 0.5


def perpendicular_sample_points(x1, y1, x2, y2, offset_ft):
    """Returns ((ax, ay), (bx, by)) - two points offset `offset_ft` to each
    side of the segment's midpoint, perpendicular to the segment. A
    degenerate (zero-length) segment falls back to a perpendicular of (1, 0)
    so callers always get two distinct points.
    """
    mid_x = (x1 + x2) / 2.0
    mid_y = (y1 + y2) / 2.0
    dx = x2 - x1
    dy = y2 - y1
    length = math.sqrt(dx * dx + dy * dy)
    if length == 0.0:
        perp_x, perp_y = 1.0, 0.0
    else:
        perp_x, perp_y = -dy / length, dx / length
    point_a = (mid_x + perp_x * offset_ft, mid_y + perp_y * offset_ft)
    point_b = (mid_x - perp_x * offset_ft, mid_y - perp_y * offset_ft)
    return point_a, point_b


def classify_by_room_adjacency(room_sides):
    """room_sides: {wall_key: (side_a_has_room, side_b_has_room)}. Returns
    the set of wall_keys classified exterior - a wall enclosed by a Room on
    both sides is interior; anything else (one side, or neither) is
    exterior.
    """
    return set(
        wall_key for wall_key, (side_a, side_b) in room_sides.items()
        if not (side_a and side_b))


def classify_by_boundary_trace(wall_segments, offset_ft=1.5, cell_size_ft=_DEFAULT_CELL_SIZE_FT):
    """wall_segments: [(wall_key, x1, y1, x2, y2, half_width_ft), ...] for
    every dimensionable wall in the view. Returns the set of wall_keys
    classified exterior - a wall is exterior if EITHER of its two
    perpendicular sample points (offset clear of its own thickness) lands
    in space reachable from the grid's border without crossing a wall.
    """
    if not wall_segments:
        return set()

    bounds = _grid_bounds(wall_segments, cell_size_ft)
    blocked = _rasterize_walls(wall_segments, bounds)
    outside = _flood_fill_outside(blocked, bounds)

    exterior = set()
    for wall_key, x1, y1, x2, y2, half_width_ft in wall_segments:
        sample_offset = half_width_ft + offset_ft
        point_a, point_b = perpendicular_sample_points(x1, y1, x2, y2, sample_offset)
        if _is_outside(point_a, outside, bounds) or _is_outside(point_b, outside, bounds):
            exterior.add(wall_key)
    return exterior


def _grid_bounds(wall_segments, cell_size_ft):
    xs = [x for _wk, x1, y1, x2, y2, _hw in wall_segments for x in (x1, x2)]
    ys = [y for _wk, x1, y1, x2, y2, _hw in wall_segments for y in (y1, y2)]
    min_x = min(xs) - _GRID_MARGIN_FT
    max_x = max(xs) + _GRID_MARGIN_FT
    min_y = min(ys) - _GRID_MARGIN_FT
    max_y = max(ys) + _GRID_MARGIN_FT
    cols = int(math.ceil((max_x - min_x) / cell_size_ft)) + 1
    rows = int(math.ceil((max_y - min_y) / cell_size_ft)) + 1
    return {u"min_x": min_x, u"min_y": min_y, u"cols": cols, u"rows": rows, u"cell_size_ft": cell_size_ft}


def _cell_index(x, y, bounds):
    col = int((x - bounds[u"min_x"]) / bounds[u"cell_size_ft"])
    row = int((y - bounds[u"min_y"]) / bounds[u"cell_size_ft"])
    col = max(0, min(bounds[u"cols"] - 1, col))
    row = max(0, min(bounds[u"rows"] - 1, row))
    return col, row


def _point_segment_distance(px, py, x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        ex, ey = px - x1, py - y1
        return math.sqrt(ex * ex + ey * ey)
    t = ((px - x1) * dx + (py - y1) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    ex, ey = px - closest_x, py - closest_y
    return math.sqrt(ex * ex + ey * ey)


def _rasterize_walls(wall_segments, bounds):
    cols, rows = bounds[u"cols"], bounds[u"rows"]
    cell_size_ft = bounds[u"cell_size_ft"]
    blocked = [[False] * cols for _ in range(rows)]
    for _wall_key, x1, y1, x2, y2, half_width_ft in wall_segments:
        margin = half_width_ft + cell_size_ft
        min_col, min_row = _cell_index(min(x1, x2) - margin, min(y1, y2) - margin, bounds)
        max_col, max_row = _cell_index(max(x1, x2) + margin, max(y1, y2) + margin, bounds)
        for row in range(min_row, max_row + 1):
            cell_y = bounds[u"min_y"] + (row + 0.5) * cell_size_ft
            for col in range(min_col, max_col + 1):
                if blocked[row][col]:
                    continue
                cell_x = bounds[u"min_x"] + (col + 0.5) * cell_size_ft
                if _point_segment_distance(cell_x, cell_y, x1, y1, x2, y2) <= half_width_ft:
                    blocked[row][col] = True
    return blocked


def _flood_fill_outside(blocked, bounds):
    cols, rows = bounds[u"cols"], bounds[u"rows"]
    outside = [[False] * cols for _ in range(rows)]
    queue = []

    def _seed(col, row):
        if not blocked[row][col] and not outside[row][col]:
            outside[row][col] = True
            queue.append((col, row))

    for col in range(cols):
        _seed(col, 0)
        _seed(col, rows - 1)
    for row in range(rows):
        _seed(0, row)
        _seed(cols - 1, row)

    head = 0
    while head < len(queue):
        col, row = queue[head]
        head += 1
        for d_col, d_row in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n_col, n_row = col + d_col, row + d_row
            if 0 <= n_col < cols and 0 <= n_row < rows \
                    and not blocked[n_row][n_col] and not outside[n_row][n_col]:
                outside[n_row][n_col] = True
                queue.append((n_col, n_row))
    return outside


def _is_outside(point, outside, bounds):
    col, row = _cell_index(point[0], point[1], bounds)
    return outside[row][col]
