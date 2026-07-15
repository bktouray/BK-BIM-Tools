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

from bkbim.automation.typical_views import MODE_PER_GROUP, MODE_PER_INSTANCE
from bkbim.ui.tokens import resolve_tokens_path
from bkbim.ui.views.summary_rows import render_summary_rows


class TypicalSectionOptionsResult(object):
    def __init__(self, mode, value_mm):
        self.mode = mode  # MODE_PER_GROUP | MODE_PER_INSTANCE
        self.value_mm = value_mm


class TypicalSectionOptionsWindow(forms.WPFWindow):
    def __init__(self, title, subtitle, summary_lines, mode_group_label, mode_instance_label,
                 value_label, default_value_mm):
        xaml_path = os.path.join(os.path.dirname(__file__), "TypicalSectionOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.result = None

        self.Title = u"BK BIM Tools - {0}".format(title)
        self.TitleText.Text = title
        self.SubtitleText.Text = subtitle
        self.GroupModeRadio.Content = mode_group_label
        self.InstanceModeRadio.Content = mode_instance_label
        self.ValueLabel.Content = value_label

        render_summary_rows(self, self.SummaryPanel, summary_lines)

        self.ValueSlider.Value = default_value_mm
        self.ValueTextBox.Text = str(int(default_value_mm))

        self.ValueSlider.ValueChanged += self._on_slider_changed
        self.ValueTextBox.LostFocus += self._on_text_committed

        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

    def _on_slider_changed(self, sender, args):
        self.ValueTextBox.Text = str(int(self.ValueSlider.Value))

    def _on_text_committed(self, sender, args):
        try:
            value = float(self.ValueTextBox.Text)
        except ValueError:
            value = self.ValueSlider.Value
        value = max(self.ValueSlider.Minimum, min(self.ValueSlider.Maximum, value))
        self.ValueSlider.Value = value
        self.ValueTextBox.Text = str(int(value))

    def _on_run(self, sender, args):
        mode = MODE_PER_INSTANCE if self.InstanceModeRadio.IsChecked else MODE_PER_GROUP
        self.result = TypicalSectionOptionsResult(mode=mode, value_mm=self.ValueSlider.Value)
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_typical_section_options(title, subtitle, summary_lines, mode_group_label, mode_instance_label,
                                  value_label, default_value_mm):
    """Shows the branded options window.

    Returns a TypicalSectionOptionsResult, or None if the user cancelled.
    """
    window = TypicalSectionOptionsWindow(
        title, subtitle, summary_lines, mode_group_label, mode_instance_label,
        value_label, default_value_mm)
    window.ShowDialog()
    return window.result
