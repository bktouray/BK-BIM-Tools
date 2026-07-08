# -*- coding: utf-8 -*-
"""Traces a slab's REAL outline (not its axis-aligned bounding box) for
"All edges of the slab" mode, per product owner (2026-07-07), sent a
screenshot of a real notched/stepped footprint with the whole perimeter
traced in red: "I want dimensions to follow every slab face." The previous
bounding-box approximation (`column_grid_planner._plan_all_edges_no_grid`)
only ever produced 4 sides, wrong for any footprint that isn't a plain
rectangle - it silently collapsed steps/notches into the overall envelope.

Each straight boundary segment (an OutlineEdge - see
domain/models/outline_edge.py) gets its own dimension, measuring its own
real length. The two references for that dimension are the TWO ADJACENT
PERPENDICULAR edges that share its two corners - e.g. the TOP edge's length
(an X-direction measurement) is referenced to the LEFT edge's own face and
the RIGHT edge's own face, found by matching which edge's own coordinate and
span meet at each of the TOP edge's two endpoints. This reuses the exact
same "reference a face, not a point" technique already used everywhere else
in this codebase - no new Revit API concept, just applied per real corner
instead of per bounding-box extreme.

Axis-aligned (rectilinear) footprints only - matches the "axis-aligned
faces only" limitation already stated in reference_provider.py. A curved or
diagonal boundary segment simply isn't produced by the adapter, so it never
reaches this planner.

Pure domain logic (ADR-0001) - no Revit types.
"""

from bkbim.domain.geometry.units import mm_to_ft
from bkbim.domain.models.dimension_plan import DimensionPlan


def _other_axis(axis):
    return u"y" if axis == u"x" else u"x"


def _find_corner_match(candidates, target_coord, target_perp, tol_ft):
    """Among `candidates` (edges of the perpendicular axis), finds the one
    that shares a corner at (target_coord, target_perp) - its own coordinate
    must match `target_coord`, and `target_perp` must land on one of ITS OWN
    span endpoints (not just fall within its span - corners meet exactly).
    """
    for candidate in candidates:
        if abs(candidate.coord - target_coord) > tol_ft:
            continue
        if abs(candidate.span_lo - target_perp) <= tol_ft or abs(candidate.span_hi - target_perp) <= tol_ft:
            return candidate
    return None


def _plan_one_slab_outline(edges, offset_ft, tol_ft):
    plans = []
    for edge in edges:
        dimension_axis = _other_axis(edge.axis)
        perp_candidates = [e for e in edges if e.axis == dimension_axis]

        lo_match = _find_corner_match(perp_candidates, edge.span_lo, edge.coord, tol_ft)
        hi_match = _find_corner_match(perp_candidates, edge.span_hi, edge.coord, tol_ft)
        if lo_match is None or hi_match is None:
            continue

        perp_pos = edge.coord + edge.sign * offset_ft
        plans.append(DimensionPlan(
            kind=DimensionPlan.KIND_SLAB_OUTLINE_EDGE,
            refs=[lo_match.ref, hi_match.ref],
            axis=dimension_axis,
            line_coord_lo=edge.span_lo, line_coord_hi=edge.span_hi,
            perp_pos=perp_pos,
        ))
    return plans


def plan_slab_outline_dimensions(all_edges, standard):
    """Plans one dimension per real boundary edge, across multiple slabs.

    all_edges: list[list[OutlineEdge]] - one inner list per slab, so edges
               from different slabs never cross-match each other's corners.
    standard: Standard profile.

    Returns list[DimensionPlan].
    """
    offset_ft = mm_to_ft(standard.structural_chain_offset_mm)
    tol_ft = mm_to_ft(standard.zero_tolerance_mm)

    plans = []
    for edges in all_edges:
        plans.extend(_plan_one_slab_outline(edges, offset_ft, tol_ft))
    return plans
