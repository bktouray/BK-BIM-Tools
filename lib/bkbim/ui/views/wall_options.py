# -*- coding: utf-8 -*-
"""Code-behind for WallOptions.xaml - replaces AutoWall's old chain of
level/face-mode/per-thickness-type/material popups with one window. One
XAML file covers BOTH drawing modes (parallel double-line / centreline) -
the chrome is identical, only the middle content's visibility toggles here,
the same technique structural_dimension_options.py uses for per-category
personalization.

Decoupled from the Revit adapter layer the same way structural_dimension_options.py
is: levels/materials/existing wall types are passed in as plain lists with a
type_name_fn callback for display names, and picking a new base wall type is
delegated to an on_pick_base_wall_type() callback.
"""

import os

import clr

clr.AddReference("PresentationFramework")

from System.Windows import Visibility
from pyrevit import forms

from bkbim.ui.tokens import resolve_tokens_path
from bkbim.ui.views.result_dialog import show_result
from bkbim.ui.views.type_mapping_row import build_type_mapping_row

MODE_PARALLEL = u"parallel"
MODE_CENTRELINE = u"centreline"

_LEAVE_DEFAULT = u"<Leave family default>"


class WallOptionsResult(object):
    def __init__(self, mode, base_level, top_level, structural, location_line=None,
                group_selections=None, base_wall_type=None, material_id=None, wall_type=None):
        self.mode = mode
        self.base_level = base_level
        self.top_level = top_level
        self.structural = structural
        self.location_line = location_line  # u"finish" | u"core" - parallel mode only
        self.group_selections = group_selections  # {thickness_mm: (kind, value, extra)} - parallel mode only
        self.base_wall_type = base_wall_type  # shared base WallType - parallel mode only
        self.material_id = material_id  # parallel mode only
        self.wall_type = wall_type  # single WallType - centreline mode only


