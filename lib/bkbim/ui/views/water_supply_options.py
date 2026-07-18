# -*- coding: utf-8 -*-
"""Run options for the combined Water Supply pushbutton.

This is intentionally just the start panel: choose which systems to run and
which pipe type(s) to use. The actual routing wizard remains in
revit/adapter/mep/water_supply_flow.py so the combined button reuses the same
proven Cold/Hot vertical slices instead of forking routing behavior.
"""

import os

from pyrevit import forms
from System.Windows import Visibility
from System.Windows.Controls import CheckBox

from bkbim.ui.tokens import resolve_tokens_path

try:
    unicode
except NameError:
    unicode = str


class WaterSupplyOptionsResult(object):
    def __init__(self, run_cold, run_hot, cold_pipe_type_name, hot_pipe_type_name):
        self.run_cold = run_cold
        self.run_hot = run_hot
        self.cold_pipe_type_name = cold_pipe_type_name
        self.hot_pipe_type_name = hot_pipe_type_name


class WaterSupplyRoutingOptionsResult(object):
    def __init__(self, source_mode, incoming_height_mm, valve_height_mm,
                 trunk_mode, ceiling_height_mm, ceiling_offset_mm,
                 floor_offset_mm, wall_trunk_height_mm, trunk_diameter_mm,
                 parallel_offset_mm, valve_symbol):
        self.source_mode = source_mode
        self.incoming_height_mm = incoming_height_mm
        self.valve_height_mm = valve_height_mm
        self.trunk_mode = trunk_mode
        self.ceiling_height_mm = ceiling_height_mm
        self.ceiling_offset_mm = ceiling_offset_mm
        self.floor_offset_mm = floor_offset_mm
        self.wall_trunk_height_mm = wall_trunk_height_mm
        self.trunk_diameter_mm = trunk_diameter_mm
        self.parallel_offset_mm = parallel_offset_mm
        self.valve_symbol = valve_symbol


class WaterSupplyFixtureSelectionResult(object):
    def __init__(self, room, fixtures):
        self.room = room
        self.fixtures = fixtures


def _set_combo_to_value(combo, value):
    if not value:
        if combo.Items.Count:
            combo.SelectedIndex = 0
        return
    for i in range(combo.Items.Count):
        if unicode(combo.Items[i]) == unicode(value):
            combo.SelectedIndex = i
            return
    if combo.Items.Count:
        combo.SelectedIndex = 0


def _selected_text(combo):
    item = combo.SelectedItem
    return None if item is None else unicode(item)


def _set_text(textbox, value):
    textbox.Text = u"{0:g}".format(float(value))


def _number_from_text(textbox, label, allow_zero=True, allow_negative=False):
    try:
        value = float(textbox.Text)
    except (TypeError, ValueError):
        raise ValueError(u"{0}: enter a valid number in millimetres.".format(label))
    if allow_negative:
        if not allow_zero and abs(value) < 0.000001:
            raise ValueError(u"{0}: enter a non-zero value.".format(label))
    elif allow_zero:
        if value < 0:
            raise ValueError(u"{0}: enter 0 or a positive value.".format(label))
    elif value <= 0:
        raise ValueError(u"{0}: enter a value greater than 0 mm.".format(label))
    return value


