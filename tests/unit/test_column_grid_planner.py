# -*- coding: utf-8 -*-
"""Covers structural column/footing dimensioning: grouping columns into rows by
proximity to a grid line (used only by MODE_CONTINUOUS_NO_GRID), and
MODE_GRID_AND_COLUMN, where each column gets its own independent per-axis pair of
dimensions - a detail (near face -> grid -> far face) and, further out, an
overall (that SAME column's own two faces, no grid) - never chained to another
column and never spanning multiple columns. Product owner, 2026-07-06, corrected
TWICE same day after live use: first, the original design chained
MODE_GRID_AND_COLUMN across the whole row (wrong); then, its "overall" string
spanned first-to-last column across a row (also wrong - it should be per column,
same as the detail dimension it sits alongside).
"""
from bkbim.domain.dimensioning.column_grid_planner import (
    MODE_CONTINUOUS_NO_GRID,
    MODE_GRID_AND_COLUMN,
    MODE_GRID_ONLY,
    MODE_OVERALL_ONLY,
    group_columns_by_row,
    plan_structural_dimensions,
)
from bkbim.domain.geometry.units import mm_to_ft
from bkbim.domain.models.axis_faces import AxisFaces
from bkbim.domain.models.dimension_plan import DimensionPlan
from bkbim.domain.models.grid_info import BUBBLE_P0, ORIENTATION_HORIZONTAL, ORIENTATION_VERTICAL, GridInfo
from bkbim.domain.standards.standard import Standard


def _col(label, x_lo, x_hi, y_lo, y_hi):
    return {
        "axis_faces_x": AxisFaces(ref_lo=label + "-xlo", ref_hi=label + "-xhi", coord_lo=x_lo, coord_hi=x_hi),
        "axis_faces_y": AxisFaces(ref_lo=label + "-ylo", ref_hi=label + "-yhi", coord_lo=y_lo, coord_hi=y_hi),
        "center_x": (x_lo + x_hi) / 2.0,
        "center_y": (y_lo + y_hi) / 2.0,
        "min_x": x_lo, "max_x": x_hi, "min_y": y_lo, "max_y": y_hi,
    }


def _v_grid(name, coord):
    return GridInfo(ref=u"v-" + name, name=name, orientation=ORIENTATION_VERTICAL,
                     coord=coord, p0=(coord, 0.0), p1=(coord, 40.0), bubble_end=BUBBLE_P0)


def _h_grid(name, coord):
    return GridInfo(ref=u"h-" + name, name=name, orientation=ORIENTATION_HORIZONTAL,
                     coord=coord, p0=(0.0, coord), p1=(40.0, coord), bubble_end=BUBBLE_P0)


def _standard(**overrides):
    return Standard(name=u"Test", **overrides)


# --- group_columns_by_row (still used for row grouping in both modes) ---

def test_group_skips_grid_with_fewer_than_two_columns():
    cols = [{"center_y": 0.0}]
    rows = group_columns_by_row(cols, [_h_grid("A", 0.0)], "center_y", max_snap_distance_ft=1.0)
    assert rows == []


def test_group_forms_a_row_from_columns_snapped_to_the_same_grid():
    cols = [{"center_y": 0.05}, {"center_y": -0.05}]
    rows = group_columns_by_row(cols, [_h_grid("A", 0.0)], "center_y", max_snap_distance_ft=1.0)
    assert len(rows) == 1
    grid, matched = rows[0]
    assert grid.name == "A"
    assert len(matched) == 2


def test_group_excludes_a_column_beyond_snap_tolerance():
    cols = [{"center_y": 0.0}, {"center_y": 0.0}, {"center_y": 1000.0}]
    rows = group_columns_by_row(cols, [_h_grid("A", 0.0)], "center_y", max_snap_distance_ft=1.0)
    assert len(rows[0][1]) == 2


def test_group_no_grids_of_that_orientation_produces_no_rows():
    cols = [{"center_y": 0.0}, {"center_y": 0.0}]
    assert group_columns_by_row(cols, [], "center_y", max_snap_distance_ft=1.0) == []


