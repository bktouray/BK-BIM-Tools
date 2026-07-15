# -*- coding: utf-8 -*-
"""Branded replacement for BOQ Export's completion `forms.alert(options=[...])`
(product owner asked for the default-pyRevit-interface buttons across the
suite to get a proper branded window, same as CategoryPicker/AutoMarkOptions/
etc). One shared window covers both the per-category/Master Export completion
summary and the Split Workbook completion - both are just "here's the saved
path, here's what happened per item, Open folder or Done."
"""

import os

from System.Windows import Visibility
from pyrevit import forms

from bkbim.ui.tokens import resolve_tokens_path
from bkbim.ui.views.summary_rows import render_summary_rows


class BOQResultWindow(forms.WPFWindow):
    def __init__(self, title, path, lines):
        xaml_path = os.path.join(os.path.dirname(__file__), "BOQResult.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.Title = u"BK BIM Tools - {0}".format(title)
        self.TitleText.Text = title
        self.PathBox.Text = path
        self.open_folder = False
        self._folder = os.path.dirname(path)

        if lines:
            render_summary_rows(self, self.SummaryPanel, lines)
        else:
            self.SummaryHeading.Visibility = Visibility.Collapsed

        self.OpenFolderButton.Click += self._on_open_folder
        self.DoneButton.Click += self._on_done

    def _on_open_folder(self, sender, args):
        self.open_folder = True
        try:
            os.startfile(self._folder)
        except Exception:
            pass

    def _on_done(self, sender, args):
        self.Close()


def show_boq_result(title, path, lines):
    """Shows the branded BOQ result window. Returns nothing - "Open folder"
    opens the folder immediately (can be clicked more than once) and "Done"
    just closes the window.
    """
    window = BOQResultWindow(title, path, lines)
    window.ShowDialog()
