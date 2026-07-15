# -*- coding: utf-8 -*-
"""Code-behind for MarkColorOptions.xaml - the Mark Colors tool's review
window: a color-swatch preview per Mark (so the product owner sees the
actual pastel colors before committing, not just numbers), a view(s)-vs-
template target picker (mirrors ElementScopeOptions' toggle-panel idiom),
and the override controls (transparency, projection/cut line weight,
projection/cut line type - product owner, 2026-07-15: "give me the option
to set line weight and cut/projection line type and weight").
"""

import os

from pyrevit import forms

from System.Windows import Thickness, Visibility
from System.Windows.Controls import Orientation, StackPanel, TextBlock
from System.Windows.Media import Color as WpfColor, SolidColorBrush
from System.Windows.Shapes import Rectangle

from bkbim.ui.tokens import resolve_tokens_path
from bkbim.ui.views.listbox_drag_select import enable_drag_multiselect

TARGET_VIEWS = u"views"
TARGET_TEMPLATE = u"template"


class MarkColorOptionsResult(object):
    def __init__(self, target_mode, selected_views, selected_template, transparency,
                 projection_weight, cut_weight, projection_pattern_id, cut_pattern_id):
        self.target_mode = target_mode  # TARGET_VIEWS | TARGET_TEMPLATE
        self.selected_views = selected_views  # list[View], only for TARGET_VIEWS
        self.selected_template = selected_template  # View, only for TARGET_TEMPLATE
        self.transparency = transparency
        self.projection_weight = projection_weight
        self.cut_weight = cut_weight
        self.projection_pattern_id = projection_pattern_id
        self.cut_pattern_id = cut_pattern_id


def _swatch_row(window, mark, count, db_color):
    row = StackPanel()
    row.Orientation = Orientation.Horizontal
    row.Margin = Thickness(0, 0, 0, 4)

    swatch = Rectangle()
    swatch.Width = 16
    swatch.Height = 16
    swatch.Margin = Thickness(0, 0, 8, 0)
    swatch.Fill = SolidColorBrush(WpfColor.FromRgb(db_color.Red, db_color.Green, db_color.Blue))
    swatch.Stroke = window.FindResource(u"Border.Default")
    swatch.StrokeThickness = 1
    row.Children.Add(swatch)

    label = TextBlock()
    label.Text = u"{0}    {1} pcs".format(mark, count)
    label.Style = window.FindResource(u"SummaryRow")
    row.Children.Add(label)
    return row