# --- MODE_CONTINUOUS_NO_GRID (unaffected by the correction) ---

def test_continuous_mode_chains_column_faces_with_no_grid_refs():
    cols = [
        _col("C1", 0.0, 1.0, -0.5, 0.5),
        _col("C2", 5.0, 6.0, -0.5, 0.5),
        _col("C3", 10.0, 11.0, -0.5, 0.5),
    ]
    grids = [_h_grid("A", 0.0), _v_grid("1", 0.5), _v_grid("2", 5.5), _v_grid("3", 10.5)]
    plans = plan_structural_dimensions(cols, grids, MODE_CONTINUOUS_NO_GRID, _standard())

    x_plans = [p for p in plans if p.axis == "x"]
    assert len(x_plans) == 1
    plan = x_plans[0]
    assert plan.kind == DimensionPlan.KIND_COLUMN_ROW_CHAIN
    assert plan.refs == ["C1-xlo", "C1-xhi", "C2-xlo", "C2-xhi", "C3-xlo", "C3-xhi"]
    assert not any(r.startswith("v-") or r.startswith("h-") for r in plan.refs)


def test_continuous_mode_produces_no_overall_plan():
    cols = [_col("C1", 0.0, 1.0, -0.5, 0.5), _col("C2", 5.0, 6.0, -0.5, 0.5)]
    grids = [_h_grid("A", 0.0)]
    plans = plan_structural_dimensions(cols, grids, MODE_CONTINUOUS_NO_GRID, _standard())
    assert all(p.kind != DimensionPlan.KIND_COLUMN_OVERALL for p in plans)


# --- MODE_GRID_AND_COLUMN: individual per-column, per-axis dimensions ---

def test_grid_and_column_mode_gives_each_column_its_own_dimension_per_axis():
    cols = [
        _col("C1", 0.0, 1.0, -0.5, 0.5),
        _col("C2", 5.0, 6.0, -0.5, 0.5),
    ]
    grids = [_h_grid("A", 0.0), _v_grid("1", 0.5), _v_grid("2", 5.5)]
    plans = plan_structural_dimensions(cols, grids, MODE_GRID_AND_COLUMN, _standard())

    # 2 columns x 2 axes = 4 individual dimensions, plus 1 overall (one row, x-axis).
    individual = [p for p in plans if p.kind != DimensionPlan.KIND_COLUMN_OVERALL]
    assert len(individual) == 4
    # Never chained: every individual plan touches exactly one column's own refs.
    for p in individual:
        assert len(p.refs) <= 3
        assert not any(r == "C1-xlo" for r in p.refs) or not any(r == "C2-xlo" for r in p.refs)


def test_grid_and_column_mode_inside_span_grid_gives_face_grid_face_stopping_there():
    cols = [_col("C1", 0.0, 1.0, -0.5, 0.5), _col("C2", 5.0, 6.0, -0.5, 0.5)]
    grids = [_h_grid("A", 0.0), _v_grid("1", 0.5), _v_grid("2", 5.5)]
    plans = plan_structural_dimensions(cols, grids, MODE_GRID_AND_COLUMN, _standard())

    x_dims = [p for p in plans if p.axis == "x" and p.kind == DimensionPlan.KIND_INSIDE_CHAIN]
    assert len(x_dims) == 2
    refs_per_plan = sorted([tuple(p.refs) for p in x_dims])
    assert refs_per_plan == [("C1-xlo", "v-1", "C1-xhi"), ("C2-xlo", "v-2", "C2-xhi")]


def test_grid_and_column_mode_never_chains_two_columns_into_one_dimension():
    cols = [
        _col("C1", 0.0, 1.0, -0.5, 0.5),
        _col("C2", 5.0, 6.0, -0.5, 0.5),
        _col("C3", 10.0, 11.0, -0.5, 0.5),
    ]
    grids = [_h_grid("A", 0.0), _v_grid("1", 0.5), _v_grid("2", 5.5), _v_grid("3", 10.5)]
    plans = plan_structural_dimensions(cols, grids, MODE_GRID_AND_COLUMN, _standard())

    individual = [p for p in plans if p.kind != DimensionPlan.KIND_COLUMN_OVERALL]
    assert len(individual) == 6  # 3 columns x 2 axes
    for p in individual:
        column_labels = set(r.split("-")[0] for r in p.refs if r.startswith("C"))
        assert len(column_labels) == 1  # exactly one column's own refs, never two


