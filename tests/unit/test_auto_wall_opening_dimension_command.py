# -*- coding: utf-8 -*-
"""Exercises auto_wall_opening_dimension_command against fakes - no Revit involved,
same payoff as the other app-command tests (SAD Sec 6). Covers opening-jamb
breaking, crossing-wall splitting, and existing-dimension skipping (product owner
feedback 2026-07-05).
"""
from bkbim.app.commands import auto_wall_opening_dimension_command
from bkbim.domain.geometry.units import mm_to_ft
from bkbim.domain.models.axis_faces import AxisFaces
from bkbim.domain.models.element_info import ElementInfo
from bkbim.domain.standards.standard import Standard, default_standard


class _FakeWallRunReader(object):
    def __init__(self, wall_faces, opening_faces_list, raise_error=False):
        self._wall_faces = wall_faces
        self._opening_faces_list = opening_faces_list
        self._raise_error = raise_error

    def wall_run_faces(self, wall_ref, length_axis, opening_locations):
        if self._raise_error:
            raise RuntimeError("boom")
        return self._wall_faces, self._opening_faces_list


class _FakeReferenceProvider(object):
    def __init__(self, faces_by_ref=None, raise_error=False):
        self._faces_by_ref = faces_by_ref or {}
        self._raise_error = raise_error

    def faces_for(self, element_ref, axis):
        if self._raise_error:
            raise RuntimeError("boom")
        return self._faces_by_ref.get(element_ref)


class _FakeDimension(object):
    def __init__(self, dim_id):
        self.Id = dim_id


class _FakeWriter(object):
    def __init__(self, always_fail=False):
        self._counter = 0
        self._always_fail = always_fail
        self.written_plans = []

    def write(self, plan):
        self.written_plans.append(plan)
        if self._always_fail:
            return None
        self._counter += 1
        return _FakeDimension(self._counter)


class _FakeFailureTracker(object):
    def __init__(self):
        self.registered = []

    def register_created(self, element_id):
        self.registered.append(element_id)


class _FakeExistingDimensionChecker(object):
    def __init__(self, always_exists=False, raise_error=False):
        self._always_exists = always_exists
        self._raise_error = raise_error
        self.checked_plans = []

    def already_exists(self, plan):
        self.checked_plans.append(plan)
        if self._raise_error:
            raise RuntimeError("boom")
        return self._always_exists


def _wall_context(wall_ref="wall-1", length_axis="x", perp_lo=0.0, perp_hi=1.0,
                   opening_locations=None, candidate_walls=None, is_exterior=False,
                   center_x=0.0, center_y=0.0):
    return {
        "wall_ref": wall_ref, "length_axis": length_axis,
        "perp_lo": perp_lo, "perp_hi": perp_hi,
        "opening_locations": opening_locations or [],
        "candidate_walls": candidate_walls or [],
        "is_exterior": is_exterior,
        "center_x": center_x, "center_y": center_y,
    }


def _run(walls_with_context, wall_run_reader, writer, failure_tracker, standard,
         reference_provider=None, existing_dimension_checker=None):
    return auto_wall_opening_dimension_command.run(
        walls_with_context, reference_provider or _FakeReferenceProvider(),
        wall_run_reader, existing_dimension_checker or _FakeExistingDimensionChecker(),
        writer, failure_tracker, standard)


def test_no_walls_fails_with_clear_message():
    result = _run([], _FakeWallRunReader(None, []), _FakeWriter(), _FakeFailureTracker(), default_standard())

    assert result.success is False
    assert "No walls" in result.message


def test_wall_with_no_openings_creates_one_dimension():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    reader = _FakeWallRunReader(wall_faces, [])
    tracker = _FakeFailureTracker()

    result = _run([_wall_context()], reader, _FakeWriter(), tracker, default_standard())

    assert result.success is True
    assert result.value["created"] == 1
    assert result.value["skipped"] == 0
    assert result.value["already_existing"] == 0
    assert len(tracker.registered) == 1


