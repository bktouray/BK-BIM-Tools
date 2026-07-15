# -*- coding: utf-8 -*-
"""Branded replacement for pyRevit's default `forms.SelectFromList` (multiselect),
used by Master Export to pick which BOQ categories go into one combined workbook.
Mirrors the drag-multiselect ListBox convention already used by Wall & Opening /
Structural Dimensions' type filters - see listbox_drag_select.py.
"""

import os

from pyrevit import forms

from bkbim.ui.tokens import resolve_tokens_path
from bkbim.ui.views.listbox_drag_select import enable_drag_multiselect


class BOQMasterExportOptionsWindow(forms.WPFWindow):
    def __init__(self, labels):
        xaml_path = os.path.join(os.path.dirname(__file__), "BOQMasterExportOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self._labels = labels
        self.result = None

        for label in labels:
            self.CategoriesList.Items.Add(label)

        enable_drag_multiselect(self.CategoriesList)

        self.SelectAllButton.Click += self._on_select_all
        self.ExportButton.Click += self._on_export
        self.CancelButton.Click += self._on_cancel

    def _on_select_all(self, sender, args):
        self.CategoriesList.SelectedItems.Clear()
        for item in self.CategoriesList.Items:
            self.CategoriesList.SelectedItems.Add(item)

    def _on_export(self, sender, args):
        selected = list(self.CategoriesList.SelectedItems)
        if not selected:
            return
        self.result = selected
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_master_export_options(labels):
    """Shows the branded Master Export category picker.

    Returns the list of selected category labels, or None if the user
    cancelled (or closed the window without exporting anything).
    """
    window = BOQMasterExportOptionsWindow(labels)
    window.ShowDialog()
    return window.result
