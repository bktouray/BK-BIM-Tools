# -*- coding: utf-8 -*-
"""Covers merging wall-end faces + opening jamb faces into ordered chains, split
into separate runs at every crossing wall (product owner feedback 2026-07-05: a
crossing wall's own thickness must never appear as a segment - break there and
resume after it). Correctness bar validated against a real door (1200mm) and
window (2000mm) opening on 2026-07-05.
"""
from bkbim.domain.dimensioning.wall_run_planner import (
    plan_wall_overall,
    plan_wall_perpendicular_chain,
    plan_wall_runs,
)
from bkbim.domain.models.axis_faces import AxisFaces
from bkbim.domain.models.dimension_plan import DimensionPlan


def test_none_wall_faces_returns_empty_list():
    assert plan_wall_runs(None, [], [], "x", 0.0) == []


def test_wall_with_no_openings_or_crossings_is_one_plan_start_to_end():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    plans = plan_wall_runs(wall_faces, [], [], "x", 5.0)

    assert len(plans) == 1
    assert plans[0].kind == DimensionPlan.KIND_WALL_RUN
    assert plans[0].refs == ["start", "end"]
    assert plans[0].line_coord_lo == 0.0
    assert plans[0].line_coord_hi == 20.0
    assert plans[0].perp_pos == 5.0


def test_wall_with_one_opening_and_no_crossings_is_still_one_plan():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    door = AxisFaces(ref_lo="door-near", ref_hi="door-far", coord_lo=8.0, coord_hi=12.0)

    plans = plan_wall_runs(wall_faces, [door], [], "x", 5.0)

    assert len(plans) == 1
    assert plans[0].refs == ["start", "door-near", "door-far", "end"]


def test_unmatched_openings_are_omitted_not_guessed():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    door = AxisFaces(ref_lo="door-near", ref_hi="door-far", coord_lo=8.0, coord_hi=12.0)

    plans = plan_wall_runs(wall_faces, [door, None], [], "x", 5.0)

    assert plans[0].refs == ["start", "door-near", "door-far", "end"]


# --- crossing walls split the run; their own thickness never appears ---

def test_single_crossing_produces_two_separate_plans():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    crossing = AxisFaces(ref_lo="cross-near", ref_hi="cross-far", coord_lo=9.0, coord_hi=10.0)

    plans = plan_wall_runs(wall_faces, [], [crossing], "x", 5.0)

    assert len(plans) == 2
    assert plans[0].refs == ["start", "cross-near"]
    assert plans[1].refs == ["cross-far", "end"]
    # The crossing wall's own 1.0-ft thickness never appears as a segment - only
    # its near/far faces as the boundary of two SEPARATE dimensions.
    assert plans[0].line_coord_hi == 9.0
    assert plans[1].line_coord_lo == 10.0


def test_two_crossings_produce_three_separate_plans():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    crossing_a = AxisFaces(ref_lo="a-near", ref_hi="a-far", coord_lo=5.0, coord_hi=5.5)
    crossing_b = AxisFaces(ref_lo="b-near", ref_hi="b-far", coord_lo=14.0, coord_hi=14.5)

    plans = plan_wall_runs(wall_faces, [], [crossing_a, crossing_b], "x", 5.0)

    assert len(plans) == 3
    assert plans[0].refs == ["start", "a-near"]
    assert plans[1].refs == ["a-far", "b-near"]
    assert plans[2].refs == ["b-far", "end"]


def test_crossings_out_of_order_are_still_sorted_correctly():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    crossing_a = AxisFaces(ref_lo="a-near", ref_hi="a-far", coord_lo=5.0, coord_hi=5.5)
    crossing_b = AxisFaces(ref_lo="b-near", ref_hi="b-far", coord_lo=14.0, coord_hi=14.5)

    # Passed in reverse order - planner must sort by position itself.
    plans = plan_wall_runs(wall_faces, [], [crossing_b, crossing_a], "x", 5.0)

    assert len(plans) == 3
    assert plans[0].refs == ["start", "a-near"]
    assert plans[2].refs == ["b-far", "end"]


def test_opening_falls_into_the_correct_run_segment():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    crossing = AxisFaces(ref_lo="cross-near", ref_hi="cross-far", coord_lo=9.0, coord_hi=10.0)
    door = AxisFaces(ref_lo="door-near", ref_hi="door-far", coord_lo=2.0, coord_hi=4.0)
    window = AxisFaces(ref_lo="win-near", ref_hi="win-far", coord_lo=15.0, coord_hi=17.0)

    plans = plan_wall_runs(wall_faces, [door, window], [crossing], "x", 5.0)

    assert len(plans) == 2
    assert plans[0].refs == ["start", "door-near", "door-far", "cross-near"]
    assert plans[1].refs == ["cross-far", "win-near", "win-far", "end"]


