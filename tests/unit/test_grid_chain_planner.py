# -*- coding: utf-8 -*-
"""Covers the convention confirmed against real reference drawings: two strings per
side (sequential + overall), mirrored on both ends ("all sides"), for each grid
orientation present - and that vertical/horizontal grids each use the CORRECT
perpendicular span (a real bug caught before it shipped: using one span for both
orientations is wrong on any non-square building).
"""
from bkbim.domain.dimensioning.grid_chain_planner import compute_bounding_span, plan_grid_chains
from bkbim.domain.geometry.units import mm_to_ft
from bkbim.domain.models.dimension_plan import DimensionPlan
from bkbim.domain.models.element_info import ElementInfo
from bkbim.domain.models.grid_info import BUBBLE_P0, ORIENTATION_HORIZONTAL, ORIENTATION_VERTICAL, GridInfo
from bkbim.domain.standards.standard import Standard


def _v_grid(name, coord, y0=0.0, y1=40.0):
    return GridInfo(ref=u"v-" + name, name=name, orientation=ORIENTATION_VERTICAL,
                     coord=coord, p0=(coord, y0), p1=(coord, y1), bubble_end=BUBBLE_P0)


def _h_grid(name, coord, x0=0.0, x1=40.0):
    return GridInfo(ref=u"h-" + name, name=name, orientation=ORIENTATION_HORIZONTAL,
                     coord=coord, p0=(x0, coord), p1=(x1, coord), bubble_end=BUBBLE_P0)


def _standard(**overrides):
    return Standard(name=u"Test", **overrides)


def test_no_grids_produces_no_plans():
    assert plan_grid_chains([], (0.0, 10.0), (0.0, 5.0), _standard()) == []


def test_single_grid_in_orientation_produces_no_plans_for_it():
    plans = plan_grid_chains([_v_grid("A", 1.0)], (0.0, 10.0), (0.0, 5.0), _standard())
    assert plans == []


def test_two_vertical_grids_produce_four_plans_two_sides_two_strings():
    grids = [_v_grid("A", 0.0), _v_grid("B", 10.0)]
    plans = plan_grid_chains(grids, x_span=(0.0, 10.0), y_span=(0.0, 5.0), standard=_standard())

    assert len(plans) == 4
    kinds = sorted(p.kind for p in plans)
    assert kinds == sorted([
        DimensionPlan.KIND_GRID_SEQUENTIAL, DimensionPlan.KIND_GRID_SEQUENTIAL,
        DimensionPlan.KIND_GRID_OVERALL, DimensionPlan.KIND_GRID_OVERALL,
    ])
    assert all(p.axis == "x" for p in plans)


def test_vertical_grids_use_y_span_not_x_span():
    # Regression test for the cross-orientation span bug: vertical grids run along
    # X, so their perpendicular offset must come from y_span, never x_span.
    grids = [_v_grid("A", 0.0), _v_grid("B", 10.0)]
    x_span = (-999.0, 999.0)  # deliberately way off - must NOT be used
    y_span = (0.0, 5.0)
    plans = plan_grid_chains(grids, x_span=x_span, y_span=y_span, standard=_standard())

    for p in plans:
        assert abs(p.perp_pos) < 900.0  # nowhere near the x_span values


def test_horizontal_grids_use_x_span_not_y_span():
    grids = [_h_grid("1", 0.0), _h_grid("2", 8.0)]
    x_span = (0.0, 5.0)
    y_span = (-999.0, 999.0)  # deliberately way off - must NOT be used
    plans = plan_grid_chains(grids, x_span=x_span, y_span=y_span, standard=_standard())

    for p in plans:
        assert abs(p.perp_pos) < 900.0


def test_both_orientations_present_produce_eight_plans_each_using_its_own_span():
    # Small, explicit offsets so the expected perp_pos ranges are unambiguous.
    std = _standard(grid_chain_offset_mm=100.0, grid_chain_gap_mm=100.0)  # ~0.33ft + ~0.33ft
    grids = [_v_grid("A", 0.0), _v_grid("B", 10.0), _h_grid("1", 0.0), _h_grid("2", 8.0)]
    plans = plan_grid_chains(grids, x_span=(0.0, 20.0), y_span=(0.0, 5.0), standard=std)

    assert len(plans) == 8
    x_axis_plans = [p for p in plans if p.axis == "x"]  # vertical grids -> use y_span (0-5)
    y_axis_plans = [p for p in plans if p.axis == "y"]  # horizontal grids -> use x_span (0-20)

    assert len(x_axis_plans) == 4
    assert len(y_axis_plans) == 4
    # y_span (0-5) + <1ft of offset/gap stays well under 10; x_span (0-20) does not.
    assert all(abs(p.perp_pos) < 10.0 for p in x_axis_plans)
    assert any(p.perp_pos > 15.0 for p in y_axis_plans)


