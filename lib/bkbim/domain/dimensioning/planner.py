# -*- coding: utf-8 -*-
"""Dimension planner: decides which references to combine and where the line goes.

Deliberately simple for this first iteration (PHASE_1_PLAN Sec 6/7: product owner
said start simple and iterate from real testing, not invent heuristics up front).
No side-picking heuristic, no multi-row/collision handling - a dimension always goes
on the Standard's fixed `default_side`, offset by `offset_first_mm` from the
element's perpendicular extent. Only one classification is kept from the
problem-space (not from v5's code): whether a nearby grid sits on an edge, inside, or
outside the element's span, because that determines which references are even
*correct* to combine, not how the dimension looks.
"""

from bkbim.domain.geometry.units import mm_to_ft
from bkbim.domain.models.dimension_plan import DimensionPlan


def _nearest_grid(element_center, grids):
    best = None
    best_dist = None
    for grid in grids:
        dist = abs(element_center - grid.coord)
        if best_dist is None or dist < best_dist:
            best = grid
            best_dist = dist
    return best, best_dist


def plan_element_axis(axis, axis_faces, element_center, perp_lo, perp_hi, grids, standard):
    """Plans one dimension for one element along one axis.

    axis: "x" | "y"
    axis_faces: AxisFaces - the element's extreme face refs/coords along this axis
    element_center: element's centerline coordinate along this axis
    perp_lo/perp_hi: element's extent along the axis PERPENDICULAR to `axis`,
                     used to place the dimension line's offset
    grids: GridInfo list, already filtered to grids whose position varies along
           `axis` (i.e. perpendicular-orientation grids)
    standard: Standard profile (offsets/tolerances)

    Returns a DimensionPlan, or None if there isn't enough to dimension.
    """
    if axis_faces.ref_lo is None or axis_faces.ref_hi is None:
        return None

    element_points = sorted(
        [(axis_faces.coord_lo, axis_faces.ref_lo), (axis_faces.coord_hi, axis_faces.ref_hi)],
        key=lambda p: p[0],
    )
    coord_lo, ref_lo = element_points[0]
    coord_hi, ref_hi = element_points[1]

    offset_ft = mm_to_ft(standard.offset_first_mm)
    perp_pos = (perp_lo - offset_ft) if standard.default_side < 0 else (perp_hi + offset_ft)

    grid, dist = _nearest_grid(element_center, grids)
    max_snap_ft = mm_to_ft(standard.max_snap_distance_mm)

    if grid is None or dist > max_snap_ft:
        return DimensionPlan(
            kind=DimensionPlan.KIND_OVERALL,
            refs=[ref_lo, ref_hi],
            axis=axis, line_coord_lo=coord_lo, line_coord_hi=coord_hi, perp_pos=perp_pos,
        )

    zero_tol_ft = mm_to_ft(standard.zero_tolerance_mm)
    intersect_tol_ft = mm_to_ft(standard.intersect_tolerance_mm)
    intersects = (coord_lo - intersect_tol_ft) < grid.coord < (coord_hi + intersect_tol_ft)

    if not intersects:
        ordered = sorted(
            [(coord_lo, ref_lo), (coord_hi, ref_hi), (grid.coord, grid.ref)],
            key=lambda p: p[0],
        )
        return DimensionPlan(
            kind=DimensionPlan.KIND_OUTSIDE_CHAIN,
            refs=[p[1] for p in ordered],
            axis=axis, line_coord_lo=ordered[0][0], line_coord_hi=ordered[-1][0],
            perp_pos=perp_pos,
        )

    is_on_lo = abs(coord_lo - grid.coord) <= zero_tol_ft
    is_on_hi = abs(coord_hi - grid.coord) <= zero_tol_ft

    if is_on_lo and is_on_hi:
        # Degenerate: element has ~zero width at the grid position. Fall back to a
        # plain overall rather than emit a malformed duplicate-reference chain.
        return DimensionPlan(
            kind=DimensionPlan.KIND_OVERALL,
            refs=[ref_lo, ref_hi],
            axis=axis, line_coord_lo=coord_lo, line_coord_hi=coord_hi, perp_pos=perp_pos,
        )

    if is_on_lo or is_on_hi:
        refs = [grid.ref, ref_hi] if is_on_lo else [ref_lo, grid.ref]
        return DimensionPlan(
            kind=DimensionPlan.KIND_SNAP_ON_EDGE,
            refs=refs,
            axis=axis, line_coord_lo=coord_lo, line_coord_hi=coord_hi, perp_pos=perp_pos,
        )

    return DimensionPlan(
        kind=DimensionPlan.KIND_INSIDE_CHAIN,
        refs=[ref_lo, grid.ref, ref_hi],
        axis=axis, line_coord_lo=coord_lo, line_coord_hi=coord_hi, perp_pos=perp_pos,
    )
