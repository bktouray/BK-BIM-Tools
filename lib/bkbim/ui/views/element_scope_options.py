# -*- coding: utf-8 -*-
"""Branded replacement for the "auto-detect from a level vs manually select"
wizard step, shared by Floors to Footings and PCC Blinding (both used the
identical forms.CommandSwitchWindow + forms.SelectFromList pair before -
extracted here once a 2nd consumer needed the same thing, per this suite's
usual "2nd consumer = extract" rule).
"""

import os

from pyrevit import forms

from System.Windows import Visibility

from bkbim.ui.tokens import resolve_tokens_path

MODE_AUTO = u"auto"
MODE_MANUAL = u"manual"


class ElementScopeOptionsResult(object):
    def __init__(self, mode, level):
        self.mode = mode  # MODE_AUTO | MODE_MANUAL
        self.level = level  # Level, only set when mode == MODE_AUTO


class ElementScopeOptionsWindow(forms.WPFWindow):
    def __init__(self, title, subtitle, auto_label, manual_label, manual_help, levels, name_fn):
        xaml_path = os.path.join(os.path.dirname(__file__), "ElementScopeOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self._levels = levels
        self._manual_help = manual_help
        self.result = None

        self.Title = u"BK BIM Tools - {0}".format(title)
        self.TitleText.Text = title
        self.SubtitleText.Text = subtitle
        self.AutoRadio.Content = auto_label
        self.ManualRadio.Content = manual_label

        for lv in levels:
            self.LevelCombo.Items.Add(name_fn(lv))
        if levels:
            self.LevelCombo.SelectedIndex = 0

        self.AutoRadio.IsChecked = True
        self._update_mode_panels()

        self.AutoRadio.Checked += self._on_mode_changed
        self.ManualRadio.Checked += self._on_mode_changed
        self.ContinueButton.Click += self._on_continue
        self.CancelButton.Click += self._on_cancel

    def _update_mode_panels(self):
        auto = bool(self.AutoRadio.IsChecked)
        self.LevelPanel.Visibility = Visibility.Visible if auto else Visibility.Collapsed
        self.ManualHelpText.Visibility = Visibility.Collapsed if auto else Visibility.Visible
        if not auto:
            self.ManualHelpText.Text = self._manual_help

    def _on_mode_changed(self, sender, args):
        self._update_mode_panels()

    def _on_continue(self, sender, args):
        if self.AutoRadio.IsChecked:
            index = self.LevelCombo.SelectedIndex
            level = self._levels[index] if 0 <= index < len(self._levels) else None
            self.result = ElementScopeOptionsResult(MODE_AUTO, level)
        else:
            self.result = ElementScopeOptionsResult(MODE_MANUAL, None)
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_element_scope_options(title, subtitle, auto_label, manual_label, manual_help, levels, name_fn):
    """Shows the branded scope picker.

    Returns an ElementScopeOptionsResult, or None if the user cancelled.
    """
    window = ElementScopeOptionsWindow(
        title, subtitle, auto_label, manual_label, manual_help, levels, name_fn)
    window.ShowDialog()
    return window.result