def test_wall_faces_none_is_counted_as_skipped():
    reader = _FakeWallRunReader(None, [])
    result = _run([_wall_context()], reader, _FakeWriter(), _FakeFailureTracker(), default_standard())

    assert result.success is True
    assert result.value["created"] == 0
    assert result.value["skipped"] == 1


def test_writer_refusal_is_counted_as_skipped_not_error():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    reader = _FakeWallRunReader(wall_faces, [])
    writer = _FakeWriter(always_fail=True)
    tracker = _FakeFailureTracker()

    result = _run([_wall_context()], reader, writer, tracker, default_standard())

    assert result.value["created"] == 0
    assert result.value["skipped"] == 1
    assert tracker.registered == []


def test_reader_exception_is_counted_as_skipped_and_does_not_crash():
    reader = _FakeWallRunReader(None, [], raise_error=True)
    result = _run([_wall_context()], reader, _FakeWriter(), _FakeFailureTracker(), default_standard())

    assert result.success is True
    assert result.value["skipped"] == 1


def test_multiple_walls_each_produce_their_own_dimension():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    reader = _FakeWallRunReader(wall_faces, [])
    tracker = _FakeFailureTracker()

    walls = [_wall_context(wall_ref="w1"), _wall_context(wall_ref="w2"), _wall_context(wall_ref="w3")]
    result = _run(walls, reader, _FakeWriter(), tracker, default_standard())

    assert result.value["created"] == 3
    assert len(tracker.registered) == 3


def test_perp_pos_uses_standard_side_and_offset():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)

    captured_plans = []

    class _CapturingWriter(object):
        def write(self, plan):
            captured_plans.append(plan)
            return _FakeDimension(1)

    std = Standard(name=u"Test", offset_first_mm=800.0, default_side=-1)
    reader = _FakeWallRunReader(wall_faces, [])

    _run([_wall_context(perp_lo=2.0, perp_hi=5.0)], reader, _CapturingWriter(), _FakeFailureTracker(), std)

    assert len(captured_plans) == 1
    assert captured_plans[0].perp_pos == 2.0 - mm_to_ft(800.0)


# --- crossing-wall splitting (product owner feedback 2026-07-05: a crossing
#     wall's own thickness must never appear as a segment - split into separate
#     dimensions instead, stopping before it and resuming after) ---

def _crossing_wall(ref, min_x, max_x, min_y=-1.0, max_y=6.0):
    return ElementInfo(ref=ref, category="Wall", min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y)


def test_crossing_wall_splits_into_two_separate_dimensions():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    reader = _FakeWallRunReader(wall_faces, [])

    crossing = _crossing_wall("cross-1", min_x=9.8, max_x=10.2)
    cross_faces = AxisFaces(ref_lo="cross-near", ref_hi="cross-far", coord_lo=9.8, coord_hi=10.2)
    provider = _FakeReferenceProvider(faces_by_ref={"cross-1": cross_faces})

    writer = _FakeWriter()
    context = _wall_context(perp_lo=-1.0, perp_hi=1.0, candidate_walls=[crossing])

    result = _run([context], reader, writer, _FakeFailureTracker(), default_standard(), reference_provider=provider)

    assert result.value["created"] == 2
    assert len(writer.written_plans) == 2
    assert writer.written_plans[0].refs == ["start", "cross-near"]
    assert writer.written_plans[1].refs == ["cross-far", "end"]


def test_non_crossing_candidate_does_not_split_the_chain():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    reader = _FakeWallRunReader(wall_faces, [])

    # Parallel wall (same orientation as main) - not a real crossing.
    non_crossing = ElementInfo(ref="parallel", category="Wall", min_x=5.0, max_x=15.0, min_y=0.8, max_y=1.2)
    provider = _FakeReferenceProvider()
    writer = _FakeWriter()
    context = _wall_context(perp_lo=-1.0, perp_hi=1.0, candidate_walls=[non_crossing])

    result = _run([context], reader, writer, _FakeFailureTracker(), default_standard(), reference_provider=provider)

    assert result.value["created"] == 1
    plan = writer.written_plans[0]
    assert plan.refs == ["start", "end"]


