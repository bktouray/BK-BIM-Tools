# -*- coding: utf-8 -*-
"""Branded replacement for pyRevit's default `forms.CommandSwitchWindow`, used
anywhere the user needs to pick ONE of several dimensioning categories/tools
before proceeding (product owner, 2026-07-06: "I don't like the default
pyRevit interface when I click Structural Dimensions... make it nice"). Same
visual language as every other options window in the suite. Shared by
Structural Dimensions' Column/Beam/Footing/Slab picker and Smart Dimension's
top-level tool picker.
"""

import os

import clr

clr.AddReference("PresentationFramework")

from System.Windows import Thickness, VerticalAlignment
from System.Windows.Controls import Button, Orientation, StackPanel, TextBlock
from pyrevit import forms

from bkbim.ui.tokens import resolve_tokens_path


class CategoryPickerWindow(forms.WPFWindow):
    def __init__(self, title, subtitle, choices, icon_factory=None):
        """icon_factory: optional callable(choice) -> small WPF element or
        None, called once per choice - lets a caller (Structural Element
        Dimensions' Column/Beam/Footing/Slab picker) show a small pictogram
        next to each label without every picker needing one.
        """
        xaml_path = os.path.join(os.path.dirname(__file__), "CategoryPicker.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.Title = u"BK BIM Tools - {0}".format(title)
        self.TitleText.Text = title
        self.SubtitleText.Text = subtitle
        self.result = None

        choice_style = self.FindResource("ChoiceButton")
        for choice in choices:
            button = Button()
            button.Style = choice_style
            button.Content = self._button_content(choice, icon_factory)
            button.Click += self._make_click_handler(choice)
            self.ChoicesPanel.Children.Add(button)

        self.CancelButton.Click += self._on_cancel

    @staticmethod
    def _button_content(choice, icon_factory):
        icon = icon_factory(choice) if icon_factory else None
        if icon is None:
            return choice

        row = StackPanel()
        row.Orientation = Orientation.Horizontal
        icon.Margin = Thickness(0, 0, 12, 0)
        icon.VerticalAlignment = VerticalAlignment.Center
        row.Children.Add(icon)

        label = TextBlock()
        label.Text = choice
        label.VerticalAlignment = VerticalAlignment.Center
        row.Children.Add(label)
        return row

    def _make_click_handler(self, choice):
        def handler(sender, args):
            self.result = choice
            self.Close()
        return handler

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_category_picker(title, subtitle, choices, icon_factory=None):
    """Shows the branded category picker.

    Returns the chosen string, or None if the user cancelled.
    """
    window = CategoryPickerWindow(title, subtitle, choices, icon_factory=icon_factory)
    window.ShowDialog()
    return window.result
