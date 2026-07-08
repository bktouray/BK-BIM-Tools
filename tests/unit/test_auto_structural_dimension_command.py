# -*- coding: utf-8 -*-
"""Exercises auto_structural_dimension_command against fakes - no Revit involved,
same payoff as test_auto_grid_dimension_command.py. Covers both dimensioning modes
and existing-dimension skipping (shared convention across all four dimensioning
tools now).
"""
from bkbim.app.commands import auto_structural_dimension_command
from bkbim.domain.dimensioning.column_grid_planner import MODE_CONTINUOUS_NO_GRID, MODE_GRID_AND_COLUMN
from bkbim.domain.models.axis_faces import AxisFaces
from bkbim.domain.models.element_info import ElementInfo
from bkbim.domain.models.grid_info import BUBBLE_P0, ORIENTATION_HORIZONTAL, ORIENTATION_VERTICAL, GridInfo
from bkbim.domain.standards.standard import default_standard


class _FakeSelectionReader(object):
    def __init__(self, elements, grids, raise_error=False):
        self._elements = elements
        self._grids = grids
        self._raise_error = raise_error

    def read(self, detected_elements):
        if self._raise_error:
            raise RuntimeError("boom")
        return self._elements, self._grids


class _FakeReferenceProvider(object):
    """Derives AxisFaces straight from each ElementInfo's own bounding box, so
    tests only need to describe columns once (as ElementInfo), not twice.
    """
    def __init__(self, elements, fail_on=None):
        self._by_ref = dict((e.ref, e) for e in elements)
        self._fail_on = fail_on or set()

    def faces_for(self, ref, axis):
        if (ref, axis) in self._fail_on:
            raise RuntimeError("boom")
        e = self._by_ref[ref]
        if axis == u"x":
            return AxisFaces(ref_lo=ref + u"-xlo", ref_hi=ref + u"-xhi", coord_lo=e.min_x, coord_hi=e.max_x)
        return AxisFaces(ref_lo=ref + u"-ylo", ref_hi=ref + u"-yhi", coord_lo=e.min_y, coord_hi=e.max_y)


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


def _h_grid(name, coord):
    return GridInfo(ref=u"h-" + name, name=name, orientation=ORIENTATION_HORIZONTAL,
                     coord=coord, p0=(0.0, coord), p1=(40.0, coord), bubble_end=BUBBLE_P0)


def _v_grid(name, coord):
    return GridInfo(ref=u"v-" + name, name=name, orientation=ORIENTATION_VERTICAL,
                     coord=coord, p0=(coord, 0.0), p1=(coord, 40.0), bubble_end=BUBBLE_P0)


def _col(ref, x_lo, x_hi, y_lo, y_hi):
    return ElementInfo(ref=ref, category=u"Column", min_x=x_lo, max_x=x_hi, min_y=y_lo, max_y=y_hi)


def _run(elements, grids, mode, writer=None, tracker=None, checker=None, ref_provider=None, fail_on=None):
    reader = _FakeSelectionReader(elements=elements, grids=grids)
    provider = ref_provider or _FakeReferenceProvider(elements, fail_on=fail_on)
    return auto_structural_dimension_command.run(
        [], reader, provider, checker or _FakeExistingDimensionChecker(),
        writer or _FakeWriter(), tracker or _FakeFailureTracker(), mode, default_standard())


def test_no_elements_fails_with_clear_message():
    result = _run([], [_h_grid("A", 0.0)], MODE_CONTINUOUS_NO_GRID)
    assert result.success is False
    assert "columns or footings" in result.message


def test_no_grids_fails_with_clear_message():
    result = _run([_col("C1", 0.0, 1.0, -0.5, 0.5)], [], MODE_CONTINUOUS_NO_GRID)
    assert result.success is False
    assert "No grids" in result.message


def test_continuous_mode_happy_path_creates_one_chain_no_overall():
    cols = [_col("C1", 0.0, 1.0, -0.5, 0.5), _col("C2", 5.0, 6.0, -0.5, 0.5)]
    grids = [_h_grid("A", 0.0)]
    tracker = _FakeFailureTracker()

    result = _run(cols, grids, MODE_CONTINUOUS_NO_GRID, tracker=tracker)

    assert result.success is True
    assert result.value["created"] == 1
    assert result.value["skipped"] == 0
    assert len(tracker.registered) == 1