class WaterSupplyOptionsWindow(forms.WPFWindow):
    def __init__(self, pipe_type_names, remembered_cold=None, remembered_hot=None):
        xaml_path = os.path.join(os.path.dirname(__file__), "WaterSupplyOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.result = None
        self._pipe_type_names = list(pipe_type_names)

        for name in self._pipe_type_names:
            self.ColdPipeTypeCombo.Items.Add(name)
            self.HotPipeTypeCombo.Items.Add(name)

        _set_combo_to_value(self.ColdPipeTypeCombo, remembered_cold)
        _set_combo_to_value(self.HotPipeTypeCombo, remembered_hot or remembered_cold)

        self.ColdCheck.IsChecked = True
        self.HotCheck.IsChecked = True
        self.UseSamePipeTypeCheck.IsChecked = (remembered_hot is None or remembered_hot == remembered_cold)

        self.ColdCheck.Checked += self._on_option_changed
        self.ColdCheck.Unchecked += self._on_option_changed
        self.HotCheck.Checked += self._on_option_changed
        self.HotCheck.Unchecked += self._on_option_changed
        self.UseSamePipeTypeCheck.Checked += self._on_option_changed
        self.UseSamePipeTypeCheck.Unchecked += self._on_option_changed
        self.ColdPipeTypeCombo.SelectionChanged += self._on_option_changed

        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

        self._refresh_enabled_state()

    def _on_option_changed(self, sender, args):
        self._refresh_enabled_state()

    def _refresh_enabled_state(self):
        run_cold = self.ColdCheck.IsChecked == True
        run_hot = self.HotCheck.IsChecked == True
        use_same = (self.UseSamePipeTypeCheck.IsChecked == True and
                    run_cold and run_hot)

        self.ColdPipeTypeCombo.IsEnabled = run_cold
        self.HotPipeTypeCombo.IsEnabled = run_hot and not use_same
        self.UseSamePipeTypeCheck.IsEnabled = run_cold and run_hot

        if use_same and self.ColdPipeTypeCombo.SelectedIndex >= 0:
            self.HotPipeTypeCombo.SelectedIndex = self.ColdPipeTypeCombo.SelectedIndex

        if run_cold and run_hot:
            self.StatusText.Text = (
                u"Cold Water will run first, then Hot Water. Hot Water uses "
                u"the configured hot/cold offset so the routes do not overlap.")
        elif run_cold:
            self.StatusText.Text = u"Only Domestic Cold Water will be routed."
        elif run_hot:
            self.StatusText.Text = u"Only Domestic Hot Water will be routed."
        else:
            self.StatusText.Text = u"Select at least one system to route."

    def _on_run(self, sender, args):
        run_cold = self.ColdCheck.IsChecked == True
        run_hot = self.HotCheck.IsChecked == True
        use_same = (self.UseSamePipeTypeCheck.IsChecked == True and
                    run_cold and run_hot)

        if not run_cold and not run_hot:
            self.StatusText.Text = u"Select Cold Water, Hot Water, or both before running."
            return

        cold_pipe_type_name = _selected_text(self.ColdPipeTypeCombo)
        hot_pipe_type_name = cold_pipe_type_name if use_same else _selected_text(self.HotPipeTypeCombo)

        if run_cold and not cold_pipe_type_name:
            self.StatusText.Text = u"Pick a Cold Water pipe type."
            return
        if run_hot and not hot_pipe_type_name:
            self.StatusText.Text = u"Pick a Hot Water pipe type."
            return

        self.result = WaterSupplyOptionsResult(
            run_cold=run_cold,
            run_hot=run_hot,
            cold_pipe_type_name=cold_pipe_type_name,
            hot_pipe_type_name=hot_pipe_type_name)
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


class WaterSupplyRoutingOptionsWindow(forms.WPFWindow):
    def __init__(self, title, system_display_name, source_modes, trunk_modes,
                 valve_options, default_incoming_height_mm,
                 default_valve_height_mm, default_trunk_diameter_mm,
                 minimum_trunk_diameter_mm, default_hot_offset_mm=None):
        xaml_path = os.path.join(os.path.dirname(__file__), "WaterSupplyRoutingOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.Title = u"BK BIM Tools - {0}".format(title)
        self.HeaderText.Text = system_display_name
        self.result = None
        self._source_modes = list(source_modes)
        self._trunk_modes = list(trunk_modes)
        self._valve_by_label = {}
        self._minimum_trunk_diameter_mm = minimum_trunk_diameter_mm
        self._default_hot_offset_mm = default_hot_offset_mm

        for mode in self._source_modes:
            self.SourceModeCombo.Items.Add(mode)
        if self.SourceModeCombo.Items.Count:
            self.SourceModeCombo.SelectedIndex = 0

        for mode in self._trunk_modes:
            self.TrunkModeCombo.Items.Add(mode)
        if self.TrunkModeCombo.Items.Count:
            self.TrunkModeCombo.SelectedIndex = 0

        for label, symbol in valve_options:
            self.ValveFamilyCombo.Items.Add(label)
            self._valve_by_label[label] = symbol
        if self.ValveFamilyCombo.Items.Count:
            self.ValveFamilyCombo.SelectedIndex = 0

        _set_text(self.IncomingHeightText, default_incoming_height_mm)
        _set_text(self.ValveHeightText, default_valve_height_mm)
        _set_text(self.CeilingHeightText, 2700.0)
        _set_text(self.CeilingOffsetText, 150.0)
        _set_text(self.FloorOffsetText, 70.0)
        _set_text(self.WallTrunkHeightText, default_valve_height_mm)
        _set_text(self.TrunkDiameterText, default_trunk_diameter_mm)
        _set_text(self.HotOffsetText, default_hot_offset_mm or 0.0)

        self.HotOffsetPanel.Visibility = (
            Visibility.Visible if default_hot_offset_mm is not None
            else Visibility.Collapsed)

        self.SourceModeCombo.SelectionChanged += self._on_option_changed
        self.TrunkModeCombo.SelectionChanged += self._on_option_changed
        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

        self._refresh_enabled_state()

    def _on_option_changed(self, sender, args):
        self._refresh_enabled_state()

    def _refresh_enabled_state(self):
        source_mode = _selected_text(self.SourceModeCombo) or u""
        trunk_mode = _selected_text(self.TrunkModeCombo) or u""

        self.IncomingHeightText.IsEnabled = u"Click incoming" in source_mode
        self.CeilingPanel.Visibility = (
            Visibility.Visible if u"ceiling" in trunk_mode.lower()
            else Visibility.Collapsed)
        self.FloorPanel.Visibility = (
            Visibility.Visible if u"floor" in trunk_mode.lower()
            else Visibility.Collapsed)
        self.WallPanel.Visibility = (
            Visibility.Visible if u"wall" in trunk_mode.lower()
            else Visibility.Collapsed)

        if u"Select existing" in source_mode:
            self.SourceHintText.Text = (
                u"You will select the existing main pipe and its tie-in point "
                u"after this window closes.")
        else:
            self.SourceHintText.Text = (
                u"You will click the incoming main point after this window closes.")

    def _on_run(self, sender, args):
        self.ErrorText.Text = u""
        try:
            source_mode = _selected_text(self.SourceModeCombo)
            trunk_mode = _selected_text(self.TrunkModeCombo)
            if not source_mode:
                raise ValueError(u"Choose an incoming-main source mode.")
            if not trunk_mode:
                raise ValueError(u"Choose where the trunk should run.")

            incoming_height_mm = _number_from_text(
                self.IncomingHeightText, u"Incoming main height", allow_zero=True)
            valve_height_mm = _number_from_text(
                self.ValveHeightText, u"Valve height", allow_zero=True)
            ceiling_height_mm = _number_from_text(
                self.CeilingHeightText, u"Ceiling height", allow_zero=False)
            ceiling_offset_mm = _number_from_text(
                self.CeilingOffsetText, u"Ceiling offset", allow_zero=True)
            floor_offset_mm = _number_from_text(
                self.FloorOffsetText, u"Floor offset", allow_zero=True)
            wall_trunk_height_mm = _number_from_text(
                self.WallTrunkHeightText, u"In-wall trunk elevation", allow_zero=True)
            trunk_diameter_mm = _number_from_text(
                self.TrunkDiameterText, u"Trunk diameter", allow_zero=False)
            if trunk_diameter_mm < self._minimum_trunk_diameter_mm:
                raise ValueError(
                    u"Trunk diameter must be at least {0:g} mm, the largest "
                    u"selected fixture connector.".format(
                        float(self._minimum_trunk_diameter_mm)))

            parallel_offset_mm = 0.0
            if self._default_hot_offset_mm is not None:
                parallel_offset_mm = _number_from_text(
                    self.HotOffsetText, u"Hot Water offset",
                    allow_zero=True, allow_negative=True)
                if abs(parallel_offset_mm) < 1.0:
                    raise ValueError(
                        u"Hot Water offset must not be 0 mm, otherwise hot "
                        u"and cold pipes can overlap.")

            valve_label = _selected_text(self.ValveFamilyCombo)
            valve_symbol = self._valve_by_label.get(valve_label)
        except ValueError as e:
            self.ErrorText.Text = unicode(e)
            return

        self.result = WaterSupplyRoutingOptionsResult(
            source_mode=source_mode,
            incoming_height_mm=incoming_height_mm,
            valve_height_mm=valve_height_mm,
            trunk_mode=trunk_mode,
            ceiling_height_mm=ceiling_height_mm,
            ceiling_offset_mm=ceiling_offset_mm,
            floor_offset_mm=floor_offset_mm,
            wall_trunk_height_mm=wall_trunk_height_mm,
            trunk_diameter_mm=trunk_diameter_mm,
            parallel_offset_mm=parallel_offset_mm,
            valve_symbol=valve_symbol)
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


class WaterSupplyFixtureSelectionWindow(forms.WPFWindow):
    def __init__(self, title, system_display_name, room_entries):
        xaml_path = os.path.join(os.path.dirname(__file__), "WaterSupplyFixtureSelection.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.Title = u"BK BIM Tools - {0}".format(title)
        self.HeaderText.Text = u"{0} Wizard".format(system_display_name)
        self.SubtitleText.Text = (
            u"Choose one room, then choose the fixtures to route. Skipped "
            u"fixtures are shown here so the workflow stays in one BK window.")
        self.result = None
        self._entries = list(room_entries)
        self._entry_by_label = {}
        self._fixture_by_label = {}
        self._checkboxes = []

        for entry in self._entries:
            self.RoomList.Items.Add(entry["label"])
            self._entry_by_label[entry["label"]] = entry
        if self.RoomList.Items.Count:
            self.RoomList.SelectedIndex = 0

        self.RoomList.SelectionChanged += self._on_room_changed
        self.SelectAllButton.Click += self._on_select_all
        self.ClearButton.Click += self._on_clear
        self.ContinueButton.Click += self._on_continue
        self.CancelButton.Click += self._on_cancel

        self._refresh_room()

    def _current_entry(self):
        label = self.RoomList.SelectedItem
        if label is None:
            return None
        return self._entry_by_label.get(unicode(label))

    def _on_room_changed(self, sender, args):
        self._refresh_room()

    def _refresh_room(self):
        self.FixturePanel.Children.Clear()
        self._fixture_by_label = {}
        self._checkboxes = []
        self.ErrorText.Text = u""

        entry = self._current_entry()
        if entry is None:
            self.RoomSummaryText.Text = u"Choose a room to review fixtures."
            self.SkipSummaryText.Text = u""
            return

        self.RoomSummaryText.Text = (
            u"{0} plumbing fixture(s) found. {1} eligible for {2}.".format(
                entry["total"], len(entry["eligible"]), self.HeaderText.Text.replace(u" Wizard", u"")))

        skipped_parts = []
        if entry["missing"]:
            skipped_parts.append(u"Missing inlet: {0}".format(len(entry["missing"])))
        if entry["ambiguous"]:
            skipped_parts.append(u"Ambiguous inlet: {0}".format(len(entry["ambiguous"])))
        if entry["connected"]:
            skipped_parts.append(u"Already connected: {0}".format(len(entry["connected"])))
        self.SkipSummaryText.Text = (
            u"Skipped - {0}".format(u"; ".join(skipped_parts))
            if skipped_parts else u"No skipped fixtures.")

        for fixture in entry["eligible"]:
            label = entry["fixture_label_fn"](fixture)
            checkbox = CheckBox()
            checkbox.Content = label
            checkbox.IsChecked = True
            checkbox.Margin = self._checkbox_margin()
            self.FixturePanel.Children.Add(checkbox)
            self._fixture_by_label[label] = fixture
            self._checkboxes.append(checkbox)

        self.ContinueButton.IsEnabled = bool(entry["eligible"])

    @staticmethod
    def _checkbox_margin():
        from System.Windows import Thickness
        return Thickness(0, 0, 0, 6)

    def _on_select_all(self, sender, args):
        for checkbox in self._checkboxes:
            checkbox.IsChecked = True

    def _on_clear(self, sender, args):
        for checkbox in self._checkboxes:
            checkbox.IsChecked = False

    def _on_continue(self, sender, args):
        entry = self._current_entry()
        if entry is None:
            self.ErrorText.Text = u"Choose a room first."
            return
        selected = []
        for checkbox in self._checkboxes:
            if checkbox.IsChecked == True:
                selected.append(self._fixture_by_label.get(unicode(checkbox.Content)))
        selected = [fixture for fixture in selected if fixture is not None]
        if not selected:
            self.ErrorText.Text = u"Choose at least one eligible fixture."
            return
        self.result = WaterSupplyFixtureSelectionResult(entry["room"], selected)
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


class WaterSupplyResultWindow(forms.WPFWindow):
    def __init__(self, title, message):
        xaml_path = os.path.join(os.path.dirname(__file__), "WaterSupplyResult.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.Title = u"BK BIM Tools - {0}".format(title)
        self.HeaderText.Text = title
        self.MessageText.Text = message or u"Water Supply command complete."
        self.DoneButton.Click += self._on_done

    def _on_done(self, sender, args):
        self.Close()


def show_water_supply_options(pipe_type_names, remembered_cold=None, remembered_hot=None):
    """Shows the combined Water Supply start window.

    Returns WaterSupplyOptionsResult, or None if the user cancelled.
    """
    window = WaterSupplyOptionsWindow(
        pipe_type_names,
        remembered_cold=remembered_cold,
        remembered_hot=remembered_hot)
    window.ShowDialog()
    return window.result


def show_water_supply_fixture_selection(title, system_display_name, room_entries):
    window = WaterSupplyFixtureSelectionWindow(title, system_display_name, room_entries)
    window.ShowDialog()
    return window.result


def show_water_supply_routing_options(title, system_display_name, source_modes,
                                      trunk_modes, valve_options,
                                      default_incoming_height_mm,
                                      default_valve_height_mm,
                                      default_trunk_diameter_mm,
                                      minimum_trunk_diameter_mm,
                                      default_hot_offset_mm=None):
    """Shows the branded per-system routing settings window.

    This replaces the old chain of CommandSwitchWindow/ask_for_string/
    SelectFromList prompts for source mode, heights, trunk mode, diameter,
    hot offset and valve family.
    """
    window = WaterSupplyRoutingOptionsWindow(
        title, system_display_name, source_modes, trunk_modes, valve_options,
        default_incoming_height_mm=default_incoming_height_mm,
        default_valve_height_mm=default_valve_height_mm,
        default_trunk_diameter_mm=default_trunk_diameter_mm,
        minimum_trunk_diameter_mm=minimum_trunk_diameter_mm,
        default_hot_offset_mm=default_hot_offset_mm)
    window.ShowDialog()
    return window.result


def show_water_supply_result(title, message):
    window = WaterSupplyResultWindow(title, message)
    window.ShowDialog()