class MarkColorOptionsWindow(forms.WPFWindow):
    def __init__(self, title, subtitle, mark_counts, colors, views, view_name_fn,
                 templates, template_name_fn, line_pattern_choices,
                 default_transparency=40, default_projection_weight=4, default_cut_weight=4):
        xaml_path = os.path.join(os.path.dirname(__file__), "MarkColorOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.result = None
        self._views = views
        self._templates = templates
        self._line_pattern_choices = line_pattern_choices

        self.Title = u"BK BIM Tools - {0}".format(title)
        self.TitleText.Text = title
        self.SubtitleText.Text = subtitle

        for mark, count in mark_counts:
            self.PreviewPanel.Children.Add(_swatch_row(self, mark, count, colors[mark]))

        for v in views:
            self.ViewsList.Items.Add(view_name_fn(v))
        enable_drag_multiselect(self.ViewsList)

        for t in templates:
            self.TemplateCombo.Items.Add(template_name_fn(t))
        if templates:
            self.TemplateCombo.SelectedIndex = 0

        for label, _pattern_id in line_pattern_choices:
            self.ProjectionPatternCombo.Items.Add(label)
            self.CutPatternCombo.Items.Add(label)
        self.ProjectionPatternCombo.SelectedIndex = 0
        self.CutPatternCombo.SelectedIndex = 0

        self.ViewsRadio.IsChecked = True
        self._update_target_panels()

        self.TransparencySlider.Value = default_transparency
        self.TransparencyTextBox.Text = str(int(default_transparency))
        self.ProjectionWeightSlider.Value = default_projection_weight
        self.ProjectionWeightTextBox.Text = str(int(default_projection_weight))
        self.CutWeightSlider.Value = default_cut_weight
        self.CutWeightTextBox.Text = str(int(default_cut_weight))

        self.ViewsRadio.Checked += self._on_target_changed
        self.TemplateRadio.Checked += self._on_target_changed
        self.TransparencySlider.ValueChanged += self._make_slider_handler(
            self.TransparencySlider, self.TransparencyTextBox)
        self.TransparencyTextBox.LostFocus += self._make_text_handler(
            self.TransparencySlider, self.TransparencyTextBox)
        self.ProjectionWeightSlider.ValueChanged += self._make_slider_handler(
            self.ProjectionWeightSlider, self.ProjectionWeightTextBox)
        self.ProjectionWeightTextBox.LostFocus += self._make_text_handler(
            self.ProjectionWeightSlider, self.ProjectionWeightTextBox)
        self.CutWeightSlider.ValueChanged += self._make_slider_handler(
            self.CutWeightSlider, self.CutWeightTextBox)
        self.CutWeightTextBox.LostFocus += self._make_text_handler(
            self.CutWeightSlider, self.CutWeightTextBox)

        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

    def _update_target_panels(self):
        is_views = bool(self.ViewsRadio.IsChecked)
        self.ViewsList.Visibility = Visibility.Visible if is_views else Visibility.Collapsed
        self.TemplateCombo.Visibility = Visibility.Collapsed if is_views else Visibility.Visible

    def _on_target_changed(self, sender, args):
        self._update_target_panels()

    def _make_slider_handler(self, slider, textbox):
        def handler(sender, args):
            textbox.Text = str(int(slider.Value))
        return handler

    def _make_text_handler(self, slider, textbox):
        def handler(sender, args):
            try:
                value = float(textbox.Text)
            except ValueError:
                value = slider.Value
            value = max(slider.Minimum, min(slider.Maximum, value))
            slider.Value = value
            textbox.Text = str(int(value))
        return handler

    def _on_run(self, sender, args):
        if self.ViewsRadio.IsChecked:
            target_mode = TARGET_VIEWS
            selected_indices = [self.ViewsList.Items.IndexOf(item) for item in self.ViewsList.SelectedItems]
            selected_views = [self._views[i] for i in selected_indices if 0 <= i < len(self._views)]
            selected_template = None
        else:
            target_mode = TARGET_TEMPLATE
            selected_views = []
            index = self.TemplateCombo.SelectedIndex
            selected_template = self._templates[index] if 0 <= index < len(self._templates) else None

        proj_index = self.ProjectionPatternCombo.SelectedIndex
        cut_index = self.CutPatternCombo.SelectedIndex
        projection_pattern_id = (self._line_pattern_choices[proj_index][1]
                                  if 0 <= proj_index < len(self._line_pattern_choices) else None)
        cut_pattern_id = (self._line_pattern_choices[cut_index][1]
                           if 0 <= cut_index < len(self._line_pattern_choices) else None)

        self.result = MarkColorOptionsResult(
            target_mode=target_mode, selected_views=selected_views, selected_template=selected_template,
            transparency=self.TransparencySlider.Value, projection_weight=self.ProjectionWeightSlider.Value,
            cut_weight=self.CutWeightSlider.Value, projection_pattern_id=projection_pattern_id,
            cut_pattern_id=cut_pattern_id)
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_mark_color_options(title, subtitle, mark_counts, colors, views, view_name_fn,
                             templates, template_name_fn, line_pattern_choices,
                             default_transparency=40, default_projection_weight=4, default_cut_weight=4):
    """Shows the modal Mark Colors review window.

    Returns a MarkColorOptionsResult, or None if the user cancelled.
    """
    window = MarkColorOptionsWindow(
        title, subtitle, mark_counts, colors, views, view_name_fn, templates, template_name_fn,
        line_pattern_choices, default_transparency, default_projection_weight, default_cut_weight)
    window.ShowDialog()
    return window.result
