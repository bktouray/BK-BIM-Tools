# -*- coding: utf-8 -*-
"""Shared branded single-select list picker.

Use this where older flows used pyRevit's default ``forms.SelectFromList``
for one choice before a larger BK wizard/options window can continue.
"""

import os

import clr

clr.AddReference("PresentationCore")
clr.AddReference("PresentationFramework")
clr.AddReference("WindowsBase")

from System.Windows import Visibility
from System.Windows.Controls import SelectionMode
from pyrevit import forms

from bkbim.ui.tokens import resolve_tokens_path

try:
    unicode
except NameError:
    unicode = str


class ListPickerWindow(forms.WPFWindow):
    def __init__(self, title, subtitle, labels, default_label=None,
                 default_labels=None, multiselect=False):
        xaml_path = os.path.join(os.path.dirname(__file__), "ListPicker.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.Title = u"BK BIM Tools - {0}".format(title)
        self.TitleText.Text = title
        self.SubtitleText.Text = subtitle or u""
        self._labels = list(labels)
        self._multiselect = multiselect
        self.result = None
        if multiselect:
            self.ItemsList.SelectionMode = SelectionMode.Extended

        self._apply_filter(
            u"", default_label=default_label, default_labels=default_labels)

        self.SearchBox.TextChanged += self._on_search_changed
        self.ItemsList.MouseDoubleClick += self._on_double_click
        self.SelectButton.Click += self._on_select
        self.CancelButton.Click += self._on_cancel

    def _apply_filter(self, query, default_label=None, default_labels=None):
        query = (query or u"").lower()
        selected = set(unicode(i) for i in self.ItemsList.SelectedItems)
        if default_labels:
            selected.update(unicode(i) for i in default_labels)
        self.ItemsList.Items.Clear()
        for label in self._labels:
            if query in unicode(label).lower():
                self.ItemsList.Items.Add(label)
        if self._multiselect:
            for item in self.ItemsList.Items:
                if unicode(item) in selected:
                    self.ItemsList.SelectedItems.Add(item)
        elif default_label and default_label in self._labels:
            self.ItemsList.SelectedItem = default_label
        elif self.ItemsList.Items.Count == 1:
            self.ItemsList.SelectedIndex = 0

    def _on_search_changed(self, sender, args):
        self._apply_filter(self.SearchBox.Text)

    def _on_double_click(self, sender, args):
        if self._multiselect:
            return
        if self.ItemsList.SelectedItem is not None:
            self._finish(self.ItemsList.SelectedItem)

    def _on_select(self, sender, args):
        if self._multiselect:
            selected = [unicode(i) for i in self.ItemsList.SelectedItems]
            if not selected:
                self.ErrorText.Text = u"Choose at least one item."
                self.ErrorText.Visibility = Visibility.Visible
                return
            self.result = selected
            self.Close()
        else:
            if self.ItemsList.SelectedItem is None:
                self.ErrorText.Text = u"Choose an item first."
                self.ErrorText.Visibility = Visibility.Visible
                return
            self._finish(self.ItemsList.SelectedItem)

    def _finish(self, label):
        self.result = unicode(label)
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_list_picker(title, subtitle, labels, default_label=None):
    """Shows a branded single-select picker and returns the chosen label."""
    window = ListPickerWindow(title, subtitle, labels, default_label=default_label)
    window.ShowDialog()
    return window.result


def show_multi_list_picker(title, subtitle, labels, default_labels=None):
    """Shows a branded multi-select picker and returns chosen labels."""
    window = ListPickerWindow(
        title, subtitle, labels, default_labels=default_labels,
        multiselect=True)
    window.ShowDialog()
    return window.result
