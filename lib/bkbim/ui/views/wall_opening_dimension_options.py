# -*- coding: utf-8 -*-
"""Code-behind for WallOpeningDimensionOptions.xaml - dimension-style picker, a
single slider+textbox spacing control (one offset value, unlike Grid Dimensions'
two strings), a wall-type multi-select (product owner, 2026-07-05: moving to a
modeling convention with each layer as its own wall element - blockwork, plaster,
tile - and needs to pick which type(s) count as the dimension-worthy structure),
and a gap-between-exterior-strings control (2026-07-07, product owner tried the
exterior perimeter feature and found the fixed 1400mm default "wayyy too much
gap" - now user-adjustable per run instead of only editable in code).
Mirrors ui/views/grid_dimension_options.py's structure.
"""

import os

from pyrevit import forms

from bkbim.ui.views.listbox_drag_select import enable_drag_multiselect


class WallOpeningDimensionOptionsResult(object):
    def __init__(self, dimension_type, offset_mm, perimeter_gap_mm, selected_wall_types):
        self.dimension_type = dimension_type
        self.offset_mm = offset_mm
        self.perimeter_gap_mm = perimeter_gap_mm
        self.selected_wall_types = selected_wall_types  # list of WallType elements


class WallOpeningDimensionOptionsWindow(forms.WPFWindow):
    def __init__(self, dimension_types, wall_types, type_name_fn, default_offset_mm, default_gap_mm):
        xaml_path = os.path.join(os.path.dirname(__file__), "WallOpeningDimensionOptions.xaml")
        forms.WPFWindow.__init__(self, xaml_path)

        self._dimension_types = dimension_types
        self._wall_types = wall_types
        self.result = None

        for dt in dimension_types:
            self.DimensionStyleCombo.Items.Add(type_name_fn(dt))
        if dimension_types:
            self.DimensionStyleCombo.SelectedIndex = 0

        self.OffsetSlider.Value = default_offset_mm
        self.OffsetTextBox.Text = str(int(default_offset_mm))
        self.GapSlider.Value = default_gap_mm
        self.GapTextBox.Text = str(int(default_gap_mm))

        for wt in wall_types:
            self.WallTypesList.Items.Add(type_name_fn(wt))
        # Default: every wall type selected, so behavior is unchanged unless the
        # user deliberately narrows it - matches every existing modeling style.
        for i in range(self.WallTypesList.Items.Count):
            self.WallTypesList.SelectedItems.Add(self.WallTypesList.Items[i])

        enable_drag_multiselect(self.WallTypesList)

        self.OffsetSlider.ValueChanged += self._on_offset_slider_changed
        self.OffsetTextBox.LostFocus += self._on_offset_text_committed
        self.GapSlider.ValueChanged += self._on_gap_slider_changed
        self.GapTextBox.LostFocus += self._on_gap_text_committed

        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

    def _on_offset_slider_changed(self, sender, args):
        self.OffsetTextBox.Text = str(int(self.OffsetSlider.Value))

    def _on_offset_text_committed(self, sender, args):
        try:
            value = float(self.OffsetTextBox.Text)
        except ValueError:
            value = self.OffsetSlider.Value
        value = max(self.OffsetSlider.Minimum, min(self.OffsetSlider.Maximum, value))
        self.OffsetSlider.Value = value
        self.OffsetTextBox.Text = str(int(value))

    def _on_gap_slider_changed(self, sender, args):
        self.GapTextBox.Text = str(int(self.GapSlider.Value))

    def _on_gap_text_committed(self, sender, args):
        try:
            value = float(self.GapTextBox.Text)
        except ValueError:
            value = self.GapSlider.Value
        value = max(self.GapSlider.Minimum, min(self.GapSlider.Maximum, value))
        self.GapSlider.Value = value
        self.GapTextBox.Text = str(int(value))

    def _on_run(self, sender, args):
        index = self.DimensionStyleCombo.SelectedIndex
        chosen_type = self._dimension_types[index] if 0 <= index < len(self._dimension_types) else None

        selected_indices = [self.WallTypesList.Items.IndexOf(item) for item in self.WallTypesList.SelectedItems]
        selected_wall_types = [self._wall_types[i] for i in selected_indices if 0 <= i < len(self._wall_types)]

        self.result = WallOpeningDimensionOptionsResult(
            dimension_type=chosen_type,
            offset_mm=self.OffsetSlider.Value,
            perimeter_gap_mm=self.GapSlider.Value,
            selected_wall_types=selected_wall_types,
        )
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_wall_opening_dimension_options(dimension_types, wall_types, type_name_fn,
                                         default_offset_mm, default_gap_mm):
    """Shows the modal options window.

    Returns a WallOpeningDimensionOptionsResult, or None if the user cancelled.
    """
    window = WallOpeningDimensionOptionsWindow(
        dimension_types, wall_types, type_name_fn, default_offset_mm, default_gap_mm)
    window.ShowDialog()
    return window.result
