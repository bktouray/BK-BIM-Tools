# -*- coding: utf-8 -*-
"""Exercises renumber_grids_command against fakes - no Revit involved, same
pattern as test_toggle_grid_extent_command.py (SAD Sec 6).
"""
from bkbim.app.commands import renumber_grids_command
from bkbim.domain.models.grid_info import ORIENTATION_HORIZONTAL, ORIENTATION_VERTICAL
from bkbim.domain.models.grid_position import SCHEME_LETTERS_TOP_NUMBERS_LEFT, GridPositionInfo


class _FakeWriter(object):
    def __init__(self, fail_names=None):
        self.calls = []
        self._fail_names = fail_names or set()
        self._current_names = {}

    def set_name(self, grid_ref, new_name):
        if new_name in self._fail_names:
            raise RuntimeError("boom")
        self.calls.append((grid_ref, new_name))
        self._current_names[grid_ref] = new_name


def test_no_grids_fails_with_a_clear_message():
    result = renumber_grids_command.run([], _FakeWriter())
    assert not result.success
    assert "No grids" in result.message


def test_only_angled_grids_fails_with_a_clear_message():
    # plan_renumber() drops anything not vertical/horizontal - simulate that
    # by passing a non-empty list whose orientation matches neither constant.
    grids = [GridPositionInfo(ref="G1", orientation=u"angled", coord=0.0)]
    result = renumber_grids_command.run(grids, _FakeWriter())
    assert not result.success
    assert "angled" in result.message.lower()


def test_renumbers_vertical_and_horizontal_grids():
    grids = [
        GridPositionInfo(ref="V1", orientation=ORIENTATION_VERTICAL, coord=0.0),
        GridPositionInfo(ref="V2", orientation=ORIENTATION_VERTICAL, coord=10.0),
        GridPositionInfo(ref="H1", orientation=ORIENTATION_HORIZONTAL, coord=10.0),
    ]
    writer = _FakeWriter()
    result = renumber_grids_command.run(grids, writer)

    assert result.success
    assert result.value["renamed"] == 3
    assert result.value["failed"] == 0
    assert writer._current_names == {"V1": "A", "V2": "B", "H1": "1"}


def test_renumbers_with_swapped_letter_and_number_directions():
    grids = [
        GridPositionInfo(ref="V1", orientation=ORIENTATION_VERTICAL, coord=0.0),
        GridPositionInfo(ref="V2", orientation=ORIENTATION_VERTICAL, coord=10.0),
        GridPositionInfo(ref="H1", orientation=ORIENTATION_HORIZONTAL, coord=10.0),
        GridPositionInfo(ref="H2", orientation=ORIENTATION_HORIZONTAL, coord=0.0),
    ]
    writer = _FakeWriter()
    result = renumber_grids_command.run(grids, writer, scheme=SCHEME_LETTERS_TOP_NUMBERS_LEFT)

    assert result.success
    assert writer._current_names == {"H1": "A", "H2": "B", "V1": "1", "V2": "2"}


def test_swapping_two_grid_names_does_not_collide():
    # A direct rename would collide: renaming G1 (currently "1") to "3" fails
    # while G2 still holds "3". The two-phase temp-stage must avoid this.
    grids = [
        GridPositionInfo(ref="G_far", orientation=ORIENTATION_HORIZONTAL, coord=0.0),   # -> "1"
        GridPositionInfo(ref="G_near", orientation=ORIENTATION_HORIZONTAL, coord=10.0),  # -> "2"
    ]
    writer = _FakeWriter()
    renumber_grids_command.run(grids, writer)

    # Every call must go through a temp name before any final name is set -
    # i.e. no final name appears before ALL grids have been staged.
    temp_calls = [c for c in writer.calls if c[1].startswith("__renumber_tmp_")]
    final_calls = [c for c in writer.calls if not c[1].startswith("__renumber_tmp_")]
    assert len(temp_calls) == 2
    assert len(final_calls) == 2
    first_final_index = writer.calls.index(final_calls[0])
    assert first_final_index >= len(temp_calls)


def test_a_grid_that_fails_to_stage_never_gets_a_final_name():
    grids = [
        GridPositionInfo(ref="bad", orientation=ORIENTATION_VERTICAL, coord=0.0),
        GridPositionInfo(ref="good", orientation=ORIENTATION_VERTICAL, coord=10.0),
    ]
    writer = _FakeWriter(fail_names={"__renumber_tmp_0__"})
    result = renumber_grids_command.run(grids, writer)

    assert result.value["renamed"] == 1
    assert result.value["failed"] == 1
    assert "bad" not in writer._current_names
    assert writer._current_names.get("good") == "B"


def test_a_grid_that_fails_final_apply_is_counted_but_does_not_stop_others():
    grids = [
        GridPositionInfo(ref="V1", orientation=ORIENTATION_VERTICAL, coord=0.0),
        GridPositionInfo(ref="V2", orientation=ORIENTATION_VERTICAL, coord=10.0),
    ]
    writer = _FakeWriter(fail_names={"A"})
    result = renumber_grids_command.run(grids, writer)

    assert result.success
    assert result.value["renamed"] == 1
    assert result.value["failed"] == 1
    assert writer._current_names.get("V2") == "B"