def test_grid_and_column_mode_no_crossing_grid_gives_plain_faces_for_both_dims():
    cols = [_col("C1", 0.0, 1.0, -0.5, 0.5)]
    grids = [_h_grid("A", 0.0)]  # no vertical grids at all
    plans = plan_structural_dimensions(cols, grids, MODE_GRID_AND_COLUMN, _standard())

    x_dims = [p for p in plans if p.axis == "x"]
    assert len(x_dims) == 2  # detail (no grid nearby -> plain overall kind) + column overall
    assert all(p.refs == ["C1-xlo", "C1-xhi"] for p in x_dims)
    kinds = sorted(p.kind for p in x_dims)
    assert kinds == sorted([DimensionPlan.KIND_OVERALL, DimensionPlan.KIND_COLUMN_OVERALL])


def test_grid_and_column_mode_single_column_still_gets_its_own_overall():
    # A lone column (no row partner) still gets both its detail dimension AND
    # its own overall - the overall is per-column now, not per-row, so it never
    # needed a row partner in the first place.
    cols = [_col("C1", 0.0, 1.0, -0.5, 0.5)]
    grids = [_h_grid("A", 0.0), _v_grid("1", 0.5)]
    plans = plan_structural_dimensions(cols, grids, MODE_GRID_AND_COLUMN, _standard())

    assert any(p.kind == DimensionPlan.KIND_INSIDE_CHAIN and p.refs == ["C1-xlo", "v-1", "C1-xhi"]
               for p in plans)
    overall = [p for p in plans if p.kind == DimensionPlan.KIND_COLUMN_OVERALL and p.axis == "x"]
    assert len(overall) == 1
    assert overall[0].refs == ["C1-xlo", "C1-xhi"]


def test_grid_and_column_mode_overall_is_per_column_not_a_row_span():
    cols = [
        _col("C1", 0.0, 1.0, -0.5, 0.5),
        _col("C2", 5.0, 6.0, -0.5, 0.5),
        _col("C3", 10.0, 11.0, -0.5, 0.5),
    ]
    grids = [_h_grid("A", 0.0), _v_grid("1", 0.5), _v_grid("2", 5.5), _v_grid("3", 10.5)]
    plans = plan_structural_dimensions(cols, grids, MODE_GRID_AND_COLUMN, _standard())

    overall = [p for p in plans if p.kind == DimensionPlan.KIND_COLUMN_OVERALL and p.axis == "x"]
    # One overall PER COLUMN (3), not one spanning first-to-last across the row.
    assert len(overall) == 3
    refs_per_plan = sorted([tuple(p.refs) for p in overall])
    assert refs_per_plan == [("C1-xlo", "C1-xhi"), ("C2-xlo", "C2-xhi"), ("C3-xlo", "C3-xhi")]


def test_grid_and_column_perp_placement_uses_the_columns_own_perpendicular_extent():
    # Each column's per-axis dimension is offset from ITS OWN bounding box in the
    # other axis, not from a shared row line - a column with a wider footprint in
    # Y places its X-axis dimension further out than a narrower one would.
    cols = [_col("C1", 0.0, 1.0, -2.0, 2.0)]
    grids = [_h_grid("A", 0.0), _v_grid("1", 0.5)]
    std = _standard(offset_first_mm=800.0, default_side=-1)
    plans = plan_structural_dimensions(cols, grids, MODE_GRID_AND_COLUMN, std)

    x_dim = [p for p in plans if p.axis == "x"][0]
    assert x_dim.perp_pos == -2.0 - mm_to_ft(800.0)


# --- both row directions / spacing for the overall string ---

