# -*- coding: utf-8 -*-
"""Shared branded yes/no confirmation dialog for BK BIM Tools."""

import os

from pyrevit import forms

from bkbim.ui.tokens import resolve_tokens_path


class ConfirmationDialogWindow(forms.WPFWindow):
    def __init__(self, title, message, subtitle=None, yes_text=u"Yes", no_text=u"No"):
        xaml_path = os.path.join(os.path.dirname(__file__), "ConfirmationDialog.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.Title = u"BK BIM Tools - {0}".format(title)
        self.TitleText.Text = title
        self.SubtitleText.Text = subtitle or u""
        self.MessageText.Text = message or u"Continue?"
        self.YesButton.Content = yes_text
        self.NoButton.Content = no_text
        self.result = False

        self.YesButton.Click += self._on_yes
        self.NoButton.Click += self._on_no

    def _on_yes(self, sender, args):
        self.result = True
        self.Close()

    def _on_no(self, sender, args):
        self.result = False
        self.Close()


def show_confirmation(title, message, subtitle=None, yes_text=u"Yes", no_text=u"No"):
    """Shows a branded yes/no dialog and returns True for yes."""
    window = ConfirmationDialogWindow(
        title, message, subtitle=subtitle, yes_text=yes_text, no_text=no_text)
    window.ShowDialog()
    return bool(window.result)
