# -*- coding: utf-8 -*-
"""Structural column/footing dimensioning: two independent modes, per product
owner (2026-07-06, corrected twice same day after live use):

- MODE_GRID_AND_COLUMN: EACH column gets its own independent dimension per axis
  (length + width) - near face -> grid -> far face, stopping there. It never
  chains into the next column ("dimension individual columns on both sides...
  measure from one face to grid then finish at the opposite face and stop there
  and not continue as a string to other columns" - the original "one continuous
  string across the whole row" design was wrong). This reuses, unchanged, the
  exact same on-edge/inside/outside-of-span classification the original Auto
  Dimension tool already established for walls/columns
  (`planner.py:plan_element_axis`) - no new logic needed for the hard part.
  A second OVERALL dimension is added per column per axis, further out - the
  SAME column's own two faces, no grid reference - not a first-to-last-column
  span across the row ("I want overall dimension on individual columns just
  like the column from face to grid to face" - the first version wrongly spanned
  the whole row; corrected to be per-column, matching the detail dimension it
  sits alongside).
- MODE_CONTINUOUS_NO_GRID: unchanged - one continuous column-face-to-column-face
  chain per row (grid used only to group/order the row, never referenced in the
  output), no overall string (the chain's own span already is one). Confirmed
  working as-is by the product owner.
- MODE_GRID_ONLY / MODE_OVERALL_ONLY (Slab Dimensions only - never used by
  Column/Beam/Footing): REDESIGNED 2026-07-07 after live use exposed both were
  wrong for a slab spanning several grid bays. First cut (2026-07-06) reused
  MODE_GRID_AND_COLUMN's per-AXIS machinery, which picks ONE grid nearest the
  element's CENTER and shares it across both faces on that axis - fine for a
  column that sits within one bay, wrong for a slab: "I want the reference to
  be taken from the closest grid to that specific slab corner and same for
  every corner, not the center grid to the outmost edge." Also only produced
  2 dimensions total (one per axis) when 4 physical edges exist: "I don't
  want it on just two sides, I want it on all sides of the slab, every single
  edge must be measured."

  Both modes are now genuinely per-FACE (4 faces: min_x/max_x/min_y/max_y),
  never per-axis-shared, AND each face's dimension is placed at BOTH
  perpendicular offsets rather than just one (2026-07-07, same-day follow-up:
  "I want it to take every slab corner, not just the 4 sides") - so every one
  of the 4 CORNERS gets its own witness dimension in each direction, not just
  each SIDE once:
  - MODE_GRID_ONLY ("Grid to slab edges"): each face independently finds its
    OWN closest grid of matching orientation - no "is it inside the span"
    classification at all, no shared center-grid - then that face-to-grid
    dimension is duplicated at both perpendicular offsets (up to 8 total for
    a rectangular slab: 2 faces per axis x 2 corner-positions each) -
    `_plan_grid_to_each_edge`.
  - MODE_OVERALL_ONLY ("All edges of the slab"): each axis's face-to-face
    span (no grid) is placed TWICE - once just outside the low face, once
    just outside the high face - so all 4 physical edges get their own
    adjacent witness dimension instead of one shared pair sitting on a single
    side - `_plan_all_edges_no_grid`.

Pure domain logic (ADR-0001) - no Revit types.
"""

from bkbim.domain.dimensioning.planner import plan_element_axis
from bkbim.domain.geometry.units import mm_to_ft
from bkbim.domain.models.dimension_plan import DimensionPlan
from bkbim.domain.models.grid_info import ORIENTATION_HORIZONTAL, ORIENTATION_VERTICAL

MODE_GRID_AND_COLUMN = u"grid_and_column"
MODE_CONTINUOUS_NO_GRID = u"continuous_no_grid"
MODE_GRID_ONLY = u"grid_only"
MODE_OVERALL_ONLY = u"overall_only"

