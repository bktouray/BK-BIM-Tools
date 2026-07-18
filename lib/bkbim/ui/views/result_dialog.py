# -*- coding: utf-8 -*-
"""Shared branded result/message dialog for BK BIM Tools.

Many pushbuttons already have proper branded option windows, but still end
with pyRevit's default ``forms.alert`` for success, rollback and error
messages. This small shared dialog gives every tool the same BK-style ending
without forcing each feature to maintain its own result XAML.
"""

import os

from pyrevit import forms

from bkbim.ui.tokens import resolve_tokens_path


class ResultDialogWindow(forms.WPFWindow):
    def __init__(self, title, message, subtitle=None):
        xaml_path = os.path.join(os.path.dirname(__file__), "ResultDialog.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.Title = u"BK BIM Tools - {0}".format(title)
        self.TitleText.Text = title
        self.SubtitleText.Text = subtitle or u""
        self.MessageText.Text = message or u"Done."
        self.DoneButton.Click += self._on_done

    def _on_done(self, sender, args):
        self.Close()


def show_result(title, message, subtitle=None):
    """Shows a branded one-button result dialog."""
    window = ResultDialogWindow(title, message, subtitle=subtitle)
    window.ShowDialog()
