# -*- coding: utf-8 -*-
"""Code-behind for StructuralDimensionOptions.xaml - dimension-style picker, the
same offset+gap spacing pair Grid Dimensions uses, a mode radio (grid-and-column
vs continuous-no-grid), and a structural-type multi-select. Mirrors
wall_opening_dimension_options.py's structure (2026-07-06: Auto Dimension for
Structural Elements).
"""

import os

from pyrevit import forms

from bkbim.domain.dimensioning.column_grid_planner import MODE_CONTINUOUS_NO_GRID, MODE_GRID_AND_COLUMN
from bkbim.ui.views.listbox_drag_select import enable_drag_multiselect

# Per-category wording (product owner, 2026-07-06: "personalize the contents of
# each window to match the actual task" - the mode radio buttons were still
# saying "column edge - grid - column edge" even when dimensioning beams, a
# literal copy-paste artifact, not just a header/label oversight).
_CATEGORY_TEXT = {
    u"Column": {
        u"window_title": u"Column Dimensions",
        u"subtitle": u"Dimensions rows of columns detected in the current view, "
                     u"grouped by the grid line each row snaps to.",
        u"mode_detail": u"Column edge - grid - column edge, plus an overall string",
        u"mode_continuous": u"Continuous column-to-column strip (grid used to group "
                            u"only, never referenced)",
        u"types_helper": u"Column types visible in the view - narrow this down to "
                         u"just the type(s) you want dimensioned.",
    },
    u"Beam": {
        u"window_title": u"Beam Dimensions",
        u"subtitle": u"Dimensions rows of beams detected in the current view, grouped "
                     u"by the grid line each row snaps to - measuring beam to beam "
                     u"and taking in each beam's own width.",
        u"mode_detail": u"Beam edge - grid - beam edge, plus an overall string",
        u"mode_continuous": u"Continuous beam-to-beam strip, taking in each beam's "
                            u"width (grid used to group only, never referenced)",
        u"types_helper": u"Beam types visible in the view - narrow this down to just "
                         u"the type(s) you want dimensioned.",
    },
    u"Footing": {
        u"window_title": u"Footing Dimensions",
        u"subtitle": u"Dimensions rows of footings detected in the current view, "
                     u"grouped by the grid line each row snaps to.",
        u"mode_detail": u"Footing edge - grid - footing edge, plus an overall string",
        u"mode_continuous": u"Continuous footing-to-footing strip (grid used to group "
                            u"only, never referenced)",
        u"types_helper": u"Footing types visible in the view - narrow this down to "
                         u"just the type(s) you want dimensioned.",
    },
}


class StructuralDimensionOptionsResult(object):
    def __init__(self, dimension_type, offset_mm, gap_mm, mode, selected_types):
        self.dimension_type = dimension_type
        self.offset_mm = offset_mm
        self.gap_mm = gap_mm
        self.mode = mode  # MODE_GRID_AND_COLUMN | MODE_CONTINUOUS_NO_GRID
        self.selected_types = selected_types  # list of FamilySymbol elements


class StructuralDimensionOptionsWindow(forms.WPFWindow):
    def __init__(self, dimension_types, structural_types, type_name_fn, default_offset_mm, default_gap_mm,
                 category_label=None):
        xaml_path = os.path.join(os.path.dirname(__file__), "StructuralDimensionOptions.xaml")
        forms.WPFWindow.__init__(self, xaml_path)

        self._dimension_types = dimension_types
        self._structural_types = structural_types
        self.result = None

        # Product owner, 2026-07-06: a mixed list of column/beam/footing types
        # with no indication which was which ("200 x 300mm" could be any of
        # them) was confusing - "I don't know what's what." The caller now
        # picks ONE category before this window ever opens, so the list only
        # ever contains that category's types - and every bit of wording here
        # (title, subtitle, both mode descriptions, types helper) is genuinely
        # personalized per category, not a copy-paste with the header swapped.
        text = _CATEGORY_TEXT.get(category_label)
        if text:
            self.Title = u"BK BIM Tools - {0}".format(text[u"window_title"])
            self.TitleText.Text = text[u"window_title"]
            self.SubtitleText.Text = text[u"subtitle"]
            self.GridAndColumnRadio.Content = text[u"mode_detail"]
            self.ContinuousRadio.Content = text[u"mode_continuous"]
            self.TypesHelperText.Text = text[u"types_helper"]

        for dt in dimension_types:
            self.DimensionStyleCombo.Items.Add(type_name_fn(dt))
        if dimension_types:
            self.DimensionStyleCombo.SelectedIndex = 0

        self.OffsetSlider.Value = default_offset_mm
        self.OffsetTextBox.Text = str(int(default_offset_mm))
        self.GapSlider.Value = default_gap_mm
        self.GapTextBox.Text = str(int(default_gap_mm))

        for st in structural_types:
            self.StructuralTypesList.Items.Add(type_name_fn(st))
        # Default: every type selected, so behavior is unchanged unless the user
        # deliberately narrows it - matches the wall-type filter's convention.
        for i in range(self.StructuralTypesList.Items.Count):
            self.StructuralTypesList.SelectedItems.Add(self.StructuralTypesList.Items[i])

        enable_drag_multiselect(self.StructuralTypesList)

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

        mode = MODE_GRID_AND_COLUMN if self.GridAndColumnRadio.IsChecked else MODE_CONTINUOUS_NO_GRID

        selected_indices = [self.StructuralTypesList.Items.IndexOf(item)
                             for item in self.StructuralTypesList.SelectedItems]
        selected_types = [self._structural_types[i] for i in selected_indices
                           if 0 <= i < len(self._structural_types)]

        self.result = StructuralDimensionOptionsResult(
            dimension_type=chosen_type,
            offset_mm=self.OffsetSlider.Value,
            gap_mm=self.GapSlider.Value,
            mode=mode,
            selected_types=selected_types,
        )
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_structural_dimension_options(dimension_types, structural_types, type_name_fn,
                                       default_offset_mm, default_gap_mm, category_label=None):
    """Shows the modal options window.

    Returns a StructuralDimensionOptionsResult, or None if the user cancelled.
    """
    window = StructuralDimensionOptionsWindow(
        dimension_types, structural_types, type_name_fn, default_offset_mm, default_gap_mm,
        category_label=category_label)
    window.ShowDialog()
    return window.result