class WallOptionsWindow(forms.WPFWindow):
    def __init__(self, mode, groups, existing_type_labels, existing_types, levels, materials, type_name_fn,
                on_pick_base_wall_type, default_start_level_name=None, default_stop_level_name=None,
                default_structural=False, default_location_line=u"finish",
                default_material_name=None, default_wall_type_name=None):
        xaml_path = os.path.join(os.path.dirname(__file__), "WallOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.result = None
        self._mode = mode
        self._groups = groups
        self._existing_types = existing_types
        self._levels = levels
        self._materials = materials
        self._on_pick_base_wall_type = on_pick_base_wall_type
        self._base_wall_type = None
        self._rows = []

        if mode == MODE_PARALLEL:
            total_runs = sum(len(runs) for _key, runs in groups)
            self.SubtitleText.Text = (
                u"Detected {0} wall(s) in {1} thickness(es). Confirm the levels "
                u"and map each thickness to a wall type."
            ).format(total_runs, len(groups))
            self.ParallelPanel.Visibility = Visibility.Visible
            self.CentrelinePanel.Visibility = Visibility.Collapsed
        else:
            self.SubtitleText.Text = u"Centreline mode - each CAD line becomes one wall's centreline."
            self.ParallelPanel.Visibility = Visibility.Collapsed
            self.CentrelinePanel.Visibility = Visibility.Visible

        level_names = [type_name_fn(lv) for lv in levels]
        for name in level_names:
            self.StartLevelCombo.Items.Add(name)
            self.StopLevelCombo.Items.Add(name)
        self.StartLevelCombo.SelectedIndex = (
            level_names.index(default_start_level_name) if default_start_level_name in level_names else 0)
        self.StopLevelCombo.SelectedIndex = (
            level_names.index(default_stop_level_name) if default_stop_level_name in level_names
            else max(0, len(level_names) - 1))

        self.StructuralCheckBox.IsChecked = bool(default_structural)

        if mode == MODE_PARALLEL:
            if default_location_line == u"core":
                self.CoreFacesRadio.IsChecked = True
            else:
                self.FinishFacesRadio.IsChecked = True

            self.ChooseBaseWallTypeButton.Click += self._on_choose_base_wall_type

            self.MaterialCombo.Items.Add(_LEAVE_DEFAULT)
            material_names = [type_name_fn(m) for m in materials]
            for name in material_names:
                self.MaterialCombo.Items.Add(name)
            self.MaterialCombo.SelectedIndex = (
                (material_names.index(default_material_name) + 1)
                if default_material_name in material_names else 0)

            surface_brush = self.FindResource(u"Surface.Raised")
            border_brush = self.FindResource(u"Border.Default")
            text_secondary_brush = self.FindResource(u"Text.Secondary")

            for group_key, runs in groups:
                group_label = u"{0} mm".format(group_key)
                count_label = u"{0} wall(s)".format(len(runs))
                border, row = build_type_mapping_row(
                    group_key, group_label, count_label, existing_type_labels, existing_types,
                    per_row_base_family=False, show_height_field=False,
                    surface_brush=surface_brush, border_brush=border_brush,
                    text_secondary_brush=text_secondary_brush)
                self._rows.append(row)
                self.ThicknessGroupsPanel.Children.Add(border)
        else:
            for label in existing_type_labels:
                self.CentrelineWallTypeCombo.Items.Add(label)
            self.CentrelineWallTypeCombo.SelectedIndex = (
                existing_type_labels.index(default_wall_type_name)
                if default_wall_type_name in existing_type_labels else 0)

        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

    def _on_choose_base_wall_type(self, sender, args):
        wall_type, label = self._on_pick_base_wall_type()
        if wall_type is not None:
            self._base_wall_type = wall_type
            self.BaseWallTypeText.Text = label

    def _on_run(self, sender, args):
        start_idx = self.StartLevelCombo.SelectedIndex
        stop_idx = self.StopLevelCombo.SelectedIndex
        base_level = self._levels[start_idx] if 0 <= start_idx < len(self._levels) else None
        top_level = self._levels[stop_idx] if 0 <= stop_idx < len(self._levels) else None
        structural = bool(self.StructuralCheckBox.IsChecked)

        if self._mode == MODE_PARALLEL:
            group_selections = {}
            needs_base_type = False
            for row in self._rows:
                selection = row.get_selection()
                if selection[0] == u"auto":
                    needs_base_type = True
                group_selections[row.group_key] = selection

            if needs_base_type and self._base_wall_type is None:
                show_result(
                    u"Wall Options",
                    u"Choose a base wall type before running - at least "
                    u"one thickness is set to Auto-generate.")
                return

            mat_idx = self.MaterialCombo.SelectedIndex
            material_id = self._materials[mat_idx - 1].Id if mat_idx > 0 else None
            location_line = u"core" if self.CoreFacesRadio.IsChecked else u"finish"

            self.result = WallOptionsResult(
                mode=MODE_PARALLEL, base_level=base_level, top_level=top_level, structural=structural,
                location_line=location_line, group_selections=group_selections,
                base_wall_type=self._base_wall_type, material_id=material_id)
        else:
            idx = self.CentrelineWallTypeCombo.SelectedIndex
            wall_type = self._existing_types[idx] if 0 <= idx < len(self._existing_types) else None
            self.result = WallOptionsResult(
                mode=MODE_CENTRELINE, base_level=base_level, top_level=top_level, structural=structural,
                wall_type=wall_type)

        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_wall_options(mode, groups, existing_type_labels, existing_types, levels, materials, type_name_fn,
                      on_pick_base_wall_type, default_start_level_name=None, default_stop_level_name=None,
                      default_structural=False, default_location_line=u"finish",
                      default_material_name=None, default_wall_type_name=None):
    """Shows the modal Wall Options window (parallel or centreline mode).

    Returns a WallOptionsResult, or None if the user cancelled.
    """
    window = WallOptionsWindow(
        mode, groups, existing_type_labels, existing_types, levels, materials, type_name_fn,
        on_pick_base_wall_type, default_start_level_name=default_start_level_name,
        default_stop_level_name=default_stop_level_name, default_structural=default_structural,
        default_location_line=default_location_line, default_material_name=default_material_name,
        default_wall_type_name=default_wall_type_name)
    window.ShowDialog()
    return window.result
