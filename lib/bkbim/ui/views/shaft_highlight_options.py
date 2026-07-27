# -*- coding: utf-8 -*-
"""Code-behind for HighlightShaftOptions.xaml.

Matches the suite's WPF/token pattern: one modal review window, explicit
target view selection, fill controls, line-style choices, and compact result
object handed back to the Revit adapter.
"""

import os

from pyrevit import forms

from System.Windows import Thickness, Visibility
from System.Windows.Media import Color as WpfColor, SolidColorBrush

from bkbim.ui.tokens import resolve_tokens_path
from bkbim.ui.views.listbox_drag_select import enable_drag_multiselect

FILL_MODE_EXISTING = u"existing"
FILL_MODE_CUSTOM = u"custom"


class ShaftHighlightOptionsResult(object):
    def __init__(self, selected_views, fill_mode, filled_region_type, red, green, blue,
                 boundary_style, draw_x, x_style, group_results):
        self.selected_views = selected_views
        self.fill_mode = fill_mode
        self.filled_region_type = filled_region_type
        self.red = red
        self.green = green
        self.blue = blue
        self.boundary_style = boundary_style
        self.draw_x = draw_x
        self.x_style = x_style
        self.group_results = group_results


class ShaftHighlightOptionsWindow(forms.WPFWindow):
    def __init__(self, title, views, active_view, view_name_fn, filled_region_types,
                 region_type_name_fn, line_styles, line_style_name_fn,
                 default_rgb=(92, 182, 214)):
        xaml_path = os.path.join(os.path.dirname(__file__), "ShaftHighlightOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.result = None
        self._views = views
        self._filled_region_types = filled_region_types
        self._line_styles = line_styles

        self.Title = u"BK BIM Tools - {0}".format(title)
        self.TitleText.Text = title
        self.SubtitleText.Text = (
            u"Fill shaft openings in plan views, rebuild previous highlights, "
            u"and leave manually drawn filled regions alone.")

        for v in views:
            self.ViewsList.Items.Add(view_name_fn(v))
        enable_drag_multiselect(self.ViewsList)
        for i, v in enumerate(views):
            if active_view is not None and v.Id == active_view.Id:
                self.ViewsList.SelectedIndex = i
                break
        if self.ViewsList.SelectedIndex < 0 and views:
            self.ViewsList.SelectedIndex = 0

        for fr_type in filled_region_types:
            self.FillTypeCombo.Items.Add(region_type_name_fn(fr_type))
        if filled_region_types:
            self.FillTypeCombo.SelectedIndex = 0

        for style in line_styles:
            label = line_style_name_fn(style)
            self.BoundaryLineStyleCombo.Items.Add(label)
            self.XLineStyleCombo.Items.Add(label)
        if line_styles:
            self.BoundaryLineStyleCombo.SelectedIndex = 0
            self.XLineStyleCombo.SelectedIndex = 0

        self.ExistingFillRadio.IsChecked = True
        self.DrawXCheckBox.IsChecked = True
        self.GroupResultsCheckBox.IsChecked = True

        self.RedSlider.Value = default_rgb[0]
        self.GreenSlider.Value = default_rgb[1]
        self.BlueSlider.Value = default_rgb[2]
        self._sync_color_text()
        self._update_fill_panels()

        self.ExistingFillRadio.Checked += self._on_fill_mode_changed
        self.CustomFillRadio.Checked += self._on_fill_mode_changed
        self.RedSlider.ValueChanged += self._on_color_changed
        self.GreenSlider.ValueChanged += self._on_color_changed
        self.BlueSlider.ValueChanged += self._on_color_changed
        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

    def _on_fill_mode_changed(self, sender, args):
        self._update_fill_panels()

    def _update_fill_panels(self):
        use_existing = bool(self.ExistingFillRadio.IsChecked)
        self.FillTypeCombo.Visibility = Visibility.Visible if use_existing else Visibility.Collapsed
        self.CustomColorPanel.Visibility = Visibility.Collapsed if use_existing else Visibility.Visible

    def _on_color_changed(self, sender, args):
        self._sync_color_text()

    def _slider_value(self, slider):
        return int(round(slider.Value))

    def _sync_color_text(self):
        r = self._slider_value(self.RedSlider)
        g = self._slider_value(self.GreenSlider)
        b = self._slider_value(self.BlueSlider)
        self.RedText.Text = unicode(r)
        self.GreenText.Text = unicode(g)
        self.BlueText.Text = unicode(b)
        self.ColorSwatch.Fill = SolidColorBrush(WpfColor.FromRgb(r, g, b))

    def _selected_indices(self, listbox):
        return [listbox.Items.IndexOf(item) for item in listbox.SelectedItems]

    def _on_run(self, sender, args):
        selected_views = [
            self._views[i] for i in self._selected_indices(self.ViewsList)
            if 0 <= i < len(self._views)]
        if not selected_views:
            forms.alert(u"Select at least one plan view.", title=self.Title)
            return

        fill_mode = FILL_MODE_CUSTOM if self.CustomFillRadio.IsChecked else FILL_MODE_EXISTING
        fill_index = self.FillTypeCombo.SelectedIndex
        filled_region_type = (
            self._filled_region_types[fill_index]
            if 0 <= fill_index < len(self._filled_region_types) else None)
        if fill_mode == FILL_MODE_EXISTING and filled_region_type is None:
            forms.alert(u"No filled region type is selected.", title=self.Title)
            return

        boundary_index = self.BoundaryLineStyleCombo.SelectedIndex
        x_index = self.XLineStyleCombo.SelectedIndex
        boundary_style = self._line_styles[boundary_index] if 0 <= boundary_index < len(self._line_styles) else None
        x_style = self._line_styles[x_index] if 0 <= x_index < len(self._line_styles) else None

        self.result = ShaftHighlightOptionsResult(
            selected_views=selected_views,
            fill_mode=fill_mode,
            filled_region_type=filled_region_type,
            red=self._slider_value(self.RedSlider),
            green=self._slider_value(self.GreenSlider),
            blue=self._slider_value(self.BlueSlider),
            boundary_style=boundary_style,
            draw_x=bool(self.DrawXCheckBox.IsChecked),
            x_style=x_style,
            group_results=bool(self.GroupResultsCheckBox.IsChecked))
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_shaft_highlight_options(title, views, active_view, view_name_fn, filled_region_types,
                                 region_type_name_fn, line_styles, line_style_name_fn):
    window = ShaftHighlightOptionsWindow(
        title, views, active_view, view_name_fn, filled_region_types,
        region_type_name_fn, line_styles, line_style_name_fn)
    window.ShowDialog()
    return window.result