def test_missing_span_for_an_orientation_skips_it():
    grids = [_v_grid("A", 0.0), _v_grid("B", 10.0), _h_grid("1", 0.0), _h_grid("2", 8.0)]
    plans = plan_grid_chains(grids, x_span=None, y_span=(0.0, 5.0), standard=_standard())

    assert all(p.axis == "x" for p in plans)  # horizontal grids skipped (no x_span)
    assert len(plans) == 4


def test_sequential_refs_are_coordinate_ordered_regardless_of_input_order():
    grids = [_v_grid("C", 20.0), _v_grid("A", 0.0), _v_grid("B", 10.0)]
    plans = plan_grid_chains(grids, (0.0, 20.0), (0.0, 5.0), _standard())

    sequential = [p for p in plans if p.kind == DimensionPlan.KIND_GRID_SEQUENTIAL]
    assert sequential[0].refs == ["v-A", "v-B", "v-C"]


def test_overall_refs_are_first_and_last_only():
    grids = [_v_grid("A", 0.0), _v_grid("B", 10.0), _v_grid("C", 20.0)]
    plans = plan_grid_chains(grids, (0.0, 20.0), (0.0, 5.0), _standard())

    overall = [p for p in plans if p.kind == DimensionPlan.KIND_GRID_OVERALL]
    assert overall[0].refs == ["v-A", "v-C"]


def test_line_span_covers_first_to_last_grid_coord():
    grids = [_v_grid("A", 2.0), _v_grid("B", 30.0)]
    plans = plan_grid_chains(grids, (0.0, 40.0), (0.0, 5.0), _standard())

    for p in plans:
        assert p.line_coord_lo == 2.0
        assert p.line_coord_hi == 30.0


def test_offsets_are_symmetric_on_both_sides():
    grids = [_v_grid("A", 0.0), _v_grid("B", 10.0)]
    std = _standard(grid_chain_offset_mm=1500.0, grid_chain_gap_mm=700.0)
    span_lo, span_hi = 2.0, 8.0
    plans = plan_grid_chains(grids, x_span=(0.0, 10.0), y_span=(span_lo, span_hi), standard=std)

    offset_ft = mm_to_ft(1500.0)
    gap_ft = mm_to_ft(700.0)

    inner_plans = [p for p in plans if p.kind == DimensionPlan.KIND_GRID_SEQUENTIAL]
    outer_plans = [p for p in plans if p.kind == DimensionPlan.KIND_GRID_OVERALL]

    inner_positions = sorted(p.perp_pos for p in inner_plans)
    outer_positions = sorted(p.perp_pos for p in outer_plans)

    assert inner_positions == sorted([span_lo - offset_ft, span_hi + offset_ft])
    assert outer_positions == sorted([span_lo - offset_ft - gap_ft, span_hi + offset_ft + gap_ft])


def test_outer_string_is_further_from_the_span_than_inner_string():
    span_lo, span_hi = 0.0, 5.0
    grids = [_v_grid("A", 0.0), _v_grid("B", 10.0)]
    plans = plan_grid_chains(grids, x_span=(0.0, 10.0), y_span=(span_lo, span_hi), standard=_standard())

    below_inner = min(p.perp_pos for p in plans if p.kind == DimensionPlan.KIND_GRID_SEQUENTIAL and p.perp_pos < span_lo)
    below_outer = min(p.perp_pos for p in plans if p.kind == DimensionPlan.KIND_GRID_OVERALL and p.perp_pos < span_lo)
    assert below_outer < below_inner

    above_inner = max(p.perp_pos for p in plans if p.kind == DimensionPlan.KIND_GRID_SEQUENTIAL and p.perp_pos > span_hi)
    above_outer = max(p.perp_pos for p in plans if p.kind == DimensionPlan.KIND_GRID_OVERALL and p.perp_pos > span_hi)
    assert above_outer > above_inner


# --- compute_bounding_span ---

def test_bounding_span_from_elements():
    elements = [
        ElementInfo(ref="w1", category="Wall", min_x=0.0, max_x=20.0, min_y=1.0, max_y=9.0),
        ElementInfo(ref="w2", category="Wall", min_x=-5.0, max_x=15.0, min_y=2.0, max_y=12.0),
    ]
    x_span, y_span = compute_bounding_span(elements, [])
    assert x_span == (-5.0, 20.0)
    assert y_span == (1.0, 12.0)


def test_bounding_span_falls_back_to_grid_endpoints_when_no_elements():
    grids = [_v_grid("A", 0.0, y0=0.0, y1=40.0), _h_grid("1", 5.0, x0=-2.0, x1=30.0)]
    x_span, y_span = compute_bounding_span([], grids)
    assert x_span == (-2.0, 30.0)
    assert y_span == (0.0, 40.0)


def test_bounding_span_none_when_nothing_selected():
    assert compute_bounding_span([], []) == (None, None)
