# -*- coding: utf-8 -*-
"""Small pure centerline clash checks for coordinated Hot/Cold Water routes.

This is intentionally not a full clash engine. It catches the obvious bad
outcomes for the combined Water Supply pushbutton: hot and cold centerline
segments overlapping, crossing at the same elevation, or vertical risers
occupying the same plan location.
"""


def _close(a, b, tolerance_mm):
    return abs(a - b) <= tolerance_mm


def _between(value, a, b, tolerance_mm):
    lo = min(a, b) - tolerance_mm
    hi = max(a, b) + tolerance_mm
    return lo <= value <= hi


def _ranges_overlap(a1, a2, b1, b2, tolerance_mm):
    return (
        max(min(a1, a2), min(b1, b2)) <=
        min(max(a1, a2), max(b1, b2)) + tolerance_mm)


def _axis(segment, tolerance_mm):
    start = segment["start"]
    end = segment["end"]
    dx = abs(end[0] - start[0])
    dy = abs(end[1] - start[1])
    dz = abs(end[2] - start[2])
    if dx <= tolerance_mm and dy <= tolerance_mm and dz <= tolerance_mm:
        return u"point"
    if dy <= tolerance_mm and dz <= tolerance_mm:
        return u"x"
    if dx <= tolerance_mm and dz <= tolerance_mm:
        return u"y"
    if dx <= tolerance_mm and dy <= tolerance_mm:
        return u"z"
    return u"other"


def _same_level(segment_a, segment_b, tolerance_mm):
    return (
        _close(segment_a["start"][2], segment_a["end"][2], tolerance_mm) and
        _close(segment_b["start"][2], segment_b["end"][2], tolerance_mm) and
        _close(segment_a["start"][2], segment_b["start"][2], tolerance_mm))


def _segment_name(segment):
    return u"{0} {1}".format(
        segment.get("system", u"Route"),
        segment.get("label", segment.get("kind", u"segment")))


def _format_point(point):
    return u"({0:.0f}, {1:.0f}, {2:.0f})".format(
        float(point[0]), float(point[1]), float(point[2]))


def _clash_message(cold_segment, hot_segment, point, reason):
    return (
        u"{0} clashes with {1} at {2}: {3}.".format(
            _segment_name(hot_segment), _segment_name(cold_segment),
            _format_point(point), reason))


def _first_overlap_point(seg_a, seg_b, axis):
    if axis == u"x":
        x = max(min(seg_a["start"][0], seg_a["end"][0]),
                min(seg_b["start"][0], seg_b["end"][0]))
        return (x, seg_a["start"][1], seg_a["start"][2])
    if axis == u"y":
        y = max(min(seg_a["start"][1], seg_a["end"][1]),
                min(seg_b["start"][1], seg_b["end"][1]))
        return (seg_a["start"][0], y, seg_a["start"][2])
    z = max(min(seg_a["start"][2], seg_a["end"][2]),
            min(seg_b["start"][2], seg_b["end"][2]))
    return (seg_a["start"][0], seg_a["start"][1], z)


def _pair_clash(cold_segment, hot_segment, tolerance_mm):
    cold_axis = _axis(cold_segment, tolerance_mm)
    hot_axis = _axis(hot_segment, tolerance_mm)
    if cold_axis == u"other" or hot_axis == u"other":
        return None

    c0, c1 = cold_segment["start"], cold_segment["end"]
    h0, h1 = hot_segment["start"], hot_segment["end"]

    if cold_axis == hot_axis:
        if cold_axis == u"x":
            if (_same_level(cold_segment, hot_segment, tolerance_mm) and
                    _close(c0[1], h0[1], tolerance_mm) and
                    _ranges_overlap(c0[0], c1[0], h0[0], h1[0], tolerance_mm)):
                return _clash_message(
                    cold_segment, hot_segment,
                    _first_overlap_point(cold_segment, hot_segment, cold_axis),
                    u"horizontal centerlines overlap")
        elif cold_axis == u"y":
            if (_same_level(cold_segment, hot_segment, tolerance_mm) and
                    _close(c0[0], h0[0], tolerance_mm) and
                    _ranges_overlap(c0[1], c1[1], h0[1], h1[1], tolerance_mm)):
                return _clash_message(
                    cold_segment, hot_segment,
                    _first_overlap_point(cold_segment, hot_segment, cold_axis),
                    u"horizontal centerlines overlap")
        elif cold_axis == u"z":
            if (_close(c0[0], h0[0], tolerance_mm) and
                    _close(c0[1], h0[1], tolerance_mm) and
                    _ranges_overlap(c0[2], c1[2], h0[2], h1[2], tolerance_mm)):
                return _clash_message(
                    cold_segment, hot_segment,
                    _first_overlap_point(cold_segment, hot_segment, cold_axis),
                    u"vertical risers overlap")
        return None

    horizontal_axes = set([cold_axis, hot_axis])
    if horizontal_axes == set([u"x", u"y"]):
        x_segment = cold_segment if cold_axis == u"x" else hot_segment
        y_segment = cold_segment if cold_axis == u"y" else hot_segment
        x0, x1 = x_segment["start"], x_segment["end"]
        y0, y1 = y_segment["start"], y_segment["end"]
        if (_same_level(x_segment, y_segment, tolerance_mm) and
                _between(y0[0], x0[0], x1[0], tolerance_mm) and
                _between(x0[1], y0[1], y1[1], tolerance_mm)):
            return _clash_message(
                cold_segment, hot_segment,
                (y0[0], x0[1], x0[2]),
                u"horizontal centerlines cross at the same elevation")
        return None

    if cold_axis == u"z" or hot_axis == u"z":
        vertical = cold_segment if cold_axis == u"z" else hot_segment
        horizontal = hot_segment if cold_axis == u"z" else cold_segment
        h_axis = hot_axis if cold_axis == u"z" else cold_axis
        v0, v1 = vertical["start"], vertical["end"]
        h0, h1 = horizontal["start"], horizontal["end"]
        if h_axis == u"x":
            in_plan = (
                _between(v0[0], h0[0], h1[0], tolerance_mm) and
                _close(v0[1], h0[1], tolerance_mm))
        elif h_axis == u"y":
            in_plan = (
                _close(v0[0], h0[0], tolerance_mm) and
                _between(v0[1], h0[1], h1[1], tolerance_mm))
        else:
            in_plan = False
        if in_plan and _between(h0[2], v0[2], v1[2], tolerance_mm):
            return _clash_message(
                cold_segment, hot_segment,
                (v0[0], v0[1], h0[2]),
                u"vertical riser crosses a horizontal run")
    return None


def detect_hot_cold_clashes(cold_segments, hot_segments, tolerance_mm=5.0,
                            limit=10):
    """Returns user-facing diagnostics for obvious Hot/Cold centerline clashes."""
    diagnostics = []
    for cold_segment in cold_segments:
        for hot_segment in hot_segments:
            message = _pair_clash(cold_segment, hot_segment, tolerance_mm)
            if message:
                diagnostics.append(message)
                if len(diagnostics) >= limit:
                    return diagnostics
    return diagnostics