# (row_axis, axis_faces_key, axis_center_key, perp_center_key, row_grid_orientation)
# - a row running along X is grouped by HORIZONTAL grids (using each column's
# center_y to find the nearest one); a row along Y is the mirror image.
_ROW_AXES = (
    (u"x", u"axis_faces_x", u"center_x", u"center_y", ORIENTATION_HORIZONTAL),
    (u"y", u"axis_faces_y", u"center_y", u"center_x", ORIENTATION_VERTICAL),
)


def group_columns_by_row(columns, row_orientation_grids, perp_key, max_snap_distance_ft):
    """Groups `columns` into rows, one per grid line in `row_orientation_grids`
    that a column snaps to (nearest grid within tolerance, by the column's
    `perp_key` coordinate - its centerline position along the axis the grid's own
    position varies along).

    columns: list of opaque per-column dicts - only read via `perp_key` lookups
             done here; never introspected beyond that.
    row_orientation_grids: GridInfo list, already filtered to one orientation.

    Returns list[(GridInfo, [matching columns, in original order])], keyed by
    each grid's `name` (assumed unique - Revit grid names are), skipping any grid
    with fewer than 2 snapped columns (nothing to chain/span).
    """
    if not row_orientation_grids:
        return []

    rows_by_name = {}
    for col in columns:
        best_grid, best_dist = None, None
        for g in row_orientation_grids:
            dist = abs(col[perp_key] - g.coord)
            if best_dist is None or dist < best_dist:
                best_grid, best_dist = g, dist
        if best_grid is None or best_dist > max_snap_distance_ft:
            continue
        if best_grid.name not in rows_by_name:
            rows_by_name[best_grid.name] = (best_grid, [])
        rows_by_name[best_grid.name][1].append(col)

    return [(grid, cols) for grid, cols in rows_by_name.values() if len(cols) >= 2]


# (axis, axis_faces_key, center_key, perp_lo_key, perp_hi_key) - perp_lo/hi come
# from the column's OWN bounding box in the axis PERPENDICULAR to `axis` (mirrors
# plan_element_axis's perp_lo/perp_hi parameters).
_COLUMN_AXES = (
    (u"x", u"axis_faces_x", u"center_x", u"min_y", u"max_y"),
    (u"y", u"axis_faces_y", u"center_y", u"min_x", u"max_x"),
)

# (axis, axis_faces_key, perp_lo_key, perp_hi_key) - same perp convention as
# _COLUMN_AXES, without the center_key the per-face slab functions don't need.
_EDGE_AXES = (
    (u"x", u"axis_faces_x", u"min_y", u"max_y"),
    (u"y", u"axis_faces_y", u"min_x", u"max_x"),
)


def _plan_individual_column_dimensions(columns, grids, standard):
    """MODE_GRID_AND_COLUMN: two dimensions per column per axis, never chained
    to another column - a detail dimension (near face -> grid -> far face, via
    plan_element_axis) and, further out (offset+gap), an overall dimension
    (that SAME column's own two faces, no grid) - both scoped to the one
    column, not the whole row.
    """
    v_grids = [g for g in grids if g.orientation == ORIENTATION_VERTICAL]
    h_grids = [g for g in grids if g.orientation == ORIENTATION_HORIZONTAL]
    crossing_grids_by_axis = {u"x": v_grids, u"y": h_grids}

    offset_ft = mm_to_ft(standard.structural_chain_offset_mm)
    gap_ft = mm_to_ft(standard.structural_chain_gap_mm)
    side = standard.default_side

    plans = []
    for col in columns:
        for axis, axis_faces_key, center_key, perp_lo_key, perp_hi_key in _COLUMN_AXES:
            axis_faces = col[axis_faces_key]
            if axis_faces is None:
                continue
            if axis_faces.ref_lo is None or axis_faces.ref_hi is None:
                continue

            perp_lo, perp_hi = col[perp_lo_key], col[perp_hi_key]

            detail_plan = plan_element_axis(
                axis, axis_faces, col[center_key], perp_lo, perp_hi,
                crossing_grids_by_axis[axis], standard)
            if detail_plan is not None:
                plans.append(detail_plan)

            points = sorted(
                [(axis_faces.coord_lo, axis_faces.ref_lo), (axis_faces.coord_hi, axis_faces.ref_hi)],
                key=lambda p: p[0],
            )
            coord_lo, ref_lo = points[0]
            coord_hi, ref_hi = points[1]
            overall_perp = (perp_lo - (offset_ft + gap_ft)) if side < 0 else (perp_hi + (offset_ft + gap_ft))
            plans.append(DimensionPlan(
                kind=DimensionPlan.KIND_COLUMN_OVERALL,
                refs=[ref_lo, ref_hi],
                axis=axis, line_coord_lo=coord_lo, line_coord_hi=coord_hi,
                perp_pos=overall_perp,
            ))
    return plans