def test_adjacent_crossings_with_no_gap_produce_no_degenerate_run():
    # Two crossing walls essentially back to back (e.g. meeting at a corner) -
    # must not emit a zero-length plan for the nonexistent gap between them.
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    crossing_a = AxisFaces(ref_lo="a-near", ref_hi="a-far", coord_lo=9.0, coord_hi=10.0)
    crossing_b = AxisFaces(ref_lo="b-near", ref_hi="b-far", coord_lo=10.001, coord_hi=11.0)

    plans = plan_wall_runs(wall_faces, [], [crossing_a, crossing_b], "x", 5.0)

    assert len(plans) == 2
    assert plans[0].refs == ["start", "a-near"]
    assert plans[1].refs == ["b-far", "end"]


def test_crossing_right_at_wall_end_produces_no_degenerate_plan_there():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    crossing = AxisFaces(ref_lo="cross-near", ref_hi="cross-far", coord_lo=0.001, coord_hi=1.0)

    plans = plan_wall_runs(wall_faces, [], [crossing], "x", 5.0)

    # No plan for the near-zero gap between "start" and the crossing's near face.
    assert len(plans) == 1
    assert plans[0].refs == ["cross-far", "end"]


def test_axis_and_perp_pos_are_passed_through_to_every_plan():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    crossing = AxisFaces(ref_lo="cross-near", ref_hi="cross-far", coord_lo=9.0, coord_hi=10.0)

    plans = plan_wall_runs(wall_faces, [], [crossing], "y", -3.5)

    for plan in plans:
        assert plan.axis == "y"
        assert plan.perp_pos == -3.5


# --- plan_wall_perpendicular_chain (middle string, exterior walls only) ---

def test_perpendicular_chain_with_no_crossings_is_just_the_wall_ends():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    plan = plan_wall_perpendicular_chain(wall_faces, [], "x", 5.0)

    assert plan.kind == DimensionPlan.KIND_WALL_PERPENDICULAR_CHAIN
    assert plan.refs == ["start", "end"]
    assert plan.line_coord_lo == 0.0
    assert plan.line_coord_hi == 20.0
    assert plan.perp_pos == 5.0


def test_perpendicular_chain_never_splits_unlike_plan_wall_runs():
    # Same inputs that made plan_wall_runs produce TWO separate plans -
    # this must stay ONE continuous chain instead.
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    crossing = AxisFaces(ref_lo="cross-near", ref_hi="cross-far", coord_lo=9.0, coord_hi=10.0)

    plan = plan_wall_perpendicular_chain(wall_faces, [crossing], "x", 5.0)

    assert plan is not None
    assert plan.refs == ["start", "cross-near", "cross-far", "end"]


def test_perpendicular_chain_with_multiple_crossings_sorted_correctly():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    crossing_a = AxisFaces(ref_lo="a-near", ref_hi="a-far", coord_lo=5.0, coord_hi=5.5)
    crossing_b = AxisFaces(ref_lo="b-near", ref_hi="b-far", coord_lo=14.0, coord_hi=14.5)

    # Passed out of order - planner must sort itself.
    plan = plan_wall_perpendicular_chain(wall_faces, [crossing_b, crossing_a], "x", 5.0)

    assert plan.refs == ["start", "a-near", "a-far", "b-near", "b-far", "end"]


def test_perpendicular_chain_skips_none_crossings():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    crossing = AxisFaces(ref_lo="cross-near", ref_hi="cross-far", coord_lo=9.0, coord_hi=10.0)

    plan = plan_wall_perpendicular_chain(wall_faces, [None, crossing], "x", 5.0)

    assert plan.refs == ["start", "cross-near", "cross-far", "end"]


def test_perpendicular_chain_returns_none_for_missing_wall_faces():
    assert plan_wall_perpendicular_chain(None, [], "x", 5.0) is None


def test_perpendicular_chain_dedupes_a_crossing_right_at_the_wall_end():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    crossing = AxisFaces(ref_lo="cross-near", ref_hi="cross-far", coord_lo=0.001, coord_hi=1.0)

    plan = plan_wall_perpendicular_chain(wall_faces, [crossing], "x", 5.0)

    # "start" and "cross-near" are coincident (0.0 vs 0.001) - only one kept.
    assert plan.refs == ["start", "cross-far", "end"]


# --- plan_wall_overall (outermost string, exterior walls only) ---

def test_overall_is_just_the_walls_own_two_end_faces():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    plan = plan_wall_overall(wall_faces, "x", 8.0)

    assert plan.kind == DimensionPlan.KIND_WALL_OVERALL
    assert plan.refs == ["start", "end"]
    assert plan.line_coord_lo == 0.0
    assert plan.line_coord_hi == 20.0
    assert plan.perp_pos == 8.0


def test_overall_returns_none_for_missing_wall_faces():
    assert plan_wall_overall(None, "x", 8.0) is None
