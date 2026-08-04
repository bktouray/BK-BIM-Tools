# -*- coding: utf-8 -*-
"""Branded options window for the first DWV collector slice."""

import os

from pyrevit import forms

from bkbim.ui.tokens import resolve_tokens_path

try:
    unicode
except NameError:
    unicode = str


class DwvCollectorOptionsResult(object):
    def __init__(self, collector_diameter_mm, slope_percent,
                 wc_drop_below_level_mm):
        self.collector_diameter_mm = collector_diameter_mm
        self.slope_percent = slope_percent
        self.wc_drop_below_level_mm = wc_drop_below_level_mm


def _set_text(textbox, value):
    textbox.Text = u"{0:g}".format(float(value))


def _number_from_text(textbox, label, allow_zero=False):
    try:
        value = float(textbox.Text)
    except (TypeError, ValueError):
        raise ValueError(u"{0}: enter a valid number.".format(label))
    if allow_zero:
        if value < 0:
            raise ValueError(u"{0}: enter 0 or a positive value.".format(label))
    elif value <= 0:
        raise ValueError(u"{0}: enter a value greater than 0.".format(label))
    return value


class DwvCollectorOptionsWindow(forms.WPFWindow):
    def __init__(self, title, default_collector_diameter_mm,
                 minimum_collector_diameter_mm, default_slope_percent):
        xaml_path = os.path.join(os.path.dirname(__file__), "DwvCollectorOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.Title = u"BK BIM Tools - {0}".format(title)
        self.result = None
        self._minimum_collector_diameter_mm = minimum_collector_diameter_mm

        _set_text(self.CollectorDiameterText, default_collector_diameter_mm)
        _set_text(self.SlopeText, default_slope_percent)
        _set_text(self.WcDropBelowLevelText, 150.0)

        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

    def _on_run(self, sender, args):
        self.ErrorText.Text = u""
        try:
            diameter = _number_from_text(
                self.CollectorDiameterText, u"Collector diameter")
            if diameter < self._minimum_collector_diameter_mm:
                raise ValueError(
                    u"Collector diameter must be at least {0:g} mm, the "
                    u"largest selected fixture drain connector.".format(
                        float(self._minimum_collector_diameter_mm)))
            slope = _number_from_text(self.SlopeText, u"Slope")
            wc_drop = _number_from_text(
                self.WcDropBelowLevelText, u"WC drop below level/slab",
                allow_zero=True)
        except ValueError as error:
            self.ErrorText.Text = unicode(error)
            return

        self.result = DwvCollectorOptionsResult(
            collector_diameter_mm=diameter,
            slope_percent=slope,
            wc_drop_below_level_mm=wc_drop)
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_dwv_collector_options(title, default_collector_diameter_mm,
                               minimum_collector_diameter_mm,
                               default_slope_percent):
    window = DwvCollectorOptionsWindow(
        title=title,
        default_collector_diameter_mm=default_collector_diameter_mm,
        minimum_collector_diameter_mm=minimum_collector_diameter_mm,
        default_slope_percent=default_slope_percent)
    window.ShowDialog()
    return window.result
