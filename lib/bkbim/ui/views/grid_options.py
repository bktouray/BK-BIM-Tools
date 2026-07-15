# -*- coding: utf-8 -*-
"""Code-behind for GridOptions.xaml - replaces AutoGrid's old two-popup
"extend? -> unit -> value" chain with one window: a checkbox plus an
mm-only Slider+TextBox pair (unit dropdown dropped entirely - mm-only
matches every other numeric field in the suite, e.g.
StructuralDimensionOptions.xaml's offset/gap fields).

Fully decoupled from the Revit adapter layer (no Revit imports at all) -
the flow module converts extend_mm to feet.
"""

import os

from pyrevit import forms

from bkbim.ui.tokens import resolve_tokens_path


class GridOptionsResult(object):
    def __init__(self, auto_extend, extend_mm):
        self.auto_extend = auto_extend
        self.extend_mm = extend_mm  # 0.0 when auto_extend is False


class GridOptionsWindow(forms.WPFWindow):
    def __init__(self, default_auto_extend=True, default_extend_mm=1500.0):
        xaml_path = os.path.join(os.path.dirname(__file__), "GridOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.result = None

        self.AutoExtendCheckBox.IsChecked = bool(default_auto_extend)
        self.ExtendSlider.Value = default_extend_mm
        self.ExtendTextBox.Text = str(int(default_extend_mm))
        self._update_extend_enabled()

        self.AutoExtendCheckBox.Checked += self._on_toggle
        self.AutoExtendCheckBox.Unchecked += self._on_toggle
        self.ExtendSlider.ValueChanged += self._on_slider_changed
        self.ExtendTextBox.LostFocus += self._on_text_committed

        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

    def _update_extend_enabled(self):
        enabled = bool(self.AutoExtendCheckBox.IsChecked)
        self.ExtendSlider.IsEnabled = enabled
        self.ExtendTextBox.IsEnabled = enabled

    def _on_toggle(self, sender, args):
        self._update_extend_enabled()

    def _on_slider_changed(self, sender, args):
        self.ExtendTextBox.Text = str(int(self.ExtendSlider.Value))

    def _on_text_committed(self, sender, args):
        try:
            value = float(self.ExtendTextBox.Text)
        except ValueError:
            value = self.ExtendSlider.Value
        value = max(self.ExtendSlider.Minimum, min(self.ExtendSlider.Maximum, value))
        self.ExtendSlider.Value = value
        self.ExtendTextBox.Text = str(int(value))

    def _on_run(self, sender, args):
        auto_extend = bool(self.AutoExtendCheckBox.IsChecked)
        extend_mm = self.ExtendSlider.Value if auto_extend else 0.0
        self.result = GridOptionsResult(auto_extend=auto_extend, extend_mm=extend_mm)
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_grid_options(default_auto_extend=True, default_extend_mm=1500.0):
    """Shows the modal Grid Options window.

    Returns a GridOptionsResult, or None if the user cancelled.
    """
    window = GridOptionsWindow(default_auto_extend=default_auto_extend, default_extend_mm=default_extend_mm)
    window.ShowDialog()
    return window.result