def test_crossing_wall_and_opening_each_land_in_the_right_run():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    door = AxisFaces(ref_lo="door-near", ref_hi="door-far", coord_lo=15.0, coord_hi=17.0)
    reader = _FakeWallRunReader(wall_faces, [door])

    crossing = _crossing_wall("cross-1", min_x=9.8, max_x=10.2)
    cross_faces = AxisFaces(ref_lo="cross-near", ref_hi="cross-far", coord_lo=9.8, coord_hi=10.2)
    provider = _FakeReferenceProvider(faces_by_ref={"cross-1": cross_faces})

    writer = _FakeWriter()
    context = _wall_context(perp_lo=-1.0, perp_hi=1.0, candidate_walls=[crossing])

    _run([context], reader, writer, _FakeFailureTracker(), default_standard(), reference_provider=provider)

    assert len(writer.written_plans) == 2
    assert writer.written_plans[0].refs == ["start", "cross-near"]
    assert writer.written_plans[1].refs == ["cross-far", "door-near", "door-far", "end"]


def test_crossing_wall_face_resolution_failure_is_skipped_gracefully():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    reader = _FakeWallRunReader(wall_faces, [])

    crossing = _crossing_wall("cross-1", min_x=9.8, max_x=10.2)
    # faces_by_ref has no entry for "cross-1" -> faces_for returns None.
    provider = _FakeReferenceProvider(faces_by_ref={})
    writer = _FakeWriter()
    context = _wall_context(perp_lo=-1.0, perp_hi=1.0, candidate_walls=[crossing])

    result = _run([context], reader, writer, _FakeFailureTracker(), default_standard(), reference_provider=provider)

    # No usable crossing reference - falls back to one plain dimension.
    assert result.value["created"] == 1
    plan = writer.written_plans[0]
    assert plan.refs == ["start", "end"]


# --- existing-dimension skipping (product owner feedback 2026-07-05: re-running
#     this command should be safe to use as an "update" - only add what's missing) ---

def test_already_existing_plan_is_skipped_not_duplicated():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    reader = _FakeWallRunReader(wall_faces, [])
    writer = _FakeWriter()
    checker = _FakeExistingDimensionChecker(always_exists=True)

    result = _run([_wall_context()], reader, writer, _FakeFailureTracker(), default_standard(),
                  existing_dimension_checker=checker)

    assert result.value["created"] == 0
    assert result.value["already_existing"] == 1
    assert result.value["skipped"] == 0
    assert writer.written_plans == []  # never even attempted to write it


def test_new_wall_still_gets_dimensioned_when_others_already_exist():
    # Two walls produce identical-shaped plans (same fake reader) - simulate
    # "first one already dimensioned, second one is new" by having the checker
    # answer differently on successive calls.
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    reader = _FakeWallRunReader(wall_faces, [])
    writer = _FakeWriter()

    call_count = {"n": 0}

    class _AlternatingChecker(object):
        def already_exists(self, plan):
            call_count["n"] += 1
            return call_count["n"] == 1  # first plan already exists, second doesn't

    result = _run(
        [_wall_context(wall_ref="w1"), _wall_context(wall_ref="w2")],
        reader, writer, _FakeFailureTracker(), default_standard(),
        existing_dimension_checker=_AlternatingChecker())

    assert result.value["created"] == 1
    assert result.value["already_existing"] == 1


def test_existing_dimension_checker_exception_does_not_block_creation():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    reader = _FakeWallRunReader(wall_faces, [])
    writer = _FakeWriter()
    checker = _FakeExistingDimensionChecker(raise_error=True)

    result = _run([_wall_context()], reader, writer, _FakeFailureTracker(), default_standard(),
                  existing_dimension_checker=checker)

    # A broken checker must not silently block all dimensioning - fail open, not closed.
    assert result.value["created"] == 1


# --- exterior wall 3-string perimeter dimensioning (2026-07-07, product owner
#     sketch: openings string closest, perpendicular-wall string in the middle,
#     overall string outermost - only for walls flagged is_exterior) ---

