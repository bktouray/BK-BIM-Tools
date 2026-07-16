# -*- coding: utf-8 -*-
"""Run options for the combined Water Supply pushbutton.

This is intentionally just the start panel: choose which systems to run and
which pipe type(s) to use. The actual routing wizard remains in
revit/adapter/mep/water_supply_flow.py so the combined button reuses the same
proven Cold/Hot vertical slices instead of forking routing behavior.
"""

import os

from pyrevit import forms

from bkbim.ui.tokens import resolve_tokens_path

try:
    unicode
except NameError:
    unicode = str


class WaterSupplyOptionsResult(object):
    def __init__(self, run_cold, run_hot, cold_pipe_type_name, hot_pipe_type_name):
        self.run_cold = run_cold
        self.run_hot = run_hot
        self.cold_pipe_type_name = cold_pipe_type_name
        self.hot_pipe_type_name = hot_pipe_type_name


def _set_combo_to_value(combo, value):
    if not value:
        if combo.Items.Count:
            combo.SelectedIndex = 0
        return
    for i in range(combo.Items.Count):
        if unicode(combo.Items[i]) == unicode(value):
            combo.SelectedIndex = i
            return
    if combo.Items.Count:
        combo.SelectedIndex = 0


def _selected_text(combo):
    item = combo.SelectedItem
    return None if item is None else unicode(item)


class WaterSupplyOptionsWindow(forms.WPFWindow):
    def __init__(self, pipe_type_names, remembered_cold=None, remembered_hot=None):
        xaml_path = os.path.join(os.path.dirname(__file__), "WaterSupplyOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.result = None
        self._pipe_type_names = list(pipe_type_names)

        for name in self._pipe_type_names:
            self.ColdPipeTypeCombo.Items.Add(name)
            self.HotPipeTypeCombo.Items.Add(name)

        _set_combo_to_value(self.ColdPipeTypeCombo, remembered_cold)
        _set_combo_to_value(self.HotPipeTypeCombo, remembered_hot or remembered_cold)

        self.ColdCheck.IsChecked = True
        self.HotCheck.IsChecked = True
        self.UseSamePipeTypeCheck.IsChecked = (remembered_hot is None or remembered_hot == remembered_cold)

        self.ColdCheck.Checked += self._on_option_changed
        self.ColdCheck.Unchecked += self._on_option_changed
        self.HotCheck.Checked += self._on_option_changed
        self.HotCheck.Unchecked += self._on_option_changed
        self.UseSamePipeTypeCheck.Checked += self._on_option_changed
        self.UseSamePipeTypeCheck.Unchecked += self._on_option_changed
        self.ColdPipeTypeCombo.SelectionChanged += self._on_option_changed

        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

        self._refresh_enabled_state()

    def _on_option_changed(self, sender, args):
        self._refresh_enabled_state()

    def _refresh_enabled_state(self):
        run_cold = self.ColdCheck.IsChecked == True
        run_hot = self.HotCheck.IsChecked == True
        use_same = (self.UseSamePipeTypeCheck.IsChecked == True and
                    run_cold and run_hot)

        self.ColdPipeTypeCombo.IsEnabled = run_cold
        self.HotPipeTypeCombo.IsEnabled = run_hot and not use_same
        self.UseSamePipeTypeCheck.IsEnabled = run_cold and run_hot

        if use_same and self.ColdPipeTypeCombo.SelectedIndex >= 0:
            self.HotPipeTypeCombo.SelectedIndex = self.ColdPipeTypeCombo.SelectedIndex

        if run_cold and run_hot:
            self.StatusText.Text = (
                u"Cold Water will run first, then Hot Water. Hot Water uses "
                u"the configured hot/cold offset so the routes do not overlap.")
        elif run_cold:
            self.StatusText.Text = u"Only Domestic Cold Water will be routed."
        elif run_hot:
            self.StatusText.Text = u"Only Domestic Hot Water will be routed."
        else:
            self.StatusText.Text = u"Select at least one system to route."

    def _on_run(self, sender, args):
        run_cold = self.ColdCheck.IsChecked == True
        run_hot = self.HotCheck.IsChecked == True
        use_same = (self.UseSamePipeTypeCheck.IsChecked == True and
                    run_cold and run_hot)

        if not run_cold and not run_hot:
            self.StatusText.Text = u"Select Cold Water, Hot Water, or both before running."
            return

        cold_pipe_type_name = _selected_text(self.ColdPipeTypeCombo)
        hot_pipe_type_name = cold_pipe_type_name if use_same else _selected_text(self.HotPipeTypeCombo)

        if run_cold and not cold_pipe_type_name:
            self.StatusText.Text = u"Pick a Cold Water pipe type."
            return
        if run_hot and not hot_pipe_type_name:
            self.StatusText.Text = u"Pick a Hot Water pipe type."
            return

        self.result = WaterSupplyOptionsResult(
            run_cold=run_cold,
            run_hot=run_hot,
            cold_pipe_type_name=cold_pipe_type_name,
            hot_pipe_type_name=hot_pipe_type_name)
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_water_supply_options(pipe_type_names, remembered_cold=None, remembered_hot=None):
    """Shows the combined Water Supply start window.

    Returns WaterSupplyOptionsResult, or None if the user cancelled.
    """
    window = WaterSupplyOptionsWindow(
        pipe_type_names,
        remembered_cold=remembered_cold,
        remembered_hot=remembered_hot)
    window.ShowDialog()
    return window.result
