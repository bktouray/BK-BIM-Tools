# -*- coding: utf-8 -*-
"""Branded replacement for Floors to Footings' remaining default-pyRevit
prompts: the base-family/material `forms.SelectFromList` calls and the
auto-size/delete-source `forms.alert(yes=True, no=True)` choices. The family
picker itself (`bkbim.automation.familyutils.pick_family_symbol`, with its
"load from .rfa" loop) is left as-is and invoked from the "Choose…" button -
it's shared by several other automation tools beyond this one, so replacing
it is a separate, larger effort.
"""

import os

from pyrevit import forms

from System.Windows import Visibility

from bkbim.ui.tokens import resolve_tokens_path

SKIP_MATERIAL = u"<Leave family default>"


class FloorsToFootingsOptionsResult(object):
    def __init__(self, base_symbol, auto_size, material_id, delete_source):
        self.base_symbol = base_symbol
        self.auto_size = auto_size
        self.material_id = material_id  # ElementId or None
        self.delete_source = delete_source


class FloorsToFootingsOptionsWindow(forms.WPFWindow):
    def __init__(self, subtitle, materials, name_fn, pick_family_fn):
        xaml_path = os.path.join(os.path.dirname(__file__), "FloorsToFootingsOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self._materials = materials
        self._pick_family_fn = pick_family_fn
        self._base_symbol = None
        self.result = None

        self.SubtitleText.Text = subtitle

        self.MaterialCombo.Items.Add(SKIP_MATERIAL)
        for m in materials:
            self.MaterialCombo.Items.Add(name_fn(m))
        self.MaterialCombo.SelectedIndex = 0

        self.AutoSizeCheckBox.IsChecked = True
        self.DeleteSourceCheckBox.IsChecked = True

        self.ChooseFamilyButton.Click += self._on_choose_family
        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

    def _on_choose_family(self, sender, args):
        symbol = self._pick_family_fn()
        if symbol is None:
            return
        self._base_symbol = symbol
        self.FamilyText.Text = u"{0} : {1}".format(
            _safe_name(symbol.Family), _safe_name(symbol))

    def _on_run(self, sender, args):
        if self._base_symbol is None:
            self.ValidationText.Text = u"Choose a base footing family first."
            self.ValidationText.Visibility = Visibility.Visible
            return

        index = self.MaterialCombo.SelectedIndex
        material_id = None
        if index > 0:
            material_id = self._materials[index - 1].Id

        self.result = FloorsToFootingsOptionsResult(
            base_symbol=self._base_symbol,
            auto_size=bool(self.AutoSizeCheckBox.IsChecked),
            material_id=material_id,
            delete_source=bool(self.DeleteSourceCheckBox.IsChecked),
        )
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def _safe_name(el):
    try:
        return el.Name
    except Exception:
        return u"?"


def show_floors_to_footings_options(subtitle, materials, name_fn, pick_family_fn):
    """Shows the branded options window.

    Returns a FloorsToFootingsOptionsResult, or None if the user cancelled.
    """
    window = FloorsToFootingsOptionsWindow(subtitle, materials, name_fn, pick_family_fn)
    window.ShowDialog()
    return window.result