def _nearest_grid_to_coord(coord, grids):
    """Like `planner._nearest_grid`, but keyed on an arbitrary coordinate (here,
    one specific FACE's own position) rather than an element's center - the
    distinction that fixes "center grid to outmost edge" for slabs spanning
    several bays.
    """
    best, best_dist = None, None
    for grid in grids:
        dist = abs(coord - grid.coord)
        if best_dist is None or dist < best_dist:
            best, best_dist = grid, dist
    return best, best_dist


def _plan_grid_to_each_edge(columns, grids, standard):
    """MODE_GRID_ONLY ("Grid to slab edges"): up to 4 dimensions per element
    (one per resolvable face), each referencing the closest grid of matching
    orientation to THAT face alone - never a grid shared between two faces on
    the same axis.
    """
    v_grids = [g for g in grids if g.orientation == ORIENTATION_VERTICAL]
    h_grids = [g for g in grids if g.orientation == ORIENTATION_HORIZONTAL]
    grids_by_axis = {u"x": v_grids, u"y": h_grids}

    offset_ft = mm_to_ft(standard.structural_chain_offset_mm)

    plans = []
    for col in columns:
        for axis, axis_faces_key, perp_lo_key, perp_hi_key in _EDGE_AXES:
            axis_faces = col[axis_faces_key]
            if axis_faces is None or axis_faces.ref_lo is None or axis_faces.ref_hi is None:
                continue

            perp_lo, perp_hi = col[perp_lo_key], col[perp_hi_key]
            matching_grids = grids_by_axis[axis]

            for coord, ref in ((axis_faces.coord_lo, axis_faces.ref_lo),
                                (axis_faces.coord_hi, axis_faces.ref_hi)):
                grid, _dist = _nearest_grid_to_coord(coord, matching_grids)
                if grid is None:
                    continue
                ordered = sorted([(coord, ref), (grid.coord, grid.ref)], key=lambda p: p[0])
                # Placed at BOTH perpendicular offsets (not just `default_side`'s
                # one) so every CORNER gets its own witness dimension, not just
                # every side - product owner, 2026-07-07: "I want it to take
                # every slab corner, not just the 4 sides."
                for perp_pos in (perp_lo - offset_ft, perp_hi + offset_ft):
                    plans.append(DimensionPlan(
                        kind=DimensionPlan.KIND_SLAB_EDGE_TO_GRID,
                        refs=[p[1] for p in ordered],
                        axis=axis, line_coord_lo=ordered[0][0], line_coord_hi=ordered[-1][0],
                        perp_pos=perp_pos,
                    ))
    return plans


