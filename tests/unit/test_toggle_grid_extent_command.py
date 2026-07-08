# -*- coding: utf-8 -*-
"""Exercises toggle_grid_extent_command against fakes - no Revit involved,
same pattern as the other app-command tests (SAD Sec 6).
"""
from bkbim.app.commands import toggle_grid_extent_command
from bkbim.domain.models.grid_extent import EXTENT_MODEL, EXTENT_VIEW_SPECIFIC, GridExtentInfo


class _FakeWriter(object):
    def __init__(self, fail_refs=None):
        self.calls = []
        self._fail_refs = fail_refs or set()

    def set_extent(self, grid_ref, end0_extent, end1_extent):
        if grid_ref in self._fail_refs:
            raise RuntimeError("boom")
        self.calls.append((grid_ref, end0_extent, end1_extent))


def test_no_grids_fails_with_a_clear_message():
    result = toggle_grid_extent_command.run([], _FakeWriter())
    assert not result.success
    assert "No grids" in result.message


def test_toggles_a_3d_grid_to_2d():
    grids = [GridExtentInfo(ref="G1", end0_extent=EXTENT_MODEL, end1_extent=EXTENT_MODEL)]
    writer = _FakeWriter()
    result = toggle_grid_extent_command.run(grids, writer)

    assert result.success
    assert writer.calls == [("G1", EXTENT_VIEW_SPECIFIC, EXTENT_VIEW_SPECIFIC)]
    assert result.value["toggled"] == 1
    assert result.value["failed"] == 0


def test_toggles_a_2d_grid_to_3d():
    grids = [GridExtentInfo(ref="G1", end0_extent=EXTENT_VIEW_SPECIFIC, end1_extent=EXTENT_VIEW_SPECIFIC)]
    writer = _FakeWriter()
    toggle_grid_extent_command.run(grids, writer)

    assert writer.calls == [("G1", EXTENT_MODEL, EXTENT_MODEL)]


def test_running_twice_returns_every_grid_to_its_original_state():
    grid = GridExtentInfo(ref="G1", end0_extent=EXTENT_MODEL, end1_extent=EXTENT_VIEW_SPECIFIC)
    writer = _FakeWriter()
    toggle_grid_extent_command.run([grid], writer)
    first_call = writer.calls[0]

    # Simulate the grid now reflecting what was just written, then toggle again.
    grid_after = GridExtentInfo(ref="G1", end0_extent=first_call[1], end1_extent=first_call[2])
    toggle_grid_extent_command.run([grid_after], writer)
    second_call = writer.calls[1]

    assert (second_call[1], second_call[2]) == (EXTENT_MODEL, EXTENT_VIEW_SPECIFIC)


def test_each_end_toggles_independently_when_mismatched():
    # One end already 2D, the other still 3D - a real state if a user manually
    # nudged just one end. Toggling must not silently normalize them together.
    grids = [GridExtentInfo(ref="G1", end0_extent=EXTENT_VIEW_SPECIFIC, end1_extent=EXTENT_MODEL)]
    writer = _FakeWriter()
    toggle_grid_extent_command.run(grids, writer)

    assert writer.calls == [("G1", EXTENT_MODEL, EXTENT_VIEW_SPECIFIC)]


def test_a_failed_grid_is_counted_but_does_not_stop_the_others():
    grids = [
        GridExtentInfo(ref="G1", end0_extent=EXTENT_MODEL, end1_extent=EXTENT_MODEL),
        GridExtentInfo(ref="G2", end0_extent=EXTENT_MODEL, end1_extent=EXTENT_MODEL),
    ]
    writer = _FakeWriter(fail_refs={"G1"})
    result = toggle_grid_extent_command.run(grids, writer)

    assert result.success
    assert result.value["toggled"] == 1
    assert result.value["failed"] == 1
    assert writer.calls == [("G2", EXTENT_VIEW_SPECIFIC, EXTENT_VIEW_SPECIFIC)]
