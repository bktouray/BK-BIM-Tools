# -*- coding: utf-8 -*-
"""Branded options window for Auto Lintels.

Combines the original prompt chain into one BKBIM-styled dialog: opening
scope, base structural-framing type, structural material, lintel height and
side bearing.
"""

import os

from pyrevit import forms

from System.Windows import Visibility

from bkbim.ui.tokens import resolve_tokens_path

SKIP_MATERIAL = u"<Leave family default>"

SCOPE_ACTIVE_VIEW = u"Active view doors and windows"
SCOPE_WHOLE_MODEL = u"Whole model doors and windows"
SCOPE_MANUAL = u"Manually select doors and windows"

DEFAULT_HEIGHT_MM = 200.0
DEFAULT_BEARING_MM = 300.0


class AutoLintelOptionsResult(object):
    def __init__(self, scope, base_symbol, material_id, height_mm, bearing_mm):
        self.scope = scope
        self.base_symbol = base_symbol
        self.material_id = material_id
        self.height_mm = height_mm
        self.bearing_mm = bearing_mm


class AutoLintelOptionsWindow(forms.WPFWindow):
    def __init__(self, subtitle, materials, name_fn, pick_family_fn):
        xaml_path = os.path.join(os.path.dirname(__file__), "AutoLintelOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self._materials = materials
        self._pick_family_fn = pick_family_fn
        self._base_symbol = None
        self.result = None

        self.SubtitleText.Text = subtitle
        self.ActiveViewRadio.IsChecked = True

        self.HeightSlider.Value = DEFAULT_HEIGHT_MM
        self.HeightTextBox.Text = str(int(DEFAULT_HEIGHT_MM))
        self.BearingSlider.Value = DEFAULT_BEARING_MM
        self.BearingTextBox.Text = str(int(DEFAULT_BEARING_MM))

        self.MaterialCombo.Items.Add(SKIP_MATERIAL)
        preferred_index = 0
        for i, material in enumerate(materials):
            label = name_fn(material)
            self.MaterialCombo.Items.Add(label)
            lower = label.lower()
            if preferred_index == 0 and (
                    u"concrete" in lower or u"wood" in lower or u"metal" in lower):
                preferred_index = i + 1
        self.MaterialCombo.SelectedIndex = preferred_index

        self.HeightSlider.ValueChanged += self._on_height_slider_changed
        self.HeightTextBox.LostFocus += self._on_height_text_committed
        self.BearingSlider.ValueChanged += self._on_bearing_slider_changed
        self.BearingTextBox.LostFocus += self._on_bearing_text_committed

        self.ChooseFamilyButton.Click += self._on_choose_family
        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

    def _on_height_slider_changed(self, sender, args):
        self.HeightTextBox.Text = str(int(self.HeightSlider.Value))

    def _on_height_text_committed(self, sender, args):
        self._commit_slider_text(self.HeightTextBox, self.HeightSlider)

    def _on_bearing_slider_changed(self, sender, args):
        self.BearingTextBox.Text = str(int(self.BearingSlider.Value))

    def _on_bearing_text_committed(self, sender, args):
        self._commit_slider_text(self.BearingTextBox, self.BearingSlider)

    def _commit_slider_text(self, textbox, slider):
        try:
            value = float(textbox.Text)
        except ValueError:
            value = slider.Value
        value = max(slider.Minimum, min(slider.Maximum, value))
        slider.Value = value
        textbox.Text = str(int(value))

    def _on_choose_family(self, sender, args):
        symbol = self._pick_family_fn()
        if symbol is None:
            return
        self._base_symbol = symbol
        self.FamilyText.Text = u"{0} : {1}".format(_safe_name(symbol.Family), _safe_name(symbol))

    def _scope(self):
        if self.ManualRadio.IsChecked:
            return SCOPE_MANUAL
        if self.WholeModelRadio.IsChecked:
            return SCOPE_WHOLE_MODEL
        return SCOPE_ACTIVE_VIEW

    def _on_run(self, sender, args):
        if self._base_symbol is None:
            self.ValidationText.Text = u"Choose a base beam family first."
            self.ValidationText.Visibility = Visibility.Visible
            return
        if self.HeightSlider.Value <= 0:
            self.ValidationText.Text = u"Lintel height must be greater than 0."
            self.ValidationText.Visibility = Visibility.Visible
            return

        material_id = None
        index = self.MaterialCombo.SelectedIndex
        if index > 0:
            material_id = self._materials[index - 1].Id

        self.result = AutoLintelOptionsResult(
            scope=self._scope(),
            base_symbol=self._base_symbol,
            material_id=material_id,
            height_mm=self.HeightSlider.Value,
            bearing_mm=self.BearingSlider.Value)
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def _safe_name(el):
    try:
        return el.Name
    except Exception:
        return u"?"


def show_auto_lintel_options(subtitle, materials, name_fn, pick_family_fn):
    window = AutoLintelOptionsWindow(subtitle, materials, name_fn, pick_family_fn)
    window.ShowDialog()
    return window.result
