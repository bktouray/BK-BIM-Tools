# -*- coding: utf-8 -*-
"""Covers the classic v5 problem-space scenarios (grid inside/on-edge/outside the
element span) plus cases the pure logic must also get right: no grid in range,
reversed face-coordinate input, and both side offsets. This is the correctness bar
for Phase 1 Stage 3 - see PHASE_1_PLAN.md Sec 2.
"""
from bkbim.domain.geometry.units import mm_to_ft
from bkbim.domain.dimensioning.planner import plan_element_axis
from bkbim.domain.models.axis_faces import AxisFaces
from bkbim.domain.models.dimension_plan import DimensionPlan
from bkbim.domain.models.grid_info import GridInfo, ORIENTATION_VERTICAL, BUBBLE_P0
from bkbim.domain.standards.standard import Standard


def _grid(name, coord):
    return GridInfo(
        ref=u"grid-" + name, name=name, orientation=ORIENTATION_VERTICAL,
        coord=coord, p0=(coord, 0.0), p1=(coord, 40.0), bubble_end=BUBBLE_P0,
    )


def _standard(**overrides):
    return Standard(name=u"Test", **overrides)


def test_no_faces_returns_none():
    std = _standard()
    faces = AxisFaces(ref_lo=None, ref_hi=None, coord_lo=0.0, coord_hi=10.0)
    assert plan_element_axis("x", faces, 5.0, 0.0, 3.0, [], std) is None


def test_no_grids_produces_overall():
    std = _standard()
    faces = AxisFaces(ref_lo="lo", ref_hi="hi", coord_lo=0.0, coord_hi=10.0)

    plan = plan_element_axis("x", faces, 5.0, 0.0, 3.0, [], std)

    assert plan.kind == DimensionPlan.KIND_OVERALL
    assert plan.refs == ["lo", "hi"]
    assert plan.line_coord_lo == 0.0
    assert plan.line_coord_hi == 10.0


def test_grid_beyond_max_snap_distance_produces_overall():
    std = _standard(max_snap_distance_mm=1000.0)  # ~3.28 ft
    faces = AxisFaces(ref_lo="lo", ref_hi="hi", coord_lo=0.0, coord_hi=10.0)
    far_grid = _grid("Z", coord=5.0 + mm_to_ft(5000.0))

    plan = plan_element_axis("x", faces, 5.0, 0.0, 3.0, [far_grid], std)

    assert plan.kind == DimensionPlan.KIND_OVERALL


def test_grid_strictly_inside_produces_inside_chain_lo_grid_hi_order():
    std = _standard()
    faces = AxisFaces(ref_lo="lo", ref_hi="hi", coord_lo=0.0, coord_hi=10.0)
    grid = _grid("A", coord=4.0)

    plan = plan_element_axis("x", faces, 5.0, 0.0, 3.0, [grid], std)

    assert plan.kind == DimensionPlan.KIND_INSIDE_CHAIN
    assert plan.refs == ["lo", "grid-A", "hi"]


def test_grid_on_lo_edge_snaps_with_grid_first():
    std = _standard()
    faces = AxisFaces(ref_lo="lo", ref_hi="hi", coord_lo=0.0, coord_hi=10.0)
    grid = _grid("A", coord=0.0)

    plan = plan_element_axis("x", faces, 5.0, 0.0, 3.0, [grid], std)

    assert plan.kind == DimensionPlan.KIND_SNAP_ON_EDGE
    assert plan.refs == ["grid-A", "hi"]


def test_grid_on_hi_edge_snaps_with_grid_last():
    std = _standard()
    faces = AxisFaces(ref_lo="lo", ref_hi="hi", coord_lo=0.0, coord_hi=10.0)
    grid = _grid("A", coord=10.0)

    plan = plan_element_axis("x", faces, 5.0, 0.0, 3.0, [grid], std)

    assert plan.kind == DimensionPlan.KIND_SNAP_ON_EDGE
    assert plan.refs == ["lo", "grid-A"]


