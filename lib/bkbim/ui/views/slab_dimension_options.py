# -*- coding: utf-8 -*-
"""Code-behind for SlabDimensionOptions.xaml. Two independent, mutually
exclusive modes only - per product owner (2026-07-06): "I want two options,
one from grid to slab edges, and another measuring all edges of the slab" -
replacing the earlier bundled MODE_GRID_AND_COLUMN (detail + overall together)
that Column/Beam/Footing still use. No gap field here: MODE_GRID_ONLY and
MODE_OVERALL_ONLY each place their one dimension straight off `offset_mm`, with
no second string to clear (gap only matters when detail AND overall coexist,
which Slab Dimensions no longer does).
"""

import os

from pyrevit import forms

from bkbim.domain.dimensioning.column_grid_planner import MODE_GRID_ONLY, MODE_OVERALL_ONLY
from bkbim.revit.adapter.stable_representation import element_id_token
from bkbim.ui.tokens import resolve_tokens_path
from bkbim.ui.views.listbox_drag_select import enable_drag_multiselect
from bkbim.ui.views.options_memory import dimension_style_index, select_remembered_types

_OFFSET_LABEL_GRID = u"Offset from grid line (mm)"
_OFFSET_LABEL_OVERALL = u"Offset from slab edge (mm)"


class SlabDimensionOptionsResult(object):
    def __init__(self, dimension_type, offset_mm, mode, selected_types):
        self.dimension_type = dimension_type
        self.offset_mm = offset_mm
        self.mode = mode  # MODE_GRID_ONLY | MODE_OVERALL_ONLY
        self.selected_types = selected_types  # list of FloorType elements


class SlabDimensionOptionsWindow(forms.WPFWindow):
    def __init__(self, dimension_types, slab_types, type_name_fn, default_offset_mm,
                 default_dimension_type_name=None, default_selected_type_names=None):
        xaml_path = os.path.join(os.path.dirname(__file__), "SlabDimensionOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self._dimension_types = dimension_types
        self._slab_types = slab_types
        self.result = None

        id_token_fn = lambda t: element_id_token(t.Id)

        for dt in dimension_types:
            self.DimensionStyleCombo.Items.Add(type_name_fn(dt))
        if dimension_types:
            self.DimensionStyleCombo.SelectedIndex = dimension_style_index(
                dimension_types, type_name_fn, default_dimension_type_name, id_token_fn=id_token_fn)

        self.OffsetSlider.Value = default_offset_mm
        self.OffsetTextBox.Text = str(int(default_offset_mm))

        for st in slab_types:
            self.StructuralTypesList.Items.Add(type_name_fn(st))
        # Default: every type selected unless a remembered subset exists
        # (Tool Memory) - matches every other type filter's convention.
        select_remembered_types(
            self.StructuralTypesList, type_name_fn, slab_types, default_selected_type_names,
            id_token_fn=id_token_fn)

        enable_drag_multiselect(self.StructuralTypesList)

        self.OffsetSlider.ValueChanged += self._on_offset_slider_changed
        self.OffsetTextBox.LostFocus += self._on_offset_text_committed
        self.GridToEdgesRadio.Checked += self._on_mode_changed
        self.AllEdgesRadio.Checked += self._on_mode_changed

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

    def _on_mode_changed(self, sender, args):
        self.OffsetLabel.Content = (
            _OFFSET_LABEL_GRID if self.GridToEdgesRadio.IsChecked else _OFFSET_LABEL_OVERALL)

    def _on_run(self, sender, args):
        index = self.DimensionStyleCombo.SelectedIndex
        chosen_type = self._dimension_types[index] if 0 <= index < len(self._dimension_types) else None

        mode = MODE_GRID_ONLY if self.GridToEdgesRadio.IsChecked else MODE_OVERALL_ONLY

        selected_indices = [self.StructuralTypesList.Items.IndexOf(item)
                             for item in self.StructuralTypesList.SelectedItems]
        selected_types = [self._slab_types[i] for i in selected_indices
                           if 0 <= i < len(self._slab_types)]

        self.result = SlabDimensionOptionsResult(
            dimension_type=chosen_type,
            offset_mm=self.OffsetSlider.Value,
            mode=mode,
            selected_types=selected_types,
        )
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_slab_dimension_options(dimension_types, slab_types, type_name_fn, default_offset_mm,
                                 default_dimension_type_name=None, default_selected_type_names=None):
    """Shows the modal options window.

    Returns a SlabDimensionOptionsResult, or None if the user cancelled.
    """
    window = SlabDimensionOptionsWindow(
        dimension_types, slab_types, type_name_fn, default_offset_mm,
        default_dimension_type_name=default_dimension_type_name,
        default_selected_type_names=default_selected_type_names)
    window.ShowDialog()
    return window.result
