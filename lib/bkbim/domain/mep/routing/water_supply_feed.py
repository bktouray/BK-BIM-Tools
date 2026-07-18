# -*- coding: utf-8 -*-
"""Pure Water Supply feed geometry helpers.

These helpers define the upstream path from incoming main to valve point to
wall/corridor trunk. They deliberately contain no Revit imports so the fragile
ceiling valve-bypass rules can be regression-tested outside Revit.
"""

_MIN_FEED_SEGMENT_MM = 10.0
_VALVE_BYPASS_HALF_LENGTH_MM = 100.0


def distance_mm(point_a, point_b):
    return sum(
        (point_b[index] - point_a[index]) ** 2
        for index in range(3)) ** 0.5


def horizontal_distance_mm(point_a, point_b):
    return (
        (point_b[0] - point_a[0]) ** 2 +
        (point_b[1] - point_a[1]) ** 2) ** 0.5


def compact_points(points, min_length_mm=_MIN_FEED_SEGMENT_MM):
    compacted = []
    for point in points:
        if not compacted or distance_mm(compacted[-1], point) >= min_length_mm:
            compacted.append(point)
    return compacted


def corridor_offset_vector(corridor_points, offset_mm):
    if not corridor_points or abs(offset_mm) < 0.001:
        return (0.0, 0.0)
    first = corridor_points[0]
    second = None
    for point in corridor_points[1:]:
        if horizontal_distance_mm(first, point) > _MIN_FEED_SEGMENT_MM:
            second = point
            break
    if second is None:
        return (0.0, 0.0)
    dx = second[0] - first[0]
    dy = second[1] - first[1]
    length = (dx * dx + dy * dy) ** 0.5
    if length <= 0:
        return (0.0, 0.0)
    normal_x = -dy / length
    normal_y = dx / length
    return (normal_x * offset_mm, normal_y * offset_mm)


def offset_point_xy(point, offset_xy):
    if (abs(offset_xy[0]) < 0.001 and abs(offset_xy[1]) < 0.001):
        return point
    return (point[0] + offset_xy[0], point[1] + offset_xy[1], point[2])


def offset_corridor_points(corridor_points, offset_mm):
    offset = corridor_offset_vector(corridor_points, offset_mm)
    if not corridor_points or (
            abs(offset[0]) < 0.001 and abs(offset[1]) < 0.001):
        return corridor_points
    return [offset_point_xy(point, offset) for point in corridor_points]


def offset_point_z(point, offset_mm):
    if abs(offset_mm) < 0.001:
        return point
    return (point[0], point[1], point[2] + offset_mm)


def trunk_aligned_approach_point(valve_point, trunk_origin_point,
                                 trunk_next_point=None):
    valve_x, valve_y, _valve_z = valve_point
    trunk_x, trunk_y, trunk_z = trunk_origin_point
    if trunk_next_point is None:
        return (trunk_x, valve_y, trunk_z)

    dx = abs(trunk_next_point[0] - trunk_x)
    dy = abs(trunk_next_point[1] - trunk_y)
    if dx >= dy:
        return (valve_x, trunk_y, trunk_z)
    return (trunk_x, valve_y, trunk_z)


def post_valve_approach_points(post_high_point, trunk_origin_point,
                               trunk_next_point=None):
    """Approaches the trunk from the downstream side without overlapping it."""
    if trunk_next_point is None:
        return [trunk_aligned_approach_point(
            post_high_point, trunk_origin_point, trunk_next_point)]

    trunk_x, trunk_y, trunk_z = trunk_origin_point
    dx = abs(trunk_next_point[0] - trunk_x)
    dy = abs(trunk_next_point[1] - trunk_y)
    post_x, post_y, _post_z = post_high_point
    offset_mm = max(_VALVE_BYPASS_HALF_LENGTH_MM * 2.0, 200.0)

    if dx >= dy:
        # Trunk runs mainly in X, so enter it with a final Y segment.
        if abs(post_y - trunk_y) >= _MIN_FEED_SEGMENT_MM:
            return [(trunk_x, post_y, trunk_z)]
        sign = 1.0 if post_y >= trunk_y else -1.0
        return [
            (post_x, trunk_y + sign * offset_mm, trunk_z),
            (trunk_x, trunk_y + sign * offset_mm, trunk_z),
        ]

    # Trunk runs mainly in Y, so enter it with a final X segment.
    if abs(post_x - trunk_x) >= _MIN_FEED_SEGMENT_MM:
        return [(post_x, trunk_y, trunk_z)]
    sign = 1.0 if post_x >= trunk_x else -1.0
    return [
        (trunk_x + sign * offset_mm, post_y, trunk_z),
        (trunk_x + sign * offset_mm, trunk_y, trunk_z),
    ]


def aligned_in_plan(point_a, point_b, tolerance_mm=1.0):
    return (abs(point_a[0] - point_b[0]) < tolerance_mm or
            abs(point_a[1] - point_b[1]) < tolerance_mm)


