# -*- coding: utf-8 -*-
"""Covers the product owner's screenshot scenario: a long horizontal wall (running
along X) with several perpendicular partition returns crossing it - the dimension
string should break at each, but not at unrelated, parallel, or merely-nearby walls.
"""
from bkbim.domain.dimensioning.crossing_wall_detector import find_crossing_walls
from bkbim.domain.models.element_info import ElementInfo


def _perpendicular_crossing_wall(min_x, max_x, min_y=-1.0, max_y=6.0):
    # Runs along Y (tall/thin in X) - perpendicular to a main wall running along X.
    return ElementInfo(ref="cross", category="Wall", min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y)


def _parallel_wall(min_x, max_x, min_y, max_y):
    # Runs along X (wide/thin in Y) - same axis as the main wall.
    return ElementInfo(ref="parallel", category="Wall", min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y)


def test_genuine_perpendicular_crossing_is_detected():
    main_axis, main_lo, main_hi = "x", 0.0, 20.0
    main_perp_lo, main_perp_hi = -1.0, 1.0
    candidate = _perpendicular_crossing_wall(min_x=9.8, max_x=10.2, min_y=-1.0, max_y=6.0)

    result = find_crossing_walls(main_axis, main_lo, main_hi, main_perp_lo, main_perp_hi, [candidate])

    assert len(result) == 1
    wall_info, break_lo, break_hi = result[0]
    assert wall_info.ref == "cross"
    assert break_lo == 9.8
    assert break_hi == 10.2


def test_parallel_wall_is_not_treated_as_crossing():
    main_axis, main_lo, main_hi = "x", 0.0, 20.0
    main_perp_lo, main_perp_hi = -1.0, 1.0
    candidate = _parallel_wall(min_x=5.0, max_x=15.0, min_y=0.8, max_y=1.2)

    result = find_crossing_walls(main_axis, main_lo, main_hi, main_perp_lo, main_perp_hi, [candidate])

    assert result == []


def test_perpendicular_wall_far_from_perp_band_is_excluded():
    # Runs perpendicular and overlaps the length span, but never touches the
    # main wall's thickness band at all - not a real intersection.
    main_axis, main_lo, main_hi = "x", 0.0, 20.0
    main_perp_lo, main_perp_hi = -1.0, 1.0
    candidate = _perpendicular_crossing_wall(min_x=9.8, max_x=10.2, min_y=50.0, max_y=56.0)

    result = find_crossing_walls(main_axis, main_lo, main_hi, main_perp_lo, main_perp_hi, [candidate])

    assert result == []


def test_perpendicular_wall_outside_length_span_is_excluded():
    # Touches the perpendicular band but sits entirely beyond the wall's length.
    main_axis, main_lo, main_hi = "x", 0.0, 20.0
    main_perp_lo, main_perp_hi = -1.0, 1.0
    candidate = _perpendicular_crossing_wall(min_x=25.0, max_x=25.4, min_y=-1.0, max_y=6.0)

    result = find_crossing_walls(main_axis, main_lo, main_hi, main_perp_lo, main_perp_hi, [candidate])

    assert result == []


def test_break_span_is_clipped_to_main_walls_own_range():
    # Candidate extends beyond the main wall's own length span on one side.
    main_axis, main_lo, main_hi = "x", 0.0, 20.0
    main_perp_lo, main_perp_hi = -1.0, 1.0
    candidate = _perpendicular_crossing_wall(min_x=-5.0, max_x=0.4, min_y=-1.0, max_y=6.0)

    result = find_crossing_walls(main_axis, main_lo, main_hi, main_perp_lo, main_perp_hi, [candidate])

    assert len(result) == 1
    _, break_lo, break_hi = result[0]
    assert break_lo == 0.0  # clipped to main wall's own start
    assert break_hi == 0.4


def test_multiple_crossing_walls_all_detected():
    main_axis, main_lo, main_hi = "x", 0.0, 20.0
    main_perp_lo, main_perp_hi = -1.0, 1.0
    candidates = [
        _perpendicular_crossing_wall(min_x=4.8, max_x=5.2),
        _perpendicular_crossing_wall(min_x=9.8, max_x=10.2),
        _perpendicular_crossing_wall(min_x=14.8, max_x=15.2),
    ]

    result = find_crossing_walls(main_axis, main_lo, main_hi, main_perp_lo, main_perp_hi, candidates)

    assert len(result) == 3
    spans = sorted((r[1], r[2]) for r in result)
    assert spans == [(4.8, 5.2), (9.8, 10.2), (14.8, 15.2)]


def test_works_for_y_oriented_main_wall_too():
    # Main wall runs along Y this time; crossing candidate must run along X.
    main_axis, main_lo, main_hi = "y", 0.0, 20.0
    main_perp_lo, main_perp_hi = -1.0, 1.0
    candidate = ElementInfo(ref="cross", category="Wall", min_x=-1.0, max_x=6.0, min_y=9.8, max_y=10.2)

    result = find_crossing_walls(main_axis, main_lo, main_hi, main_perp_lo, main_perp_hi, [candidate])

    assert len(result) == 1
    _, break_lo, break_hi = result[0]
    assert break_lo == 9.8
    assert break_hi == 10.2


def test_near_coincident_crossings_are_deduplicated_to_one():
    # Two different wall elements meeting at the same physical point (e.g. a
    # partition split on either side of the main wall) - confirmed live to differ
    # by only a fraction of a millimeter. Must collapse to a single break, not two
    # near-duplicate references in the same chain.
    main_axis, main_lo, main_hi = "x", 0.0, 20.0
    main_perp_lo, main_perp_hi = -1.0, 1.0
    almost_identical_a = _perpendicular_crossing_wall(min_x=9.8000000001, max_x=10.2000000001)
    almost_identical_b = _perpendicular_crossing_wall(min_x=9.8000000002, max_x=10.2000000003)

    result = find_crossing_walls(
        main_axis, main_lo, main_hi, main_perp_lo, main_perp_hi,
        [almost_identical_a, almost_identical_b])

    assert len(result) == 1


def test_genuinely_distinct_nearby_crossings_are_both_kept():
    # Two real, separate partitions close together but clearly distinguishable -
    # must not be merged just because they're both "near" each other.
    main_axis, main_lo, main_hi = "x", 0.0, 20.0
    main_perp_lo, main_perp_hi = -1.0, 1.0
    first = _perpendicular_crossing_wall(min_x=9.8, max_x=10.0)
    second = _perpendicular_crossing_wall(min_x=10.5, max_x=10.7)

    result = find_crossing_walls(main_axis, main_lo, main_hi, main_perp_lo, main_perp_hi, [first, second])

    assert len(result) == 2


def test_degenerate_zero_width_overlap_is_excluded():
    # Candidate just barely touches the main wall's very edge - overlap rounds to
    # zero width, should not produce a spurious break.
    main_axis, main_lo, main_hi = "x", 0.0, 20.0
    main_perp_lo, main_perp_hi = -1.0, 1.0
    candidate = _perpendicular_crossing_wall(min_x=20.0, max_x=20.4, min_y=-1.0, max_y=6.0)

    result = find_crossing_walls(main_axis, main_lo, main_hi, main_perp_lo, main_perp_hi, [candidate])

    assert result == []
