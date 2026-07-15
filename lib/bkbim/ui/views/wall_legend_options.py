# -*- coding: utf-8 -*-
"""Branded replacement for Wall Legend's default-pyRevit wizard (a chain of
`forms.alert` choice screens, `forms.SelectFromList` single/multi pickers, and
`forms.ask_for_string`). One window covers: wall-type source (view / whole
model / pick-from-list / all), title + label text types, legend title text,
and the auto-refresh toggle. Business logic (bkd_walllegend.py) is untouched -
this only replaces how the choices get made.
"""

import os

from pyrevit import forms

from System.Windows import Visibility

from bkbim.ui.tokens import resolve_tokens_path
from bkbim.ui.views.listbox_drag_select import enable_drag_multiselect

SOURCE_VIEW = u"view"
SOURCE_MODEL = u"model"
SOURCE_LIST = u"list"
SOURCE_ALL = u"all"


class WallLegendOptionsResult(object):
    def __init__(self, source, source_view, wall_types, title_type, label_type, title_text, auto):
        self.source = source
        self.source_view = source_view  # View, only set when source == SOURCE_VIEW
        self.wall_types = wall_types  # list of WallType, only set when source == SOURCE_LIST
        self.title_type = title_type
        self.label_type = label_type
        self.title_text = title_text
        self.auto = auto


class WallLegendOptionsWindow(forms.WPFWindow):
    def __init__(self, views, wall_types, text_types, name_fn, id_fn, cfg):
        xaml_path = os.path.join(os.path.dirname(__file__), "WallLegendOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self._views = views
        self._wall_types = wall_types
        self._text_types = text_types
        self._id_fn = id_fn
        self.result = None

        for v in views:
            self.ViewsList.Items.Add(u"{0}  [{1}]".format(v.Name, v.ViewType))
        for wt in wall_types:
            self.WallTypesList.Items.Add(name_fn(wt))
        for t in text_types:
            self.TitleTypeCombo.Items.Add(name_fn(t))
            self.LabelTypeCombo.Items.Add(name_fn(t))
        enable_drag_multiselect(self.WallTypesList)

        source = cfg.get("source", SOURCE_MODEL)
        self.ViewSourceRadio.IsChecked = (source == SOURCE_VIEW)
        self.ModelSourceRadio.IsChecked = (source == SOURCE_MODEL)
        self.ListSourceRadio.IsChecked = (source == SOURCE_LIST)
        self.AllSourceRadio.IsChecked = (source == SOURCE_ALL)
        self._update_source_panels()

        source_view_id = cfg.get("source_view_id")
        if source_view_id is not None:
            for i, v in enumerate(views):
                if id_fn(v.Id) == source_view_id:
                    self.ViewsList.SelectedIndex = i
                    break

        type_ids = set(cfg.get("type_ids", []))
        if type_ids:
            for i, wt in enumerate(wall_types):
                if id_fn(wt.Id) in type_ids:
                    self.WallTypesList.SelectedItems.Add(self.WallTypesList.Items[i])

        self.TitleTypeCombo.SelectedIndex = self._match_or_first(text_types, id_fn, cfg.get("title_type_id"))
        self.LabelTypeCombo.SelectedIndex = self._match_or_first(text_types, id_fn, cfg.get("label_type_id"))

        self.TitleTextBox.Text = cfg.get("title_text", u"WALL TYPE LEGEND")
        self.AutoCheckBox.IsChecked = bool(cfg.get("auto", False))

        self.ViewSourceRadio.Checked += self._on_source_changed
        self.ModelSourceRadio.Checked += self._on_source_changed
        self.ListSourceRadio.Checked += self._on_source_changed
        self.AllSourceRadio.Checked += self._on_source_changed

        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

    @staticmethod
    def _match_or_first(items, id_fn, target_id):
        if target_id is not None:
            for i, item in enumerate(items):
                if id_fn(item.Id) == target_id:
                    return i
        return 0 if items else -1

    def _update_source_panels(self):
        self.ViewPickerPanel.Visibility = (
            Visibility.Visible if self.ViewSourceRadio.IsChecked else Visibility.Collapsed)
        self.WallTypePickerPanel.Visibility = (
            Visibility.Visible if self.ListSourceRadio.IsChecked else Visibility.Collapsed)

    def _on_source_changed(self, sender, args):
        self._update_source_panels()

    def _show_validation(self, message):
        self.ValidationText.Text = message
        self.ValidationText.Visibility = Visibility.Visible

    def _on_run(self, sender, args):
        if self.ViewSourceRadio.IsChecked:
            source = SOURCE_VIEW
        elif self.ListSourceRadio.IsChecked:
            source = SOURCE_LIST
        elif self.AllSourceRadio.IsChecked:
            source = SOURCE_ALL
        else:
            source = SOURCE_MODEL

        source_view = None
        wall_types = None

        if source == SOURCE_VIEW:
            index = self.ViewsList.SelectedIndex
            if index < 0:
                self._show_validation(u"Pick a view first.")
                return
            source_view = self._views[index]

        if source == SOURCE_LIST:
            indices = [self.WallTypesList.Items.IndexOf(item) for item in self.WallTypesList.SelectedItems]
            wall_types = [self._wall_types[i] for i in indices if 0 <= i < len(self._wall_types)]
            if not wall_types:
                self._show_validation(u"Pick at least one wall type.")
                return

        title_index = self.TitleTypeCombo.SelectedIndex
        label_index = self.LabelTypeCombo.SelectedIndex
        if title_index < 0 or label_index < 0:
            self._show_validation(u"No text types available in this model.")
            return

        self.result = WallLegendOptionsResult(
            source=source,
            source_view=source_view,
            wall_types=wall_types,
            title_type=self._text_types[title_index],
            label_type=self._text_types[label_index],
            title_text=self.TitleTextBox.Text,
            auto=bool(self.AutoCheckBox.IsChecked),
        )
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_wall_legend_options(views, wall_types, text_types, name_fn, id_fn, cfg):
    """Shows the branded Wall Legend options window.

    Returns a WallLegendOptionsResult, or None if the user cancelled.
    """
    window = WallLegendOptionsWindow(views, wall_types, text_types, name_fn, id_fn, cfg)
    window.ShowDialog()
    return window.result
