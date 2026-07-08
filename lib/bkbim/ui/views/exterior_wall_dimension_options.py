# -*- coding: utf-8 -*-
"""Code-behind for ExteriorWallDimensionOptions.xaml - the lightweight
options window for the standalone Exterior Wall Dimension pushbutton
(product owner, 2026-07-08: "give me a small push button for exterior wall
dimension (3 string) so that i can manually select walls if i wish to").

No wall-type list here, unlike wall_opening_dimension_options.py - this
tool always dimensions exactly whichever walls you manually pick after
Run, never a type-filtered set collected from the whole view.
"""

import os

from pyrevit import forms


class ExteriorWallDimensionOptionsResult(object):
    def __init__(self, dimension_type, offset_mm, perimeter_gap_mm):
        self.dimension_type = dimension_type
        self.offset_mm = offset_mm
        self.perimeter_gap_mm = perimeter_gap_mm


class ExteriorWallDimensionOptionsWindow(forms.WPFWindow):
    def __init__(self, dimension_types, type_name_fn, default_offset_mm, default_gap_mm):
        xaml_path = os.path.join(os.path.dirname(__file__), "ExteriorWallDimensionOptions.xaml")
        forms.WPFWindow.__init__(self, xaml_path)

        self._dimension_types = dimension_types
        self.result = None

        for dt in dimension_types:
            self.DimensionStyleCombo.Items.Add(type_name_fn(dt))
        if dimension_types:
            self.DimensionStyleCombo.SelectedIndex = 0

        self.OffsetSlider.Value = default_offset_mm
        self.OffsetTextBox.Text = str(int(default_offset_mm))
        self.GapSlider.Value = default_gap_mm
        self.GapTextBox.Text = str(int(default_gap_mm))

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

        self.result = ExteriorWallDimensionOptionsResult(
            dimension_type=chosen_type,
            offset_mm=self.OffsetSlider.Value,
            perimeter_gap_mm=self.GapSlider.Value,
        )
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_exterior_wall_dimension_options(dimension_types, type_name_fn, default_offset_mm, default_gap_mm):
    """Shows the modal options window. Returns an
    ExteriorWallDimensionOptionsResult, or None if the user cancelled.
    """
    window = ExteriorWallDimensionOptionsWindow(dimension_types, type_name_fn, default_offset_mm, default_gap_mm)
    window.ShowDialog()
    return window.result
