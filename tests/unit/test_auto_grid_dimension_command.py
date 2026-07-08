# -*- coding: utf-8 -*-
"""Exercises auto_grid_dimension_command against fakes - no Revit involved, same
payoff as test_auto_dimension_command.py (SAD Sec 6). Covers existing-dimension
skipping (product owner feedback 2026-07-05).
"""
from bkbim.app.commands import auto_grid_dimension_command
from bkbim.domain.models.element_info import ElementInfo
from bkbim.domain.models.grid_info import BUBBLE_P0, ORIENTATION_HORIZONTAL, ORIENTATION_VERTICAL, GridInfo
from bkbim.domain.standards.standard import default_standard


class _FakeSelectionReader(object):
    def __init__(self, elements, grids, raise_error=False):
        self._elements = elements
        self._grids = grids
        self._raise_error = raise_error

    def read(self, selected_elements):
        if self._raise_error:
            raise RuntimeError("boom")
        return self._elements, self._grids


class _FakeDimension(object):
    def __init__(self, dim_id):
        self.Id = dim_id


class _FakeWriter(object):
    def __init__(self, always_fail=False):
        self._counter = 0
        self._always_fail = always_fail

    def write(self, plan):
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

    def already_exists(self, plan):
        if self._raise_error:
            raise RuntimeError("boom")
        return self._always_exists


def _v_grid(name, coord):
    return GridInfo(ref="v-" + name, name=name, orientation=ORIENTATION_VERTICAL,
                     coord=coord, p0=(coord, 0.0), p1=(coord, 40.0), bubble_end=BUBBLE_P0)


def _h_grid(name, coord):
    return GridInfo(ref="h-" + name, name=name, orientation=ORIENTATION_HORIZONTAL,
                     coord=coord, p0=(0.0, coord), p1=(40.0, coord), bubble_end=BUBBLE_P0)


def _wall():
    return ElementInfo(ref="w1", category="Wall", min_x=0.0, max_x=20.0, min_y=0.0, max_y=10.0)


def _run(selected_elements, reader, writer, failure_tracker, standard, existing_dimension_checker=None):
    return auto_grid_dimension_command.run(
        selected_elements, reader, existing_dimension_checker or _FakeExistingDimensionChecker(),
        writer, failure_tracker, standard)


def test_no_grids_fails_with_clear_message():
    reader = _FakeSelectionReader(elements=[], grids=[])
    result = _run([], reader, _FakeWriter(), _FakeFailureTracker(), default_standard())

    assert result.success is False
    assert "grids" in result.message


def test_single_grid_fails_not_enough_to_chain():
    reader = _FakeSelectionReader(elements=[_wall()], grids=[_v_grid("A", 5.0)])
    result = _run([], reader, _FakeWriter(), _FakeFailureTracker(), default_standard())

    assert result.success is False
    assert "at least 2 grids" in result.message


def test_happy_path_creates_eight_plans_for_both_orientations():
    grids = [_v_grid("A", 0.0), _v_grid("B", 10.0), _h_grid("1", 0.0), _h_grid("2", 8.0)]
    reader = _FakeSelectionReader(elements=[_wall()], grids=grids)
    tracker = _FakeFailureTracker()

    result = _run([], reader, _FakeWriter(), tracker, default_standard())

    assert result.success is True
    assert result.value["created"] == 8
    assert result.value["skipped"] == 0
    assert result.value["already_existing"] == 0
    assert len(tracker.registered) == 8


def test_writer_refusal_is_counted_as_skipped():
    grids = [_v_grid("A", 0.0), _v_grid("B", 10.0)]
    reader = _FakeSelectionReader(elements=[_wall()], grids=grids)
    writer = _FakeWriter(always_fail=True)
    tracker = _FakeFailureTracker()

    result = _run([], reader, writer, tracker, default_standard())

    assert result.success is True
    assert result.value["created"] == 0
    assert result.value["skipped"] == 4  # 2 sides x 2 strings for the one orientation
    assert tracker.registered == []


def test_selection_reader_exception_produces_failure_result():
    reader = _FakeSelectionReader(elements=[], grids=[], raise_error=True)
    result = _run([], reader, _FakeWriter(), _FakeFailureTracker(), default_standard())

    assert result.success is False
    assert "Could not read the selection" in result.message


def test_works_with_only_grids_selected_no_elements():
    # No walls/columns selected - span must fall back to the grids' own endpoints.
    grids = [_v_grid("A", 0.0), _v_grid("B", 10.0)]
    reader = _FakeSelectionReader(elements=[], grids=grids)
    tracker = _FakeFailureTracker()

    result = _run([], reader, _FakeWriter(), tracker, default_standard())

    assert result.success is True
    assert result.value["created"] == 4


# --- existing-dimension skipping (product owner feedback 2026-07-05: re-running
#     this command should be safe to use as an "update" - only add what's missing) ---

def test_all_already_existing_plans_are_skipped_not_duplicated():
    grids = [_v_grid("A", 0.0), _v_grid("B", 10.0)]
    reader = _FakeSelectionReader(elements=[_wall()], grids=grids)
    writer = _FakeWriter()
    checker = _FakeExistingDimensionChecker(always_exists=True)

    result = _run([], reader, writer, _FakeFailureTracker(), default_standard(),
                  existing_dimension_checker=checker)

    assert result.value["created"] == 0
    assert result.value["already_existing"] == 4
    assert result.value["skipped"] == 0


def test_existing_dimension_checker_exception_does_not_block_creation():
    grids = [_v_grid("A", 0.0), _v_grid("B", 10.0)]
    reader = _FakeSelectionReader(elements=[_wall()], grids=grids)
    writer = _FakeWriter()
    checker = _FakeExistingDimensionChecker(raise_error=True)

    result = _run([], reader, writer, _FakeFailureTracker(), default_standard(),
                  existing_dimension_checker=checker)

    # A broken checker must not silently block all dimensioning - fail open, not closed.
    assert result.value["created"] == 4