def test_non_exterior_wall_still_gets_only_one_dimension():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    reader = _FakeWallRunReader(wall_faces, [])
    writer = _FakeWriter()

    result = _run([_wall_context(is_exterior=False)], reader, writer, _FakeFailureTracker(), default_standard())

    assert result.value["created"] == 1
    assert len(writer.written_plans) == 1
    assert writer.written_plans[0].kind == u"wall_run"


def test_exterior_wall_with_no_openings_or_crossings_gets_three_dimensions():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    reader = _FakeWallRunReader(wall_faces, [])
    writer = _FakeWriter()

    result = _run([_wall_context(is_exterior=True)], reader, writer, _FakeFailureTracker(), default_standard())

    assert result.value["created"] == 3
    kinds = sorted(p.kind for p in writer.written_plans)
    assert kinds == sorted([u"wall_run", u"wall_perpendicular_chain", u"wall_overall"])
    assert all(p.refs == ["start", "end"] for p in writer.written_plans)


def test_exterior_wall_strings_are_placed_progressively_further_out():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    reader = _FakeWallRunReader(wall_faces, [])
    writer = _FakeWriter()
    std = Standard(name=u"Test", offset_first_mm=300.0, wall_perimeter_gap_mm=1400.0, default_side=-1)

    _run([_wall_context(perp_lo=-1.0, perp_hi=1.0, is_exterior=True)], reader, writer,
         _FakeFailureTracker(), std)

    by_kind = dict((p.kind, p) for p in writer.written_plans)
    offset_ft = mm_to_ft(300.0)
    gap_ft = mm_to_ft(1400.0)
    assert by_kind[u"wall_run"].perp_pos == -1.0 - offset_ft
    assert by_kind[u"wall_perpendicular_chain"].perp_pos == -1.0 - offset_ft - gap_ft
    assert by_kind[u"wall_overall"].perp_pos == -1.0 - offset_ft - 2 * gap_ft


def test_exterior_wall_strings_do_not_stack_when_gap_setting_is_zero():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    reader = _FakeWallRunReader(wall_faces, [])
    writer = _FakeWriter()
    std = Standard(name=u"Test", offset_first_mm=300.0, wall_perimeter_gap_mm=0.0, default_side=1)

    _run([_wall_context(perp_lo=-1.0, perp_hi=1.0, is_exterior=True)], reader, writer,
         _FakeFailureTracker(), std)

    by_kind = dict((p.kind, p) for p in writer.written_plans)
    offset_ft = mm_to_ft(300.0)
    min_gap_ft = mm_to_ft(300.0)
    assert by_kind[u"wall_run"].perp_pos == 1.0 + offset_ft
    assert by_kind[u"wall_perpendicular_chain"].perp_pos == 1.0 + offset_ft + min_gap_ft
    assert by_kind[u"wall_overall"].perp_pos == 1.0 + offset_ft + 2 * min_gap_ft


def test_exterior_wall_with_crossing_splits_the_inner_string_but_chains_the_middle_one():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    reader = _FakeWallRunReader(wall_faces, [])

    crossing = _crossing_wall("cross-1", min_x=9.8, max_x=10.2)
    cross_faces = AxisFaces(ref_lo="cross-near", ref_hi="cross-far", coord_lo=9.8, coord_hi=10.2)
    provider = _FakeReferenceProvider(faces_by_ref={"cross-1": cross_faces})
    writer = _FakeWriter()

    context = _wall_context(perp_lo=-1.0, perp_hi=1.0, candidate_walls=[crossing], is_exterior=True)
    result = _run([context], reader, writer, _FakeFailureTracker(), default_standard(), reference_provider=provider)

    # Inner "wall_run" string: split into 2 (unchanged existing behavior).
    inner = [p for p in writer.written_plans if p.kind == u"wall_run"]
    assert len(inner) == 2
    assert inner[0].refs == ["start", "cross-near"]
    assert inner[1].refs == ["cross-far", "end"]

    # Middle "perpendicular chain" string: ONE continuous chain including the crossing.
    middle = [p for p in writer.written_plans if p.kind == u"wall_perpendicular_chain"]
    assert len(middle) == 1
    assert middle[0].refs == ["start", "cross-near", "cross-far", "end"]

    # Outer "overall" string: just the wall's own two ends.
    outer = [p for p in writer.written_plans if p.kind == u"wall_overall"]
    assert len(outer) == 1
    assert outer[0].refs == ["start", "end"]

    assert result.value["created"] == 4  # 2 inner + 1 middle + 1 outer