def test_both_orientations_produce_independent_individual_dimensions_in_one_call():
    x_row_cols = [_col("X1", 0.0, 1.0, -0.5, 0.5), _col("X2", 5.0, 6.0, -0.5, 0.5)]
    y_row_cols = [_col("Y1", 20.0, 21.0, 0.0, 1.0), _col("Y2", 20.0, 21.0, 5.0, 6.0)]
    grids = [_h_grid("A", 0.0), _v_grid("1", 20.5)]
    plans = plan_structural_dimensions(
        x_row_cols + y_row_cols, grids, MODE_CONTINUOUS_NO_GRID, _standard())

    assert len(plans) == 2
    axes = sorted(p.axis for p in plans)
    assert axes == ["x", "y"]


def test_overall_offset_and_gap_placement_is_relative_to_the_columns_own_extent():
    # The overall's perp position is offset+gap from the COLUMN's own bounding box
    # in the other axis (min_y/max_y for an x-axis dimension) - not from a grid's
    # coordinate, since the overall no longer spans/anchors to a row at all.
    cols = [_col("C1", 0.0, 1.0, -3.0, 3.0)]
    grids = [_h_grid("A", 0.0), _v_grid("1", 0.5)]
    std = _standard(structural_chain_offset_mm=800.0, structural_chain_gap_mm=700.0, default_side=-1)
    plans = plan_structural_dimensions(cols, grids, MODE_GRID_AND_COLUMN, std)

    overall = [p for p in plans if p.kind == DimensionPlan.KIND_COLUMN_OVERALL and p.axis == "x"][0]
    assert overall.perp_pos == -3.0 - mm_to_ft(800.0 + 700.0)


def test_column_with_unresolved_axis_faces_on_one_axis_still_gets_the_other():
    cols = [
        {"axis_faces_x": None, "axis_faces_y": AxisFaces("a", "b", -0.5, 0.5),
         "center_x": 0.5, "center_y": 0.0, "min_x": 0.0, "max_x": 1.0, "min_y": -0.5, "max_y": 0.5},
    ]
    grids = [_h_grid("A", 0.0)]
    plans = plan_structural_dimensions(cols, grids, MODE_GRID_AND_COLUMN, _standard())
    # Detail + overall for the resolved (y) axis only; nothing for the unresolved x axis.
    assert len(plans) == 2
    assert all(p.axis == "y" for p in plans)


# --- MODE_GRID_ONLY / MODE_OVERALL_ONLY (Slab Dimensions' two independent
# modes - genuinely per-FACE, never per-axis-shared, and duplicated at both
# perpendicular offsets so every CORNER gets its own witness dimension, not
# just every side; see column_grid_planner's module docstring for the
# 2026-07-07 "closest grid to that specific corner, not the center grid to
# the outmost edge" / "every slab corner, not just the 4 sides" corrections) ---

def test_grid_only_mode_gives_two_dimensions_per_resolvable_face():
    cols = [_col("C1", 0.0, 1.0, -0.5, 0.5), _col("C2", 5.0, 6.0, -0.5, 0.5)]
    grids = [_h_grid("A", 0.0), _v_grid("1", 0.5), _v_grid("2", 5.5)]
    plans = plan_structural_dimensions(cols, grids, MODE_GRID_ONLY, _standard())

    # 2 columns x 2 axes x 2 faces x 2 corner-positions = 16 - every corner
    # gets its own witness dimension, not just every side.
    assert len(plans) == 16
    assert all(p.kind == DimensionPlan.KIND_SLAB_EDGE_TO_GRID for p in plans)
    assert all(len(p.refs) == 2 for p in plans)


