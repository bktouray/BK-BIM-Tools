# -*- coding: utf-8 -*-
"""Code-behind for ColumnOptions.xaml - replaces AutoColumn's old chain of
confirm-alert / level-picker / material-picker popups with one window:
Start/Stop Level, a shared base family for auto-generated sizes (one base
family only, matching what get_or_create_sized_type has always supported -
see automation/columns.py), Material, and one type_mapping_row per detected
column section size.

Decoupled from the Revit adapter layer the same way structural_dimension_options.py
is: levels/materials/existing types are passed in as plain lists with a
type_name_fn callback for display names, and picking a new base family is
delegated to an on_pick_base_family() callback (the caller's
familyutils.pick_family_symbol flow) rather than importing familyutils here.
"""

import os

from pyrevit import forms

from bkbim.ui.tokens import resolve_tokens_path
from bkbim.ui.views.result_dialog import show_result
from bkbim.ui.views.type_mapping_row import build_type_mapping_row

_LEAVE_DEFAULT = u"<Leave family default>"


class ColumnOptionsResult(object):
    def __init__(self, base_level, top_level, material_id, base_symbol, group_selections):
        self.base_level = base_level
        self.top_level = top_level
        self.material_id = material_id
        self.base_symbol = base_symbol  # shared base FamilySymbol for any "auto" group
        self.group_selections = group_selections  # {group_key: (kind, value, extra)}


class ColumnOptionsWindow(forms.WPFWindow):
    def __init__(self, groups, levels, materials, existing_types_by_label, type_name_fn,
                 on_pick_base_family, default_start_level_name=None, default_stop_level_name=None,
                 default_material_name=None):
        xaml_path = os.path.join(os.path.dirname(__file__), "ColumnOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.result = None
        self._groups = groups  # [(group_key=(short_mm,long_mm), rects), ...]
        self._levels = levels
        self._materials = materials
        self._on_pick_base_family = on_pick_base_family
        self._base_symbol = None
        self._rows = []

        total_rects = sum(len(rects) for _key, rects in groups)
        self.SubtitleText.Text = (
            u"Detected {0} column location(s) in {1} size(s). Confirm the "
            u"levels and map each size to a family type."
        ).format(total_rects, len(groups))

        level_names = [type_name_fn(lv) for lv in levels]
        for name in level_names:
            self.StartLevelCombo.Items.Add(name)
            self.StopLevelCombo.Items.Add(name)
        self.StartLevelCombo.SelectedIndex = (
            level_names.index(default_start_level_name) if default_start_level_name in level_names else 0)
        self.StopLevelCombo.SelectedIndex = (
            level_names.index(default_stop_level_name) if default_stop_level_name in level_names
            else max(0, len(level_names) - 1))

        self.MaterialCombo.Items.Add(_LEAVE_DEFAULT)
        material_names = [type_name_fn(m) for m in materials]
        for name in material_names:
            self.MaterialCombo.Items.Add(name)
        self.MaterialCombo.SelectedIndex = (
            (material_names.index(default_material_name) + 1)
            if default_material_name in material_names else 0)

        self.ChooseBaseFamilyButton.Click += self._on_choose_base_family

        surface_brush = self.FindResource(u"Surface.Raised")
        border_brush = self.FindResource(u"Border.Default")
        text_secondary_brush = self.FindResource(u"Text.Secondary")

        existing_labels = sorted(existing_types_by_label.keys())
        existing_types = [existing_types_by_label[lbl] for lbl in existing_labels]
        for group_key, rects in groups:
            short_mm, long_mm = group_key
            group_label = u"{0} x {1} mm".format(short_mm, long_mm)
            count_label = u"{0} column(s)".format(len(rects))
            border, row = build_type_mapping_row(
                group_key, group_label, count_label, existing_labels, existing_types,
                per_row_base_family=False, show_height_field=False,
                surface_brush=surface_brush, border_brush=border_brush,
                text_secondary_brush=text_secondary_brush)
            self._rows.append(row)
            self.SizeGroupsPanel.Children.Add(border)

        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

    def _on_choose_base_family(self, sender, args):
        symbol, label = self._on_pick_base_family()
        if symbol is not None:
            self._base_symbol = symbol
            self.BaseFamilyText.Text = label

    def _on_run(self, sender, args):
        group_selections = {}
        needs_base_family = False
        for row in self._rows:
            selection = row.get_selection()
            if selection[0] == u"auto":
                needs_base_family = True
            group_selections[row.group_key] = selection

        if needs_base_family and self._base_symbol is None:
            show_result(
                u"Column Options",
                u"Choose a base family before running - at least one "
                u"size is set to Auto-generate.")
            return

        start_idx = self.StartLevelCombo.SelectedIndex
        stop_idx = self.StopLevelCombo.SelectedIndex
        base_level = self._levels[start_idx] if 0 <= start_idx < len(self._levels) else None
        top_level = self._levels[stop_idx] if 0 <= stop_idx < len(self._levels) else None

        mat_idx = self.MaterialCombo.SelectedIndex
        material_id = self._materials[mat_idx - 1].Id if mat_idx > 0 else None

        self.result = ColumnOptionsResult(
            base_level=base_level, top_level=top_level, material_id=material_id,
            base_symbol=self._base_symbol, group_selections=group_selections)
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_column_options(groups, levels, materials, existing_types_by_label, type_name_fn,
                        on_pick_base_family, default_start_level_name=None,
                        default_stop_level_name=None, default_material_name=None):
    """Shows the modal Column Options window.

    Returns a ColumnOptionsResult, or None if the user cancelled.
    """
    window = ColumnOptionsWindow(
        groups, levels, materials, existing_types_by_label, type_name_fn, on_pick_base_family,
        default_start_level_name=default_start_level_name,
        default_stop_level_name=default_stop_level_name,
        default_material_name=default_material_name)
    window.ShowDialog()
    return window.result