def _plan_all_edges_no_grid(columns, standard):
    """MODE_OVERALL_ONLY ("All edges of the slab"): each axis's face-to-face
    span (no grid reference) is placed TWICE - once just outside the low
    face, once just outside the high face - giving all 4 physical edges their
    own adjacent witness dimension instead of one pair sitting on a single
    side.
    """
    offset_ft = mm_to_ft(standard.structural_chain_offset_mm)

    plans = []
    for col in columns:
        for axis, axis_faces_key, perp_lo_key, perp_hi_key in _EDGE_AXES:
            axis_faces = col[axis_faces_key]
            if axis_faces is None or axis_faces.ref_lo is None or axis_faces.ref_hi is None:
                continue

            points = sorted(
                [(axis_faces.coord_lo, axis_faces.ref_lo), (axis_faces.coord_hi, axis_faces.ref_hi)],
                key=lambda p: p[0],
            )
            coord_lo, ref_lo = points[0]
            coord_hi, ref_hi = points[1]
            perp_lo, perp_hi = col[perp_lo_key], col[perp_hi_key]

            for perp_pos in (perp_lo - offset_ft, perp_hi + offset_ft):
                plans.append(DimensionPlan(
                    kind=DimensionPlan.KIND_COLUMN_OVERALL,
                    refs=[ref_lo, ref_hi],
                    axis=axis, line_coord_lo=coord_lo, line_coord_hi=coord_hi,
                    perp_pos=perp_pos,
                ))
    return plans


def _plan_continuous_row_chains(columns, grids, standard):
    """MODE_CONTINUOUS_NO_GRID: one chain per row, column faces only, no grid
    references, no overall string.
    """
    max_snap_ft = mm_to_ft(standard.max_snap_distance_mm)
    offset_ft = mm_to_ft(standard.structural_chain_offset_mm)
    side = standard.default_side

    plans = []
    for row_axis, axis_faces_key, axis_center_key, perp_center_key, row_orientation in _ROW_AXES:
        row_grids = [g for g in grids if g.orientation == row_orientation]
        rows = group_columns_by_row(columns, row_grids, perp_center_key, max_snap_ft)
        for grid, cols in rows:
            cols_sorted = sorted(cols, key=lambda c: c[axis_center_key])
            axis_faces_list = [c[axis_faces_key] for c in cols_sorted]
            if any(af is None for af in axis_faces_list):
                continue

            base = grid.coord
            inner_perp = (base - offset_ft) if side < 0 else (base + offset_ft)
            chain_refs = []
            for axis_faces in axis_faces_list:
                chain_refs.append((axis_faces.coord_lo, axis_faces.ref_lo))
                chain_refs.append((axis_faces.coord_hi, axis_faces.ref_hi))
            plans.append(DimensionPlan(
                kind=DimensionPlan.KIND_COLUMN_ROW_CHAIN,
                refs=[r[1] for r in chain_refs],
                axis=row_axis, line_coord_lo=chain_refs[0][0], line_coord_hi=chain_refs[-1][0],
                perp_pos=inner_perp,
            ))
    return plans


def plan_structural_dimensions(columns, grids, mode, standard):
    """Plans structural column/footing/slab dimensions.

    columns: list of dicts, one per element, each with:
        "axis_faces_x": AxisFaces along X, or None if unresolved
        "axis_faces_y": AxisFaces along Y, or None if unresolved
        "center_x"/"center_y": element's own centerline coordinates
        "min_x"/"max_x"/"min_y"/"max_y": element's own bounding box, used to
            place each per-axis dimension's line relative to the element's own
            extent in the OTHER axis (mirrors plan_element_axis's perp_lo/hi).
    grids: GridInfo list, any mix of orientations.
    mode: MODE_GRID_AND_COLUMN | MODE_CONTINUOUS_NO_GRID | MODE_GRID_ONLY |
          MODE_OVERALL_ONLY.
    standard: Standard profile.

    Returns list[DimensionPlan].
    """
    if mode == MODE_GRID_AND_COLUMN:
        return _plan_individual_column_dimensions(columns, grids, standard)
    if mode == MODE_GRID_ONLY:
        return _plan_grid_to_each_edge(columns, grids, standard)
    if mode == MODE_OVERALL_ONLY:
        return _plan_all_edges_no_grid(columns, standard)
    return _plan_continuous_row_chains(columns, grids, standard)
