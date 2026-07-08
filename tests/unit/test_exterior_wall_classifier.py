# -*- coding: utf-8 -*-
"""Covers the two exterior-wall auto-detection methods (product owner,
2026-07-08: "is it possible to just autodetect the building boundary, or do
I have to differentiate exterior and interior walls?") - Room-adjacency
classification, and the geometric boundary-trace fallback used when a view
has no Rooms placed.
"""
from bkbim.domain.dimensioning.exterior_wall_classifier import (
    classify_by_boundary_trace,
    classify_by_room_adjacency,
    perpendicular_sample_points,
)


def test_perpendicular_sample_points_offsets_a_horizontal_segment_in_y():
    point_a, point_b = perpendicular_sample_points(0.0, 0.0, 20.0, 0.0, offset_ft=2.0)

    assert sorted([point_a, point_b]) == [(10.0, -2.0), (10.0, 2.0)]


def test_perpendicular_sample_points_offsets_a_vertical_segment_in_x():
    point_a, point_b = perpendicular_sample_points(0.0, 0.0, 0.0, 10.0, offset_ft=2.0)

    assert sorted([point_a, point_b]) == [(-2.0, 5.0), (2.0, 5.0)]


def test_perpendicular_sample_points_handles_zero_length_segment():
    # Degenerate input shouldn't blow up - falls back to a fixed perpendicular.
    point_a, point_b = perpendicular_sample_points(5.0, 5.0, 5.0, 5.0, offset_ft=1.0)

    assert point_a != point_b


def test_classify_by_room_adjacency_wall_between_two_rooms_is_interior():
    room_sides = {"partition": (True, True)}

    result = classify_by_room_adjacency(room_sides)

    assert result == set()


def test_classify_by_room_adjacency_wall_with_room_on_one_side_is_exterior():
    room_sides = {"exterior_wall": (True, False)}

    result = classify_by_room_adjacency(room_sides)

    assert result == {"exterior_wall"}


def test_classify_by_room_adjacency_wall_with_no_room_either_side_is_exterior():
    # e.g. a wall bounding an un-roomed space (garage, void) on both sides -
    # still not enclosed by a Room, so it's not classified interior.
    room_sides = {"unroomed_wall": (False, False)}

    result = classify_by_room_adjacency(room_sides)

    assert result == {"unroomed_wall"}


def test_classify_by_room_adjacency_mixed_set():
    room_sides = {
        "south": (True, False),
        "north": (True, False),
        "partition": (True, True),
    }

    result = classify_by_room_adjacency(room_sides)

    assert result == {"south", "north"}


def _rectangle_walls(width=20.0, height=10.0, half_width_ft=0.5):
    # A closed rectangular footprint, walls named by compass side.
    return [
        ("south", 0.0, 0.0, width, 0.0, half_width_ft),
        ("north", 0.0, height, width, height, half_width_ft),
        ("west", 0.0, 0.0, 0.0, height, half_width_ft),
        ("east", width, 0.0, width, height, half_width_ft),
    ]


def test_classify_by_boundary_trace_rectangle_is_all_exterior():
    wall_segments = _rectangle_walls()

    result = classify_by_boundary_trace(wall_segments)

    assert result == {"south", "north", "west", "east"}


def test_classify_by_boundary_trace_interior_partition_is_excluded():
    # Same rectangle, plus a partition wall splitting it into two rooms -
    # the partition's own sample points land inside the footprint on both
    # sides, so it must NOT be classified exterior.
    wall_segments = _rectangle_walls(width=16.0, height=10.0)
    wall_segments.append(("partition", 8.0, 0.0, 8.0, 10.0, 0.5))

    result = classify_by_boundary_trace(wall_segments)

    assert result == {"south", "north", "west", "east"}
    assert "partition" not in result


def test_classify_by_boundary_trace_l_shaped_footprint():
    # An L-shaped footprint (a 10x10 square with a 5x5 notch bitten out of
    # the top-right corner) - every wall, including the two forming the
    # notch, is still on the building's outer boundary.
    wall_segments = [
        ("bottom", 0.0, 0.0, 10.0, 0.0, 0.5),
        ("right_lower", 10.0, 0.0, 10.0, 5.0, 0.5),
        ("notch_horizontal", 10.0, 5.0, 5.0, 5.0, 0.5),
        ("notch_vertical", 5.0, 5.0, 5.0, 10.0, 0.5),
        ("top", 5.0, 10.0, 0.0, 10.0, 0.5),
        ("left", 0.0, 10.0, 0.0, 0.0, 0.5),
    ]

    result = classify_by_boundary_trace(wall_segments)

    assert result == {"bottom", "right_lower", "notch_horizontal", "notch_vertical", "top", "left"}