def test_grid_and_column_mode_creates_individual_dimensions_plus_per_column_overall():
    cols = [_col("C1", 0.0, 1.0, -0.5, 0.5), _col("C2", 5.0, 6.0, -0.5, 0.5)]
    grids = [_h_grid("A", 0.0), _v_grid("1", 0.5), _v_grid("2", 5.5)]
    tracker = _FakeFailureTracker()

    result = _run(cols, grids, MODE_GRID_AND_COLUMN, tracker=tracker)

    assert result.success is True
    # 2 columns x 2 axes x 2 dims each (detail + that column's own overall) = 8.
    assert result.value["created"] == 8
    assert len(tracker.registered) == 8


def test_single_column_alone_still_gets_its_own_detail_and_overall():
    cols = [_col("C1", 0.0, 1.0, -0.5, 0.5)]
    grids = [_h_grid("A", 0.0), _v_grid("1", 0.5)]

    result = _run(cols, grids, MODE_GRID_AND_COLUMN)

    assert result.success is True
    assert result.value["created"] == 4  # x-axis (detail+overall) + y-axis (detail+overall)


def test_not_enough_columns_in_a_row_fails_with_clear_message():
    result = _run([_col("C1", 0.0, 1.0, -0.5, 0.5)], [_h_grid("A", 0.0)], MODE_CONTINUOUS_NO_GRID)
    assert result.success is False
    assert "Nothing to dimension" in result.message


def test_column_with_unresolvable_faces_on_both_axes_is_counted_as_skipped():
    cols = [_col("C1", 0.0, 1.0, -0.5, 0.5), _col("C2", 5.0, 6.0, -0.5, 0.5)]
    grids = [_h_grid("A", 0.0)]
    result = _run(cols, grids, MODE_CONTINUOUS_NO_GRID,
                  fail_on=set([("C1", u"x"), ("C1", u"y")]))

    # C1 dropped entirely (unresolved on both axes) - only C2 remains, not enough
    # to form a row by itself, so the whole thing fails cleanly.
    assert result.success is False


def test_writer_refusal_is_counted_as_skipped():
    cols = [_col("C1", 0.0, 1.0, -0.5, 0.5), _col("C2", 5.0, 6.0, -0.5, 0.5)]
    grids = [_h_grid("A", 0.0)]
    writer = _FakeWriter(always_fail=True)
    tracker = _FakeFailureTracker()

    result = _run(cols, grids, MODE_CONTINUOUS_NO_GRID, writer=writer, tracker=tracker)

    assert result.success is True
    assert result.value["created"] == 0
    assert result.value["skipped"] == 1
    assert tracker.registered == []


def test_selection_reader_exception_produces_failure_result():
    reader = _FakeSelectionReader(elements=[], grids=[], raise_error=True)
    result = auto_structural_dimension_command.run(
        [], reader, _FakeReferenceProvider([]), _FakeExistingDimensionChecker(),
        _FakeWriter(), _FakeFailureTracker(), MODE_CONTINUOUS_NO_GRID, default_standard())

    assert result.success is False
    assert "Could not read the detected elements" in result.message


def test_all_already_existing_plans_are_skipped_not_duplicated():
    cols = [_col("C1", 0.0, 1.0, -0.5, 0.5), _col("C2", 5.0, 6.0, -0.5, 0.5)]
    grids = [_h_grid("A", 0.0)]
    checker = _FakeExistingDimensionChecker(always_exists=True)

    result = _run(cols, grids, MODE_CONTINUOUS_NO_GRID, checker=checker)

    assert result.value["created"] == 0
    assert result.value["already_existing"] == 1
    assert result.value["skipped"] == 0


def test_existing_dimension_checker_exception_does_not_block_creation():
    cols = [_col("C1", 0.0, 1.0, -0.5, 0.5), _col("C2", 5.0, 6.0, -0.5, 0.5)]
    grids = [_h_grid("A", 0.0)]
    checker = _FakeExistingDimensionChecker(raise_error=True)

    result = _run(cols, grids, MODE_CONTINUOUS_NO_GRID, checker=checker)

    # A broken checker must not silently block all dimensioning - fail open.
    assert result.value["created"] == 1