def corridor_axis_reference_point(valve_point, trunk_origin_point,
                                  trunk_next_point=None):
    """Returns a point from the valve parallel to the selected wall corridor."""
    if trunk_next_point is None:
        return None
    dx = trunk_next_point[0] - trunk_origin_point[0]
    dy = trunk_next_point[1] - trunk_origin_point[1]
    if abs(dx) < _MIN_FEED_SEGMENT_MM and abs(dy) < _MIN_FEED_SEGMENT_MM:
        return None

    valve_x, valve_y, _valve_z = valve_point
    trunk_z = trunk_origin_point[2]
    if abs(dx) >= abs(dy):
        return (valve_x + (1.0 if dx >= 0 else -1.0), valve_y, trunk_z)
    return (valve_x, valve_y + (1.0 if dy >= 0 else -1.0), trunk_z)


def valve_bypass_axis(incoming_point, valve_point, approach_point):
    """Returns (use_y_axis, drop_side_sign).

    The selected wall/corridor chooses the valve-piece axis. The incoming main
    chooses which side the drop lands on. The post-valve rise is always on the
    opposite side.
    """
    valve_x, valve_y, _valve_z = valve_point
    use_y_axis = None
    if approach_point is not None:
        approach_dx = approach_point[0] - valve_x
        approach_dy = approach_point[1] - valve_y
        if abs(approach_dx) < 1.0 and abs(approach_dy) >= 1.0:
            use_y_axis = True
        elif abs(approach_dy) < 1.0 and abs(approach_dx) >= 1.0:
            use_y_axis = False

    delta_x = valve_x - incoming_point[0]
    delta_y = valve_y - incoming_point[1]
    if use_y_axis is None:
        use_y_axis = abs(delta_y) >= abs(delta_x)

    incoming_delta = (
        incoming_point[1] - valve_y if use_y_axis
        else incoming_point[0] - valve_x)
    if abs(incoming_delta) >= 1.0:
        return use_y_axis, (1.0 if incoming_delta >= 0 else -1.0)

    if abs(delta_y) >= abs(delta_x):
        return True, (-1.0 if delta_y >= 0 else 1.0)
    return False, (-1.0 if delta_x >= 0 else 1.0)


def valve_bypass_points(incoming_point, valve_point, trunk_z,
                        approach_point=None):
    """Creates a ceiling/main-to-valve-height bypass around the valve point."""
    valve_x, valve_y, valve_z = valve_point
    incoming_z = incoming_point[2]
    if (incoming_z <= valve_z + _MIN_FEED_SEGMENT_MM or
            trunk_z <= valve_z + _MIN_FEED_SEGMENT_MM):
        return None

    use_y_axis, drop_side_sign = valve_bypass_axis(
        incoming_point, valve_point, approach_point)
    half = _VALVE_BYPASS_HALF_LENGTH_MM
    if use_y_axis:
        pre = (valve_x, valve_y + drop_side_sign * half, incoming_z)
        pre_low = (valve_x, valve_y + drop_side_sign * half, valve_z)
        post_low = (valve_x, valve_y - drop_side_sign * half, valve_z)
        post_high = (valve_x, valve_y - drop_side_sign * half, trunk_z)
    else:
        pre = (valve_x + drop_side_sign * half, valve_y, incoming_z)
        pre_low = (valve_x + drop_side_sign * half, valve_y, valve_z)
        post_low = (valve_x - drop_side_sign * half, valve_y, valve_z)
        post_high = (valve_x - drop_side_sign * half, valve_y, trunk_z)
    return pre, pre_low, post_low, post_high


def feed_points_from_main_to_trunk(incoming_point, valve_point, trunk_origin_point,
                                   trunk_next_point=None):
    """Upstream route: water main -> valve point -> trunk origin."""
    valve_x, valve_y, _valve_z = valve_point
    _trunk_x, _trunk_y, trunk_z = trunk_origin_point
    approach_point = trunk_aligned_approach_point(
        valve_point, trunk_origin_point, trunk_next_point)
    corridor_axis_reference = corridor_axis_reference_point(
        valve_point, trunk_origin_point, trunk_next_point)
    bypass_axis_reference = (
        corridor_axis_reference or
        (trunk_origin_point if aligned_in_plan(valve_point, trunk_origin_point)
         else approach_point))
    bypass = valve_bypass_points(
        incoming_point, valve_point, trunk_z,
        approach_point=bypass_axis_reference)
    if bypass is not None:
        pre, pre_low, post_low, post_high = bypass
        return compact_points([
            incoming_point,
            (pre[0], incoming_point[1], incoming_point[2]),
            pre,
            pre_low,
            post_low,
            post_high,
        ] + post_valve_approach_points(
            post_high, trunk_origin_point, trunk_next_point) + [
            trunk_origin_point,
        ])

    points = [
        incoming_point,
        (valve_x, incoming_point[1], incoming_point[2]),
        (valve_x, valve_y, incoming_point[2]),
        valve_point,
        (valve_x, valve_y, trunk_z),
        approach_point,
        trunk_origin_point,
    ]
    return compact_points(points)
