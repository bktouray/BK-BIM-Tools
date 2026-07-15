# -*- coding: utf-8 -*-
"""Branded replacement for familyutils.pick_family_symbol's default
`forms.SelectFromList` (which baked a "Load family from file" entry into the
list itself, then re-showed the list in a while-loop after a successful
load). Same behavior here, just as a real window: a searchable list of
"Family : Type" options, a "Load family from file" button that reloads the
list in place instead of re-opening a dialog, single selection, Cancel
returns None.
"""

import os

from pyrevit import forms

from System.Windows import Visibility

from bkbim.ui.tokens import resolve_tokens_path

_LOAD_LABEL = u"⬇  Load family from file (.rfa)…"


class FamilySymbolPickerWindow(forms.WPFWindow):
    def __init__(self, subtitle, collect_fn, load_fn):
        xaml_path = os.path.join(os.path.dirname(__file__), "FamilySymbolPicker.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self._collect_fn = collect_fn
        self._load_fn = load_fn
        self._symbols = {}
        self._labels = []
        self.result = None

        self.SubtitleText.Text = subtitle
        self._reload(select_label=None)

        self.SearchBox.TextChanged += self._on_search_changed
        self.SymbolsList.MouseDoubleClick += self._on_list_double_click
        self.LoadFamilyButton.Click += self._on_load_family
        self.SelectButton.Click += self._on_select
        self.CancelButton.Click += self._on_cancel

    def _reload(self, select_label):
        self._symbols = self._collect_fn()
        self._labels = sorted(self._symbols.keys())
        self._apply_filter(self.SearchBox.Text if self.SearchBox.Text else u"", select_label)

    def _apply_filter(self, query, select_label=None):
        query = (query or u"").lower()
        self.SymbolsList.Items.Clear()
        for label in self._labels:
            if query in label.lower():
                self.SymbolsList.Items.Add(label)
        if select_label and select_label in self._labels:
            self.SymbolsList.SelectedItem = select_label
        elif self.SymbolsList.Items.Count == 1:
            self.SymbolsList.SelectedIndex = 0

    def _on_search_changed(self, sender, args):
        self._apply_filter(self.SearchBox.Text)

    def _on_list_double_click(self, sender, args):
        if self.SymbolsList.SelectedItem is not None:
            self._finish(self.SymbolsList.SelectedItem)

    def _on_load_family(self, sender, args):
        attempted = self._load_fn()
        if attempted:
            self._reload(select_label=None)

    def _on_select(self, sender, args):
        label = self.SymbolsList.SelectedItem
        if label is None:
            self.ValidationText.Text = u"Choose a family type first."
            self.ValidationText.Visibility = Visibility.Visible
            return
        self._finish(label)

    def _finish(self, label):
        self.result = self._symbols.get(label)
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_family_symbol_picker(subtitle, collect_fn, load_fn):
    """Shows the branded family/type picker.

    collect_fn: callable() -> dict {"Family : Type" -> FamilySymbol}.
    load_fn: callable() -> bool, True if a family load was attempted (same
    contract as familyutils.load_family_from_file).

    Returns the chosen FamilySymbol, or None if the user cancelled.
    """
    window = FamilySymbolPickerWindow(subtitle, collect_fn, load_fn)
    window.ShowDialog()
    return window.result
