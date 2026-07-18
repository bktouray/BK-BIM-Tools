# -*- coding: utf-8 -*-
"""Branded replacement for the Typical Beams/Columns/Footings wizard: the
"N typical sections found, continue?" `forms.alert`, the
`forms.CommandSwitchWindow` scope picker (per-group vs per-instance), and the
`forms.ask_for_string` far-clip/margin prompt. One shared window - all three
pushbuttons have the identical shape, only the wording and the numeric
field's meaning (far clip vs margin) differ.
"""

import os

from pyrevit import forms

from System.Windows import Visibility

from bkbim.automation.typical_views import MODE_PER_GROUP, MODE_PER_INSTANCE
from bkbim.ui.tokens import resolve_tokens_path
from bkbim.ui.views.summary_rows import render_summary_rows


class TypicalSectionOptionsResult(object):
    def __init__(self, mode, value_mm, secondary_value_mm=None, view_family_type=None):
        self.mode = mode  # MODE_PER_GROUP | MODE_PER_INSTANCE
        self.value_mm = value_mm
        self.secondary_value_mm = secondary_value_mm
        self.view_family_type = view_family_type


class TypicalSectionOptionsWindow(forms.WPFWindow):
    def __init__(self, title, subtitle, summary_lines, mode_group_label, mode_instance_label,
                 value_label, default_value_mm, secondary_value_label=None,
                 default_secondary_value_mm=None, view_family_types=None,
                 view_family_type_name_fn=None, default_view_family_type=None):
        xaml_path = os.path.join(os.path.dirname(__file__), "TypicalSectionOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.result = None
        self._has_secondary_value = bool(secondary_value_label)
        self._view_family_types = view_family_types or []

        self.Title = u"BK BIM Tools - {0}".format(title)
        self.TitleText.Text = title
        self.SubtitleText.Text = subtitle
        self.GroupModeRadio.Content = mode_group_label
        self.InstanceModeRadio.Content = mode_instance_label
        self.ValueLabel.Content = value_label
        if view_family_type_name_fn is None:
            view_family_type_name_fn = lambda v: unicode(v)

        render_summary_rows(self, self.SummaryPanel, summary_lines)

        for vft in self._view_family_types:
            self.ViewFamilyTypeCombo.Items.Add(view_family_type_name_fn(vft))
        if self._view_family_types:
            default_index = 0
            if default_view_family_type is not None:
                for i, vft in enumerate(self._view_family_types):
                    if vft.Id == default_view_family_type.Id:
                        default_index = i
                        break
            self.ViewFamilyTypeCombo.SelectedIndex = default_index
        else:
            self.ViewFamilyTypePanel.Visibility = Visibility.Collapsed

        self.ValueSlider.Value = default_value_mm
        self.ValueTextBox.Text = str(int(default_value_mm))

        if self._has_secondary_value:
            if default_secondary_value_mm is None:
                default_secondary_value_mm = default_value_mm
            self.SecondaryValuePanel.Visibility = Visibility.Visible
            self.SecondaryValueLabel.Content = secondary_value_label
            self.SecondaryValueSlider.Value = default_secondary_value_mm
            self.SecondaryValueTextBox.Text = str(int(default_secondary_value_mm))
        else:
            self.SecondaryValuePanel.Visibility = Visibility.Collapsed

        self.ValueSlider.ValueChanged += self._on_slider_changed
        self.ValueTextBox.LostFocus += self._on_text_committed
        self.SecondaryValueSlider.ValueChanged += self._on_secondary_slider_changed
        self.SecondaryValueTextBox.LostFocus += self._on_secondary_text_committed

        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

    def _sync_text_to_slider(self, slider, textbox):
        textbox.Text = str(int(slider.Value))

    def _sync_slider_to_text(self, slider, textbox):
        try:
            value = float(textbox.Text)
        except ValueError:
            value = slider.Value
        value = max(slider.Minimum, min(slider.Maximum, value))
        slider.Value = value
        textbox.Text = str(int(value))

    def _on_slider_changed(self, sender, args):
        self._sync_text_to_slider(self.ValueSlider, self.ValueTextBox)

    def _on_text_committed(self, sender, args):
        self._sync_slider_to_text(self.ValueSlider, self.ValueTextBox)

    def _on_secondary_slider_changed(self, sender, args):
        self._sync_text_to_slider(self.SecondaryValueSlider, self.SecondaryValueTextBox)

    def _on_secondary_text_committed(self, sender, args):
        self._sync_slider_to_text(self.SecondaryValueSlider, self.SecondaryValueTextBox)

    def _on_run(self, sender, args):
        mode = MODE_PER_INSTANCE if self.InstanceModeRadio.IsChecked else MODE_PER_GROUP
        secondary_value_mm = self.SecondaryValueSlider.Value if self._has_secondary_value else None
        index = self.ViewFamilyTypeCombo.SelectedIndex
        view_family_type = self._view_family_types[index] if 0 <= index < len(self._view_family_types) else None
        self.result = TypicalSectionOptionsResult(
            mode=mode, value_mm=self.ValueSlider.Value, secondary_value_mm=secondary_value_mm,
            view_family_type=view_family_type)
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_typical_section_options(title, subtitle, summary_lines, mode_group_label, mode_instance_label,
                                  value_label, default_value_mm, secondary_value_label=None,
                                  default_secondary_value_mm=None, view_family_types=None,
                                  view_family_type_name_fn=None, default_view_family_type=None):
    """Shows the branded options window.

    Returns a TypicalSectionOptionsResult, or None if the user cancelled.
    """
    window = TypicalSectionOptionsWindow(
        title, subtitle, summary_lines, mode_group_label, mode_instance_label,
        value_label, default_value_mm, secondary_value_label, default_secondary_value_mm,
        view_family_types, view_family_type_name_fn, default_view_family_type)
    window.ShowDialog()
    return window.result
