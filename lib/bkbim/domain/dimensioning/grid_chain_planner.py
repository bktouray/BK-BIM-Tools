# -*- coding: utf-8 -*-
"""Grid chain planner: dimensions grids with two strings per side.

Matches the convention confirmed against real reference drawings (product owner's
GROUND.pdf / str.pdf, 2026-07-05): an inner SEQUENTIAL string (grid -> grid -> grid)
plus an outer OVERALL string (first grid -> last grid), mirrored on BOTH ends of the
perpendicular span - top+bottom for vertical grids, left+right for horizontal grids -
not just one side.
"""

from bkbim.domain.geometry.units import mm_to_ft
from bkbim.domain.models.dimension_plan import DimensionPlan
from bkbim.domain.models.grid_info import ORIENTATION_HORIZONTAL, ORIENTATION_VERTICAL


def compute_bounding_span(elements, grids):
    """Returns (x_span, y_span), each an (lo, hi) tuple, or (None, None) if nothing
    to measure. Used to place grid chains at the actual edges of what's selected
    ("all sides"). Prefers the selected elements' extent (the real building
    footprint); falls back to the grids' own line endpoints if no elements were
    selected alongside the grids.
    """
    xs = []
    ys = []
    for e in elements:
        xs.append(e.min_x)
        xs.append(e.max_x)
        ys.append(e.min_y)
        ys.append(e.max_y)

    if not xs:
        for g in grids:
            xs.append(g.p0[0])
            xs.append(g.p1[0])
            ys.append(g.p0[1])
            ys.append(g.p1[1])

    if not xs or not ys:
        return None, None

    return (min(xs), max(xs)), (min(ys), max(ys))


def plan_grid_chains(grids, x_span, y_span, standard):
    """Plans grid dimension chains for both orientations found in `grids`.

    grids: list[GridInfo] - any mix of orientations; grouped internally.
    x_span: (lo, hi) extent along X - perpendicular axis for HORIZONTAL grids
            (they run along Y, so their chains sit at the X extremes).
    y_span: (lo, hi) extent along Y - perpendicular axis for VERTICAL grids
            (they run along X, so their chains sit at the Y extremes).
    standard: Standard profile - `grid_chain_offset_mm` (inner string distance from
              the span edge) and `grid_chain_gap_mm` (extra gap to the outer string)
              are the user-adjustable spacing values from the options UI.

    Returns list[DimensionPlan] - up to 4 plans per orientation present (2 sides x
    2 strings), fewer if an orientation has fewer than 2 grids or its span is None.
    """
    plans = []
    if y_span is not None:
        plans.extend(_plan_for_orientation(grids, ORIENTATION_VERTICAL, u"x", y_span, standard))
    if x_span is not None:
        plans.extend(_plan_for_orientation(grids, ORIENTATION_HORIZONTAL, u"y", x_span, standard))
    return plans


def _plan_for_orientation(grids, orientation, measuring_axis, perp_span, standard):
    same_orientation = sorted(
        (g for g in grids if g.orientation == orientation),
        key=lambda g: g.coord,
    )
    if len(same_orientation) < 2:
        return []

    line_lo = same_orientation[0].coord
    line_hi = same_orientation[-1].coord
    refs_sequential = [g.ref for g in same_orientation]
    refs_overall = [same_orientation[0].ref, same_orientation[-1].ref]

    offset_ft = mm_to_ft(standard.grid_chain_offset_mm)
    gap_ft = mm_to_ft(standard.grid_chain_gap_mm)
    span_lo, span_hi = perp_span

    plans = []
    for side in (-1, 1):
        base = span_lo if side < 0 else span_hi
        inner_perp = (base - offset_ft) if side < 0 else (base + offset_ft)
        outer_perp = (base - (offset_ft + gap_ft)) if side < 0 else (base + (offset_ft + gap_ft))

        plans.append(DimensionPlan(
            kind=DimensionPlan.KIND_GRID_SEQUENTIAL, refs=refs_sequential,
            axis=measuring_axis, line_coord_lo=line_lo, line_coord_hi=line_hi,
            perp_pos=inner_perp,
        ))
        plans.append(DimensionPlan(
            kind=DimensionPlan.KIND_GRID_OVERALL, refs=refs_overall,
            axis=measuring_axis, line_coord_lo=line_lo, line_coord_hi=line_hi,
            perp_pos=outer_perp,
        ))

    return plans
