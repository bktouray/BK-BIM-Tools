# -*- coding: utf-8 -*-
"""Code-behind for OpeningOptions.xaml - shared by AutoDoor and AutoWindow
(both tools are identical apart from category/labels, same as the old
automation/opening_tool.py already assumed). Replaces the old chain of
level/lintel/per-width-family/per-width-height popups with one window.

Personalizes title/subtitle per kind ("Door"/"Window") via a _CATEGORY_TEXT
dict, the same technique structural_dimension_options.py uses. Each width
group gets its OWN base family (today's opening_tool.py already supports
this - different widths often mean different families, e.g. sliding vs
single) via type_mapping_row's per_row_base_family mode.
"""

import os

from pyrevit import forms

from bkbim.ui.tokens import resolve_tokens_path
from bkbim.ui.views.type_mapping_row import build_type_mapping_row

_CATEGORY_TEXT = {
    u"Door": {
        u"window_title": u"Door Options",
        u"subtitle_fmt": u"Detected {0} door(s) in {1} width(s). Confirm the "
                        u"host level and map each width to a family type.",
    },
    u"Window": {
        u"window_title": u"Window Options",
        u"subtitle_fmt": u"Detected {0} window(s) in {1} width(s). Confirm the "
                        u"host level and map each width to a family type.",
    },
}


class OpeningOptionsResult(object):
    def __init__(self, level, lintel_mm, group_selections):
        self.level = level
        self.lintel_mm = lintel_mm
        self.group_selections = group_selections  # {width_mm: (kind, value, extra)}


def _make_row_picker(width_mm, on_pick_base_family_for_group):
    def _pick():
        return on_pick_base_family_for_group(width_mm)
    return _pick


class OpeningOptionsWindow(forms.WPFWindow):
    def __init__(self, kind, groups, levels, existing_type_labels, existing_types, type_name_fn,
                on_pick_base_family_for_group, default_level_name=None, default_lintel_mm=2100.0,
                default_height_mm=2100.0):
        xaml_path = os.path.join(os.path.dirname(__file__), "OpeningOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.result = None
        self._levels = levels
        self._rows = []

        text = _CATEGORY_TEXT.get(kind, _CATEGORY_TEXT[u"Door"])
        total_ops = sum(len(ops) for _w, ops in groups)
        self.Title = u"BK BIM Tools - {0}".format(text[u"window_title"])
        self.TitleText.Text = text[u"window_title"]
        self.SubtitleText.Text = text[u"subtitle_fmt"].format(total_ops, len(groups))

        level_names = [type_name_fn(lv) for lv in levels]
        for name in level_names:
            self.HostLevelCombo.Items.Add(name)
        self.HostLevelCombo.SelectedIndex = (
            level_names.index(default_level_name) if default_level_name in level_names else 0)

        self.LintelSlider.Value = default_lintel_mm
        self.LintelTextBox.Text = str(int(default_lintel_mm))
        self.LintelSlider.ValueChanged += self._on_lintel_slider_changed
        self.LintelTextBox.LostFocus += self._on_lintel_text_committed

        surface_brush = self.FindResource(u"Surface.Raised")
        border_brush = self.FindResource(u"Border.Default")
        text_secondary_brush = self.FindResource(u"Text.Secondary")

        for width_mm, ops in groups:
            group_label = u"{0} mm".format(width_mm)
            count_label = u"{0} {1}(s)".format(len(ops), kind.lower())
            border, row = build_type_mapping_row(
                width_mm, group_label, count_label, existing_type_labels, existing_types,
                per_row_base_family=True, on_pick_base_family=_make_row_picker(width_mm, on_pick_base_family_for_group),
                show_height_field=True, default_height_mm=default_height_mm,
                surface_brush=surface_brush, border_brush=border_brush,
                text_secondary_brush=text_secondary_brush)
            self._rows.append(row)
            self.WidthGroupsPanel.Children.Add(border)

        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

    def _on_lintel_slider_changed(self, sender, args):
        self.LintelTextBox.Text = str(int(self.LintelSlider.Value))

    def _on_lintel_text_committed(self, sender, args):
        try:
            value = float(self.LintelTextBox.Text)
        except ValueError:
            value = self.LintelSlider.Value
        value = max(self.LintelSlider.Minimum, min(self.LintelSlider.Maximum, value))
        self.LintelSlider.Value = value
        self.LintelTextBox.Text = str(int(value))

    def _on_run(self, sender, args):
        group_selections = {}
        for row in self._rows:
            kind, value, extra = row.get_selection()
            if kind == u"auto" and value is None:
                forms.alert(u"Choose a base family for the {0}mm group before "
                           u"running.".format(row.group_key), title=self.Title)
                return
            group_selections[row.group_key] = (kind, value, extra)

        idx = self.HostLevelCombo.SelectedIndex
        level = self._levels[idx] if 0 <= idx < len(self._levels) else None

        self.result = OpeningOptionsResult(
            level=level, lintel_mm=self.LintelSlider.Value, group_selections=group_selections)
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_opening_options(kind, groups, levels, existing_type_labels, existing_types, type_name_fn,
                         on_pick_base_family_for_group, default_level_name=None,
                         default_lintel_mm=2100.0, default_height_mm=2100.0):
    """Shows the modal Door/Window Options window.

    Returns an OpeningOptionsResult, or None if the user cancelled.
    """
    window = OpeningOptionsWindow(
        kind, groups, levels, existing_type_labels, existing_types, type_name_fn,
        on_pick_base_family_for_group, default_level_name=default_level_name,
        default_lintel_mm=default_lintel_mm, default_height_mm=default_height_mm)
    window.ShowDialog()
    return window.result
