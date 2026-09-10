# -*- coding: utf-8 -*-
"""Branded options window for the Beam Legend tool."""

import os

from pyrevit import forms
from System.Windows import Visibility

from bkbim.ui.tokens import resolve_tokens_path

try:
    unicode
except NameError:
    unicode = str

SOURCE_PROJECT = u"model"
SOURCE_VIEW = u"view"


class BeamLegendOptionsResult(object):
    def __init__(self, source_scope, source_view, legend_view, title_type, label_type,
                 title_text, row_spacing_mm, mark_to_component_mm,
                 component_to_size_mm):
        self.source_scope = source_scope
        self.source_view = source_view
        self.legend_view = legend_view
        self.title_type = title_type
        self.label_type = label_type
        self.title_text = title_text
        self.row_spacing_mm = row_spacing_mm
        self.mark_to_component_mm = mark_to_component_mm
        self.component_to_size_mm = component_to_size_mm


class BeamLegendOptionsWindow(forms.WPFWindow):
    def __init__(self, source_views, legend_views, text_types, name_fn, id_fn, cfg,
                 default_source_view=None, default_legend_view=None):
        xaml_path = os.path.join(os.path.dirname(__file__), "BeamLegendOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self._source_views = source_views
        self._legend_views = legend_views
        self._text_types = text_types
        self.result = None

        for v in source_views:
            self.SourceViewCombo.Items.Add(u"{0}  [{1}]".format(v.Name, v.ViewType))
        for v in legend_views:
            self.LegendViewCombo.Items.Add(v.Name)
        for t in text_types:
            self.TitleTypeCombo.Items.Add(name_fn(t))
            self.LabelTypeCombo.Items.Add(name_fn(t))

        source_scope = cfg.get("source_scope", SOURCE_PROJECT)
        self.ProjectScopeRadio.IsChecked = source_scope != SOURCE_VIEW
        self.ViewScopeRadio.IsChecked = source_scope == SOURCE_VIEW

        self.SourceViewCombo.SelectedIndex = self._match_view_or_first(
            source_views, id_fn, cfg.get("source_view_id"), default_source_view)
        self.LegendViewCombo.SelectedIndex = self._match_view_or_first(
            legend_views, id_fn, cfg.get("legend_view_id"), default_legend_view)
        self.TitleTypeCombo.SelectedIndex = self._match_or_first(text_types, id_fn, cfg.get("title_type_id"))
        self.LabelTypeCombo.SelectedIndex = self._match_or_first(text_types, id_fn, cfg.get("label_type_id"))

        self.TitleTextBox.Text = cfg.get("title_text", u"BEAM TYPE LEGEND")
        self.RowSpacingTextBox.Text = unicode(cfg.get("row_spacing_mm", 650.0))
        self.MarkComponentTextBox.Text = unicode(cfg.get("mark_to_component_mm", 1800.0))
        self.ComponentSizeTextBox.Text = unicode(cfg.get("component_to_size_mm", 3400.0))

        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

    @staticmethod
    def _match_or_first(items, id_fn, target_id):
        if target_id is not None:
            for i, item in enumerate(items):
                if id_fn(item.Id) == target_id:
                    return i
        return 0 if items else -1

    @staticmethod
    def _match_view_or_first(items, id_fn, target_id, default_view):
        if default_view is not None:
            for i, item in enumerate(items):
                if id_fn(item.Id) == id_fn(default_view.Id):
                    return i
        if target_id is not None:
            for i, item in enumerate(items):
                if id_fn(item.Id) == target_id:
                    return i
        return 0 if items else -1

    def _show_validation(self, message):
        self.ValidationText.Text = message
        self.ValidationText.Visibility = Visibility.Visible

    def _parse_mm(self, textbox, label):
        try:
            value = float(textbox.Text)
        except Exception:
            self._show_validation(u"{0} must be a number in millimetres.".format(label))
            return None
        if value <= 0:
            self._show_validation(u"{0} must be greater than zero.".format(label))
            return None
        return value

    def _on_run(self, sender, args):
        source_index = self.SourceViewCombo.SelectedIndex
        legend_index = self.LegendViewCombo.SelectedIndex
        title_index = self.TitleTypeCombo.SelectedIndex
        label_index = self.LabelTypeCombo.SelectedIndex

        if source_index < 0:
            self._show_validation(u"Pick a source view.")
            return
        if legend_index < 0:
            self._show_validation(u"Pick a legend view.")
            return
        if title_index < 0 or label_index < 0:
            self._show_validation(u"No text types available in this model.")
            return

        row_spacing = self._parse_mm(self.RowSpacingTextBox, u"Row spacing")
        if row_spacing is None:
            return
        mark_to_component = self._parse_mm(self.MarkComponentTextBox, u"Mark to component spacing")
        if mark_to_component is None:
            return
        component_to_size = self._parse_mm(self.ComponentSizeTextBox, u"Component to size spacing")
        if component_to_size is None:
            return

        source_scope = SOURCE_VIEW if self.ViewScopeRadio.IsChecked else SOURCE_PROJECT
        self.result = BeamLegendOptionsResult(
            source_scope=source_scope,
            source_view=self._source_views[source_index],
            legend_view=self._legend_views[legend_index],
            title_type=self._text_types[title_index],
            label_type=self._text_types[label_index],
            title_text=self.TitleTextBox.Text,
            row_spacing_mm=row_spacing,
            mark_to_component_mm=mark_to_component,
            component_to_size_mm=component_to_size)
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_beam_legend_options(source_views, legend_views, text_types, name_fn, id_fn, cfg,
                             default_source_view=None, default_legend_view=None):
    window = BeamLegendOptionsWindow(
        source_views, legend_views, text_types, name_fn, id_fn, cfg,
        default_source_view=default_source_view,
        default_legend_view=default_legend_view)
    window.ShowDialog()
    return window.result

