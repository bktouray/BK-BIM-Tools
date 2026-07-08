# -*- coding: utf-8 -*-
from bkbim.domain.models.grid_info import (
    BUBBLE_P0,
    BUBBLE_P1,
    ORIENTATION_HORIZONTAL,
    ORIENTATION_VERTICAL,
    GridInfo,
)


def test_grid_info_holds_fields_as_given():
    gi = GridInfo(
        ref="grid-A",
        name="A",
        orientation=ORIENTATION_VERTICAL,
        coord=12.0,
        p0=(12.0, 0.0),
        p1=(12.0, 40.0),
        bubble_end=BUBBLE_P1,
    )

    assert gi.name == "A"
    assert gi.orientation == ORIENTATION_VERTICAL
    assert gi.coord == 12.0
    assert gi.p0 == (12.0, 0.0)
    assert gi.p1 == (12.0, 40.0)
    assert gi.bubble_end == BUBBLE_P1


def test_orientation_constants_are_distinct():
    assert ORIENTATION_HORIZONTAL != ORIENTATION_VERTICAL


def test_bubble_constants_are_distinct():
    assert BUBBLE_P0 != BUBBLE_P1


def test_repr_works_with_plain_int_coord():
    # Regression test: see test_element_info.test_repr_works_with_plain_int_coordinates
    gi = GridInfo(
        ref=None, name="A", orientation=ORIENTATION_VERTICAL,
        coord=12, p0=(12, 0), p1=(12, 40), bubble_end=BUBBLE_P1,
    )
    assert "A" in repr(gi)
