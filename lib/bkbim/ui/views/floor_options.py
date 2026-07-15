# -*- coding: utf-8 -*-
"""Code-behind for FloorOptions.xaml - replaces AutoFloor's old chain of
floor-type / level / boundary-mode / unit-then-value popups with one
window. Offset is mm-only (the old separate "unit first" popup is dropped
entirely, matching every other numeric field in the suite).

Decoupled from the Revit adapter layer the same way structural_dimension_options.py
is: floor types/levels are passed in as plain lists with a type_name_fn
callback for display names.
"""

import os

from pyrevit import forms

from bkbim.ui.tokens import resolve_tokens_path


class FloorOptionsResult(object):
    def __init__(self, floor_type, level, subtract_walls, offset_mm):
        self.floor_type = floor_type
        self.level = level
        self.subtract_walls = subtract_walls
        self.offset_mm = offset_mm


class FloorOptionsWindow(forms.WPFWindow):
    def __init__(self, floor_types, levels, type_name_fn, default_floor_type_name=None,
                 default_level_name=None, default_subtract_walls=False, default_offset_mm=0.0):
        xaml_path = os.path.join(os.path.dirname(__file__), "FloorOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.result = None
        self._floor_types = floor_types
        self._levels = levels

        floor_type_names = [type_name_fn(ft) for ft in floor_types]
        for name in floor_type_names:
            self.FloorTypeCombo.Items.Add(name)
        self.FloorTypeCombo.SelectedIndex = (
            floor_type_names.index(default_floor_type_name) if default_floor_type_name in floor_type_names else 0)

        level_names = [type_name_fn(lv) for lv in levels]
        for name in level_names:
            self.LevelCombo.Items.Add(name)
        self.LevelCombo.SelectedIndex = (
            level_names.index(default_level_name) if default_level_name in level_names else 0)

        if default_subtract_walls:
            self.WallsBoundaryRadio.IsChecked = True
        else:
            self.TotalBoundaryRadio.IsChecked = True

        self.OffsetSlider.Value = default_offset_mm
        self.OffsetTextBox.Text = str(int(default_offset_mm))

        self.OffsetSlider.ValueChanged += self._on_slider_changed
        self.OffsetTextBox.LostFocus += self._on_text_committed

        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

    def _on_slider_changed(self, sender, args):
        self.OffsetTextBox.Text = str(int(self.OffsetSlider.Value))

    def _on_text_committed(self, sender, args):
        try:
            value = float(self.OffsetTextBox.Text)
        except ValueError:
            value = self.OffsetSlider.Value
        value = max(self.OffsetSlider.Minimum, min(self.OffsetSlider.Maximum, value))
        self.OffsetSlider.Value = value
        self.OffsetTextBox.Text = str(int(value))

    def _on_run(self, sender, args):
        ft_idx = self.FloorTypeCombo.SelectedIndex
        lv_idx = self.LevelCombo.SelectedIndex
        floor_type = self._floor_types[ft_idx] if 0 <= ft_idx < len(self._floor_types) else None
        level = self._levels[lv_idx] if 0 <= lv_idx < len(self._levels) else None

        self.result = FloorOptionsResult(
            floor_type=floor_type, level=level,
            subtract_walls=bool(self.WallsBoundaryRadio.IsChecked),
            offset_mm=self.OffsetSlider.Value)
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_floor_options(floor_types, levels, type_name_fn, default_floor_type_name=None,
                       default_level_name=None, default_subtract_walls=False, default_offset_mm=0.0):
    """Shows the modal Floor Options window.

    Returns a FloorOptionsResult, or None if the user cancelled.
    """
    window = FloorOptionsWindow(
        floor_types, levels, type_name_fn, default_floor_type_name=default_floor_type_name,
        default_level_name=default_level_name, default_subtract_walls=default_subtract_walls,
        default_offset_mm=default_offset_mm)
    window.ShowDialog()
    return window.result
