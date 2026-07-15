# -*- coding: utf-8 -*-
from bkbim.domain.mep.models.routing_plan import FittingPlan
from bkbim.domain.mep.sanitary.fitting_rules import select_fitting


def test_branch_junction_always_gets_a_45_degree_wye_never_a_square_tee():
    fitting = select_fitting((0, 0, 0), 100, 100, is_branch_junction=True)
    assert fitting.kind == FittingPlan.KIND_WYE_45
    assert fitting.angle_deg == 45.0


def test_branch_junction_wins_even_with_a_diameter_change():
    fitting = select_fitting((0, 0, 0), 100, 75, is_branch_junction=True)
    assert fitting.kind == FittingPlan.KIND_WYE_45
    assert fitting.diameter_mm == 100


def test_diameter_change_without_branch_gets_a_reducer():
    fitting = select_fitting((0, 0, 0), 100, 75)
    assert fitting.kind == FittingPlan.KIND_REDUCER
    assert fitting.diameter_mm == 100


def test_direction_change_gets_an_elbow():
    fitting = select_fitting((0, 0, 0), 100, 100, direction_change_deg=90.0)
    assert fitting.kind == FittingPlan.KIND_ELBOW
    assert fitting.angle_deg == 90.0


def test_straight_same_diameter_no_branch_needs_no_fitting():
    assert select_fitting((0, 0, 0), 100, 100) is None


def test_tiny_direction_change_within_tolerance_needs_no_fitting():
    assert select_fitting((0, 0, 0), 100, 100, direction_change_deg=1.0) is None