# --- per-wall outward side (2026-07-07 follow-up: "I always want it to go
#     towards the exterior of the building" - a single fixed side is wrong for
#     a wall on the opposite side of the building from whatever that favors) ---

def test_exterior_walls_on_opposite_sides_of_the_building_place_strings_on_opposite_sides():
    # Two exterior walls on opposite sides of a building (top wall centered at
    # y=10, bottom wall centered at y=0) - their group centroid sits at y=5.
    # The TOP wall's own center (10) is ABOVE the centroid -> outward = +side
    # (above it). The BOTTOM wall's own center (0) is BELOW the centroid ->
    # outward = -side (below it). A single fixed default_side (-1) would have
    # put BOTH on the same side, wrong for one of them.
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    reader = _FakeWallRunReader(wall_faces, [])
    writer = _FakeWriter()

    top_wall = _wall_context(wall_ref="top", perp_lo=9.5, perp_hi=10.5,
                              is_exterior=True, center_x=10.0, center_y=10.0)
    bottom_wall = _wall_context(wall_ref="bottom", perp_lo=-0.5, perp_hi=0.5,
                                 is_exterior=True, center_x=10.0, center_y=0.0)

    std = Standard(name=u"Test", offset_first_mm=300.0, default_side=-1)
    _run([top_wall, bottom_wall], reader, writer, _FakeFailureTracker(), std)

    # Use the inner "wall_run" string (just offset_ft, no gap term) to keep
    # the expected math simple - both walls produce identical refs (the fake
    # reader always returns the same start/end), so compare perp_pos only.
    inner_positions = sorted(p.perp_pos for p in writer.written_plans if p.kind == u"wall_run")
    offset_ft = mm_to_ft(300.0)
    # Bottom wall's string sits BELOW its own perp_lo (further from center);
    # top wall's sits ABOVE its own perp_hi - never both on the same side.
    assert inner_positions == sorted([-0.5 - offset_ft, 10.5 + offset_ft])


def test_a_single_exterior_wall_falls_back_to_default_side():
    # With only one exterior wall, the "centroid" IS that wall's own center -
    # nothing to compare against, so it must fall back to default_side rather
    # than dividing by zero or picking arbitrarily.
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    reader = _FakeWallRunReader(wall_faces, [])
    writer = _FakeWriter()

    context = _wall_context(perp_lo=-1.0, perp_hi=1.0, is_exterior=True, center_x=5.0, center_y=5.0)
    std = Standard(name=u"Test", offset_first_mm=300.0, default_side=1)
    _run([context], reader, writer, _FakeFailureTracker(), std)

    inner = [p for p in writer.written_plans if p.kind == u"wall_run"][0]
    assert inner.perp_pos == 1.0 + mm_to_ft(300.0)  # default_side=1 -> perp_hi side


def test_non_exterior_walls_are_unaffected_by_the_exterior_centroid():
    wall_faces = AxisFaces(ref_lo="start", ref_hi="end", coord_lo=0.0, coord_hi=20.0)
    reader = _FakeWallRunReader(wall_faces, [])
    writer = _FakeWriter()

    exterior = _wall_context(wall_ref="ext", perp_lo=9.5, perp_hi=10.5,
                              is_exterior=True, center_x=10.0, center_y=10.0)
    interior = _wall_context(wall_ref="int", perp_lo=-1.0, perp_hi=1.0,
                              is_exterior=False, center_x=0.0, center_y=0.0)

    std = Standard(name=u"Test", offset_first_mm=300.0, default_side=-1)
    _run([exterior, interior], reader, writer, _FakeFailureTracker(), std)

    interior_plan = [p for p in writer.written_plans if p.refs == ["start", "end"] and p.kind == u"wall_run"
                      and p.perp_pos == -1.0 - mm_to_ft(300.0)]
    assert len(interior_plan) == 1  # interior wall still used default_side (-1), untouched
