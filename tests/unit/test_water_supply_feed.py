# -*- coding: utf-8 -*-
from bkbim.domain.mep.routing.water_supply_feed import (
    corridor_offset_vector,
    feed_points_from_main_to_trunk,
    offset_corridor_points,
    valve_bypass_points,
)


def _close(a, b, tolerance=0.001):
    return abs(a - b) <= tolerance


def test_ceiling_valve_bypass_is_200mm_and_rises_opposite_drop_side():
    incoming = (0.0, 1000.0, 2400.0)
    valve = (0.0, 0.0, 1800.0)
    trunk_z = 2450.0

    pre, pre_low, post_low, post_high = valve_bypass_points(
        incoming, valve, trunk_z, approach_point=(0.0, 1.0, trunk_z))

    assert pre[1] == 100.0
    assert pre_low[1] == 100.0
    assert post_low[1] == -100.0
    assert post_high[1] == -100.0
    assert _close(abs(post_low[1] - pre_low[1]), 200.0)
    assert pre_low[2] == valve[2]
    assert post_low[2] == valve[2]
    assert post_high[2] == trunk_z


def test_feed_points_finish_at_trunk_origin_without_overlapping_first_trunk_leg():
    incoming = (0.0, 1000.0, 2400.0)
    valve = (0.0, 0.0, 1800.0)
    trunk_origin = (-500.0, 0.0, 2450.0)
    trunk_next = (-500.0, 1000.0, 2450.0)

    points = feed_points_from_main_to_trunk(
        incoming, valve, trunk_origin, trunk_next_point=trunk_next)

    assert points[-1] == trunk_origin
    final_start = points[-2]
    final_end = points[-1]
    # First trunk segment runs along Y at x=-500. The final feed segment
    # should enter it along X, not overlap it along the same Y-axis line.
    assert final_start[1] == final_end[1]
    assert final_start[0] != final_end[0]


def test_corridor_offset_vector_offsets_perpendicular_to_first_leg():
    corridor = [(0.0, 0.0, 2000.0), (0.0, 1000.0, 2000.0)]

    offset = corridor_offset_vector(corridor, 50.0)

    assert offset == (-50.0, 0.0)
    assert offset_corridor_points(corridor, 50.0) == [
        (-50.0, 0.0, 2000.0),
        (-50.0, 1000.0, 2000.0),
    ]


def test_no_bypass_when_main_and_trunk_are_not_above_valve():
    assert valve_bypass_points(
        (0.0, 1000.0, 1700.0),
        (0.0, 0.0, 1800.0),
        2450.0,
        approach_point=(0.0, 1.0, 2450.0)) is None
