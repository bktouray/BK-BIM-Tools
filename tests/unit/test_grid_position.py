# -*- coding: utf-8 -*-
from bkbim.domain.models.grid_info import ORIENTATION_HORIZONTAL, ORIENTATION_VERTICAL
from bkbim.domain.models.grid_position import GridPositionInfo, letter_name, plan_renumber


def test_letter_name_covers_a_to_z():
    assert letter_name(0) == "A"
    assert letter_name(25) == "Z"


def test_letter_name_rolls_over_to_double_letters():
    assert letter_name(26) == "AA"
    assert letter_name(27) == "AB"
    assert letter_name(51) == "AZ"
    assert letter_name(52) == "BA"


def test_plan_renumber_orders_vertical_grids_left_to_right():
    grids = [
        GridPositionInfo(ref="right", orientation=ORIENTATION_VERTICAL, coord=30.0),
        GridPositionInfo(ref="left", orientation=ORIENTATION_VERTICAL, coord=0.0),
        GridPositionInfo(ref="middle", orientation=ORIENTATION_VERTICAL, coord=15.0),
    ]
    plan = plan_renumber(grids)

    assert plan == [("left", "A"), ("middle", "B"), ("right", "C")]


def test_plan_renumber_orders_horizontal_grids_top_to_bottom():
    # Higher Y = further "up"/top on plan, so the highest coord gets "1".
    grids = [
        GridPositionInfo(ref="bottom", orientation=ORIENTATION_HORIZONTAL, coord=0.0),
        GridPositionInfo(ref="top", orientation=ORIENTATION_HORIZONTAL, coord=30.0),
        GridPositionInfo(ref="middle", orientation=ORIENTATION_HORIZONTAL, coord=15.0),
    ]
    plan = plan_renumber(grids)

    assert plan == [("top", "1"), ("middle", "2"), ("bottom", "3")]


def test_plan_renumber_handles_both_orientations_independently():
    grids = [
        GridPositionInfo(ref="V1", orientation=ORIENTATION_VERTICAL, coord=0.0),
        GridPositionInfo(ref="V2", orientation=ORIENTATION_VERTICAL, coord=10.0),
        GridPositionInfo(ref="H1", orientation=ORIENTATION_HORIZONTAL, coord=10.0),
        GridPositionInfo(ref="H2", orientation=ORIENTATION_HORIZONTAL, coord=0.0),
    ]
    plan = dict(plan_renumber(grids))

    assert plan == {"V1": "A", "V2": "B", "H1": "1", "H2": "2"}


def test_plan_renumber_rolls_over_past_z_for_many_vertical_grids():
    grids = [
        GridPositionInfo(ref="g{0}".format(i), orientation=ORIENTATION_VERTICAL, coord=float(i))
        for i in range(27)
    ]
    plan = plan_renumber(grids)

    assert plan[25] == ("g25", "Z")
    assert plan[26] == ("g26", "AA")


def test_plan_renumber_returns_empty_list_for_no_grids():
    assert plan_renumber([]) == []
