# -*- coding: utf-8 -*-
"""Branded replacement for PCC Blinding's remaining default-pyRevit prompts:
the depth/offset `forms.ask_for_string` calls and the family/material
`forms.SelectFromList` calls. The family picker itself
(`bkbim.automation.familyutils.pick_family_symbol`, with its "load from .rfa"
loop) is left as-is and invoked from the "Choose…" button - it's shared by
several other automation tools beyond this one.
"""

import os

from pyrevit import forms

from System.Windows import Visibility

from bkbim.ui.tokens import resolve_tokens_path

SKIP_MATERIAL = u"<Leave family default>"

DEFAULT_DEPTH_MM = 75.0
DEFAULT_OFFSET_MM = 100.0


class PCCBlindingOptionsResult(object):
    def __init__(self, base_symbol, depth_mm, offset_mm, material_id):
        self.base_symbol = base_symbol
        self.depth_mm = depth_mm
        self.offset_mm = offset_mm
        self.material_id = material_id  # ElementId or None


class PCCBlindingOptionsWindow(forms.WPFWindow):
    def __init__(self, subtitle, materials, name_fn, pick_family_fn):
        xaml_path = os.path.join(os.path.dirname(__file__), "PCCBlindingOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self._materials = materials
        self._pick_family_fn = pick_family_fn
        self._base_symbol = None
        self.result = None

        self.SubtitleText.Text = subtitle

        self.DepthSlider.Value = DEFAULT_DEPTH_MM
        self.DepthTextBox.Text = str(int(DEFAULT_DEPTH_MM))
        self.OffsetSlider.Value = DEFAULT_OFFSET_MM
        self.OffsetTextBox.Text = str(int(DEFAULT_OFFSET_MM))

        self.MaterialCombo.Items.Add(SKIP_MATERIAL)
        preferred_index = 0
        for i, m in enumerate(materials):
            self.MaterialCombo.Items.Add(name_fn(m))
            if preferred_index == 0 and u"red stone" in name_fn(m).lower():
                preferred_index = i + 1
        self.MaterialCombo.SelectedIndex = preferred_index

        self.DepthSlider.ValueChanged += self._on_depth_slider_changed
        self.DepthTextBox.LostFocus += self._on_depth_text_committed
        self.OffsetSlider.ValueChanged += self._on_offset_slider_changed
        self.OffsetTextBox.LostFocus += self._on_offset_text_committed

        self.ChooseFamilyButton.Click += self._on_choose_family
        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

    def _on_depth_slider_changed(self, sender, args):
        self.DepthTextBox.Text = str(int(self.DepthSlider.Value))

    def _on_depth_text_committed(self, sender, args):
        try:
            value = float(self.DepthTextBox.Text)
        except ValueError:
            value = self.DepthSlider.Value
        value = max(self.DepthSlider.Minimum, min(self.DepthSlider.Maximum, value))
        self.DepthSlider.Value = value
        self.DepthTextBox.Text = str(int(value))

    def _on_offset_slider_changed(self, sender, args):
        self.OffsetTextBox.Text = str(int(self.OffsetSlider.Value))

    def _on_offset_text_committed(self, sender, args):
        try:
            value = float(self.OffsetTextBox.Text)
        except ValueError:
            value = self.OffsetSlider.Value
        value = max(self.OffsetSlider.Minimum, min(self.OffsetSlider.Maximum, value))
        self.OffsetSlider.Value = value
        self.OffsetTextBox.Text = str(int(value))

    def _on_choose_family(self, sender, args):
        symbol = self._pick_family_fn()
        if symbol is None:
            return
        self._base_symbol = symbol
        self.FamilyText.Text = u"{0} : {1}".format(
            _safe_name(symbol.Family), _safe_name(symbol))

    def _on_run(self, sender, args):
        if self._base_symbol is None:
            self.ValidationText.Text = u"Choose a base blinding pad family first."
            self.ValidationText.Visibility = Visibility.Visible
            return
        if self.DepthSlider.Value <= 0 or self.OffsetSlider.Value <= 0:
            self.ValidationText.Text = u"Depth and offset must be greater than 0."
            self.ValidationText.Visibility = Visibility.Visible
            return

        index = self.MaterialCombo.SelectedIndex
        material_id = None
        if index > 0:
            material_id = self._materials[index - 1].Id

        self.result = PCCBlindingOptionsResult(
            base_symbol=self._base_symbol,
            depth_mm=self.DepthSlider.Value,
            offset_mm=self.OffsetSlider.Value,
            material_id=material_id,
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


def show_pcc_blinding_options(subtitle, materials, name_fn, pick_family_fn):
    """Shows the branded options window.

    Returns a PCCBlindingOptionsResult, or None if the user cancelled.
    """
    window = PCCBlindingOptionsWindow(subtitle, materials, name_fn, pick_family_fn)
    window.ShowDialog()
    return window.result