def test_grid_only_mode_references_each_faces_own_closest_grid_not_a_shared_center_grid():
    # A single wide element (standing in for a slab spanning several bays):
    # its low face is much closer to "near-lo," its high face much closer to
    # "near-hi" - a "nearest to the element's CENTER" algorithm would instead
    # pick "center" for both faces (the bug this mode was rebuilt to fix).
    cols = [_col("S1", 0.0, 10.0, -0.5, 0.5)]
    grids = [_h_grid("A", 0.0), _v_grid("near-lo", 0.3), _v_grid("center", 5.0), _v_grid("near-hi", 9.7)]
    plans = plan_structural_dimensions(cols, grids, MODE_GRID_ONLY, _standard())

    x_dims = [p for p in plans if p.axis == "x"]
    assert len(x_dims) == 4  # one per face, duplicated at both corners of that face
    refs = sorted(set([tuple(p.refs) for p in x_dims]))
    assert refs == [("S1-xlo", "v-near-lo"), ("v-near-hi", "S1-xhi")]
    assert not any("center" in r for p in x_dims for r in p.refs)


def test_grid_only_mode_duplicates_each_faces_dimension_at_both_corners():
    cols = [_col("C1", 0.0, 1.0, -3.0, 3.0)]
    grids = [_h_grid("A", 0.0), _v_grid("1", 0.5)]
    std = _standard(structural_chain_offset_mm=800.0)
    plans = plan_structural_dimensions(cols, grids, MODE_GRID_ONLY, std)

    x_dims = [p for p in plans if p.axis == "x"]
    assert len(x_dims) == 4  # 2 faces (both nearest to the one grid) x 2 corners each
    perp_positions = sorted(set(p.perp_pos for p in x_dims))
    assert perp_positions == sorted([-3.0 - mm_to_ft(800.0), 3.0 + mm_to_ft(800.0)])
    for perp in perp_positions:
        refs_at_perp = sorted(tuple(p.refs) for p in x_dims if p.perp_pos == perp)
        assert refs_at_perp == [("C1-xlo", "v-1"), ("v-1", "C1-xhi")]


def test_grid_only_mode_skips_a_face_with_no_grid_of_matching_orientation():
    cols = [_col("C1", 0.0, 1.0, -0.5, 0.5)]
    grids = [_h_grid("A", 0.0)]  # no vertical grids at all
    plans = plan_structural_dimensions(cols, grids, MODE_GRID_ONLY, _standard())

    assert all(p.axis != "x" for p in plans)  # nothing to reference on X
    y_dims = [p for p in plans if p.axis == "y"]
    assert len(y_dims) == 4  # both Y faces still resolve against grid "A", each at both corners


def test_overall_only_mode_places_the_same_span_on_both_sides_of_each_axis():
    cols = [_col("C1", 0.0, 1.0, -3.0, 3.0)]
    grids = [_h_grid("A", 0.0), _v_grid("1", 0.5)]
    std = _standard(structural_chain_offset_mm=800.0)
    plans = plan_structural_dimensions(cols, grids, MODE_OVERALL_ONLY, std)

    x_dims = [p for p in plans if p.axis == "x"]
    assert len(x_dims) == 2  # same overall span, once per side - "all sides" coverage
    assert all(p.kind == DimensionPlan.KIND_COLUMN_OVERALL for p in x_dims)
    assert all(p.refs == ["C1-xlo", "C1-xhi"] for p in x_dims)
    perp_positions = sorted(p.perp_pos for p in x_dims)
    assert perp_positions == sorted([-3.0 - mm_to_ft(800.0), 3.0 + mm_to_ft(800.0)])


def test_overall_only_mode_gives_four_dimensions_for_two_columns():
    cols = [_col("C1", 0.0, 1.0, -0.5, 0.5), _col("C2", 5.0, 6.0, -0.5, 0.5)]
    grids = [_h_grid("A", 0.0), _v_grid("1", 0.5), _v_grid("2", 5.5)]
    plans = plan_structural_dimensions(cols, grids, MODE_OVERALL_ONLY, _standard())

    # 2 columns x 2 axes x 2 sides = 8, no grid references anywhere.
    assert len(plans) == 8
    assert all(p.kind == DimensionPlan.KIND_COLUMN_OVERALL for p in plans)
    x_refs = sorted([tuple(p.refs) for p in plans if p.axis == "x"])
    assert x_refs == [("C1-xlo", "C1-xhi"), ("C1-xlo", "C1-xhi"), ("C2-xlo", "C2-xhi"), ("C2-xlo", "C2-xhi")]