def test_degenerate_grid_on_both_edges_falls_back_to_overall():
    std = _standard(zero_tolerance_mm=5000.0)  # huge tolerance forces both-edge case
    faces = AxisFaces(ref_lo="lo", ref_hi="hi", coord_lo=0.0, coord_hi=0.01)
    grid = _grid("A", coord=0.005)

    plan = plan_element_axis("x", faces, 0.005, 0.0, 3.0, [grid], std)

    assert plan.kind == DimensionPlan.KIND_OVERALL
    assert plan.refs == ["lo", "hi"]


def test_grid_below_element_span_produces_outside_chain_grid_first():
    std = _standard()
    faces = AxisFaces(ref_lo="lo", ref_hi="hi", coord_lo=10.0, coord_hi=20.0)
    grid = _grid("A", coord=5.0)  # below the element's span

    plan = plan_element_axis("x", faces, 15.0, 0.0, 3.0, [grid], std)

    assert plan.kind == DimensionPlan.KIND_OUTSIDE_CHAIN
    assert plan.refs == ["grid-A", "lo", "hi"]
    assert plan.line_coord_lo == 5.0
    assert plan.line_coord_hi == 20.0


def test_grid_above_element_span_produces_outside_chain_grid_last():
    std = _standard()
    faces = AxisFaces(ref_lo="lo", ref_hi="hi", coord_lo=0.0, coord_hi=10.0)
    grid = _grid("A", coord=15.0)  # above the element's span

    plan = plan_element_axis("x", faces, 5.0, 0.0, 3.0, [grid], std)

    assert plan.kind == DimensionPlan.KIND_OUTSIDE_CHAIN
    assert plan.refs == ["lo", "hi", "grid-A"]
    assert plan.line_coord_lo == 0.0
    assert plan.line_coord_hi == 15.0


def test_reversed_face_coordinates_are_normalized():
    # ref_lo/ref_hi swapped relative to their actual coordinates - planner must not
    # assume input order matches coordinate order.
    std = _standard()
    faces = AxisFaces(ref_lo="hi-side", ref_hi="lo-side", coord_lo=10.0, coord_hi=0.0)
    grid = _grid("A", coord=4.0)

    plan = plan_element_axis("x", faces, 5.0, 0.0, 3.0, [grid], std)

    assert plan.kind == DimensionPlan.KIND_INSIDE_CHAIN
    assert plan.refs == ["lo-side", "grid-A", "hi-side"]


def test_default_side_minus_one_offsets_below_perp_lo():
    std = _standard(offset_first_mm=800.0, default_side=-1)
    faces = AxisFaces(ref_lo="lo", ref_hi="hi", coord_lo=0.0, coord_hi=10.0)

    plan = plan_element_axis("x", faces, 5.0, perp_lo=2.0, perp_hi=5.0, grids=[], standard=std)

    assert plan.perp_pos == 2.0 - mm_to_ft(800.0)


def test_default_side_plus_one_offsets_above_perp_hi():
    std = _standard(offset_first_mm=800.0, default_side=1)
    faces = AxisFaces(ref_lo="lo", ref_hi="hi", coord_lo=0.0, coord_hi=10.0)

    plan = plan_element_axis("x", faces, 5.0, perp_lo=2.0, perp_hi=5.0, grids=[], standard=std)

    assert plan.perp_pos == 5.0 + mm_to_ft(800.0)


def test_nearest_of_multiple_grids_is_chosen():
    std = _standard()
    faces = AxisFaces(ref_lo="lo", ref_hi="hi", coord_lo=0.0, coord_hi=10.0)
    near = _grid("NEAR", coord=4.2)
    far = _grid("FAR", coord=1.0)

    plan = plan_element_axis("x", faces, 4.0, 0.0, 3.0, [far, near], std)

    assert plan.kind == DimensionPlan.KIND_INSIDE_CHAIN
    assert plan.refs == ["lo", "grid-NEAR", "hi"]
