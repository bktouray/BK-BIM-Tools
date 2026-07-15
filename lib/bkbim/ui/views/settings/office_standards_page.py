# -*- coding: utf-8 -*-
"""Settings page controller for 'Office Standards' - the suite's first real
settings page (Settings platform design Sec 2.9). Edits the dimensioning
offset/gap fields and MEP tables already defined on
domain/standards/standard.Standard, persisted at the OFFICE SettingsStore
layer (core/settings_paths.office_standards_path()).

Deferred, not built (per the approved answer to the "no-consumer fields"
question): Naming Conventions, Dimension Precision, Annotation Defaults - no
code consumer exists for any of them today; adding UI for them would be
speculative business logic (ADR-0002).

Controls are built programmatically (StackPanel/Grid.Children.Add), the same
idiom every other options window in this suite uses (see
auto_mark_options.py's per-family rows) - no XAML data-template precedent
exists here. Values only round-trip to disk when apply() runs (called by the
shell's Apply/OK); build() never touches the saved copy, so Cancel naturally
discards in-progress edits.

Duck-typed page-controller contract the shell (ui/shell/settings_window.py)
expects: build() -> WPF UIElement, validate() -> list[str], apply(),
reset_to_defaults(), export_to_file(path), import_from_file(path). No base
class - this codebase doesn't use ABCs anywhere else (see domain ports.py
files for the same plain-class convention).
"""

import json

import clr

clr.AddReference("PresentationFramework")

from System.Windows import (
    FontWeights, GridLength, GridUnitType, TextAlignment, TextWrapping, Thickness, VerticalAlignment,
)
from System.Windows.Controls import ColumnDefinition, Expander, Grid, StackPanel, TextBlock, TextBox

from bkbim.core.manifest import ModuleManifest
from bkbim.core.settings import LAYER_OFFICE, get_settings
from bkbim.core.settings_paths import office_standards_path
from bkbim.core.settings_registry import SettingsPageDescriptor
from bkbim.domain.standards.standard import Standard, default_standard, load_office_standard

_SETTINGS_KEY = u"office_standards.standard"

# The 6 fields named in the approved plan (Sec 2.9): offset_first/grid_chain/
# structural_chain + their gaps.
_OFFSET_FIELDS = [
    (u"offset_first_mm", u"Wall & opening dimension offset (mm)"),
    (u"wall_perimeter_gap_mm", u"Gap between exterior perimeter strings (mm)"),
    (u"grid_chain_offset_mm", u"Grid-to-grid dimension offset (mm)"),
    (u"grid_chain_gap_mm", u"Gap to grid overall string (mm)"),
    (u"structural_chain_offset_mm", u"Structural element dimension offset (mm)"),
    (u"structural_chain_gap_mm", u"Gap to structural overall string (mm)"),
]


def _format_number(value):
    # Explicit float() cast - IronPython 2.7 raises ValueError on a ".Nf"
    # format spec against a plain int operand (documented engine quirk);
    # casting first keeps this safe regardless of how the value is stored.
    return u"{0:g}".format(float(value))


def _parse_float(text):
    text = (text or u"").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


class _Row(object):
    def __init__(self, container, control):
        self.container = container
        self.control = control


class OfficeStandardsPage(object):
    def __init__(self):
        self._standard = load_office_standard()
        self._scalar_controls = {}     # field_name -> TextBox (offsets/gaps + valve height)
        self._material_control = None
        self._pipe_type_control = None
        self._frequency_controls = {}  # usage -> TextBox
        self._discharge_controls = {}  # fixture -> TextBox
        self._min_slope_controls = []  # list of (dn_mm, TextBox)
        self._max_slope_control = None
        self._capacity_controls = []   # list of (dn_mm, TextBox)

    # -- building ------------------------------------------------------

    def build(self):
        root = StackPanel()
        root.Children.Add(self._build_expander(
            u"Dimension Offsets & Spacing", self._build_offsets_section()))
        root.Children.Add(self._build_expander(
            u"MEP - Sanitary Drainage  (WARNING: un-validated placeholder values - "
            u"verify against BS EN 12056-2 or your office's own reference before "
            u"trusting a real sizing run)",
            self._build_sanitary_section()))
        root.Children.Add(self._build_expander(
            u"MEP - Water Supply", self._build_water_supply_section()))
        return root

    def _build_expander(self, header, content):
        expander = Expander()
        expander.Header = header
        expander.IsExpanded = True
        expander.Margin = Thickness(0, 0, 0, 12)
        expander.Content = content
        return expander

    def _section_label(self, text):
        block = TextBlock()
        block.Text = text
        block.FontWeight = FontWeights.SemiBold
        block.Margin = Thickness(0, 10, 0, 4)
        return block

    def _build_number_row(self, label, value):
        grid = Grid()
        grid.Margin = Thickness(0, 0, 0, 8)
        grid.ColumnDefinitions.Add(ColumnDefinition(Width=GridLength(1, GridUnitType.Star)))
        grid.ColumnDefinitions.Add(ColumnDefinition(Width=GridLength(100)))

        label_block = TextBlock()
        label_block.Text = label
        label_block.VerticalAlignment = VerticalAlignment.Center
        label_block.TextWrapping = TextWrapping.Wrap
        Grid.SetColumn(label_block, 0)
        grid.Children.Add(label_block)

        text_box = TextBox()
        text_box.Height = 26
        text_box.VerticalContentAlignment = VerticalAlignment.Center
        text_box.TextAlignment = TextAlignment.Right
        text_box.Text = u"" if value is None else _format_number(value)
        Grid.SetColumn(text_box, 1)
        grid.Children.Add(text_box)

        return _Row(grid, text_box)

    def _build_text_row(self, label, value):
        grid = Grid()
        grid.Margin = Thickness(0, 0, 0, 8)
        grid.ColumnDefinitions.Add(ColumnDefinition(Width=GridLength(1, GridUnitType.Star)))
        grid.ColumnDefinitions.Add(ColumnDefinition(Width=GridLength(160)))

        label_block = TextBlock()
        label_block.Text = label
        label_block.VerticalAlignment = VerticalAlignment.Center
        Grid.SetColumn(label_block, 0)
        grid.Children.Add(label_block)

        text_box = TextBox()
        text_box.Height = 26
        text_box.VerticalContentAlignment = VerticalAlignment.Center
        text_box.Text = value or u""
        Grid.SetColumn(text_box, 1)
        grid.Children.Add(text_box)

        return _Row(grid, text_box)

    def _build_offsets_section(self):
        panel = StackPanel()
        panel.Margin = Thickness(8, 8, 8, 8)
        for field_name, label in _OFFSET_FIELDS:
            row = self._build_number_row(label, getattr(self._standard, field_name))
            self._scalar_controls[field_name] = row.control
            panel.Children.Add(row.container)
        return panel

    def _build_sanitary_section(self):
        panel = StackPanel()
        panel.Margin = Thickness(8, 8, 8, 8)

        panel.Children.Add(self._section_label(u"Frequency factor by usage"))
        for usage, factor in sorted(self._standard.mep_frequency_factor_by_usage.items()):
            row = self._build_number_row(usage, factor)
            self._frequency_controls[usage] = row.control
            panel.Children.Add(row.container)

        panel.Children.Add(self._section_label(u"Discharge units by fixture type"))
        for fixture, du in sorted(self._standard.mep_discharge_units_by_fixture_type.items()):
            row = self._build_number_row(fixture, du)
            self._discharge_controls[fixture] = row.control
            panel.Children.Add(row.container)

        panel.Children.Add(self._section_label(u"Minimum slope by pipe size"))
        for dn_mm, slope_percent in self._standard.mep_min_slope_table_percent:
            row = self._build_number_row(u"DN{0} min slope (%)".format(dn_mm), slope_percent)
            self._min_slope_controls.append((dn_mm, row.control))
            panel.Children.Add(row.container)

        row = self._build_number_row(
            u"Maximum slope (%) - optional, blank = no cap", self._standard.mep_max_slope_percent)
        self._max_slope_control = row.control
        panel.Children.Add(row.container)

        panel.Children.Add(self._section_label(u"Pipe capacity by size (discharge units)"))
        for dn_mm, capacity_du in self._standard.mep_pipe_capacity_table_du:
            row = self._build_number_row(u"DN{0} capacity (DU)".format(dn_mm), capacity_du)
            self._capacity_controls.append((dn_mm, row.control))
            panel.Children.Add(row.container)

        return panel

    def _build_water_supply_section(self):
        panel = StackPanel()
        panel.Margin = Thickness(8, 8, 8, 8)

        row = self._build_number_row(u"Valve height above level (mm)", self._standard.mep_valve_height_mm)
        self._scalar_controls[u"mep_valve_height_mm"] = row.control
        panel.Children.Add(row.container)

        material_row = self._build_text_row(u"Default pipe material", self._standard.mep_default_pipe_material)
        self._material_control = material_row.control
        panel.Children.Add(material_row.container)

        pipe_type_row = self._build_text_row(
            u"Default pipe type name (blank = pick per run)",
            self._standard.mep_default_pipe_type_name or u"")
        self._pipe_type_control = pipe_type_row.control
        panel.Children.Add(pipe_type_row.container)

        return panel

    # -- reading / persisting -------------------------------------------

    def read_values(self):
        """Current control values as a dict shaped like Standard.to_dict() -
        starts from the last-loaded Standard so untouched keys this page
        doesn't expose (name, tolerances, collision fields) survive."""
        data = self._standard.to_dict()
        for field_name, control in self._scalar_controls.items():
            data[field_name] = _parse_float(control.Text)
        data[u"mep_frequency_factor_by_usage"] = dict(
            (usage, _parse_float(control.Text)) for usage, control in self._frequency_controls.items())
        data[u"mep_discharge_units_by_fixture_type"] = dict(
            (fixture, _parse_float(control.Text)) for fixture, control in self._discharge_controls.items())
        data[u"mep_min_slope_table_percent"] = [
            (dn_mm, _parse_float(control.Text)) for dn_mm, control in self._min_slope_controls]
        data[u"mep_max_slope_percent"] = _parse_float(self._max_slope_control.Text)
        data[u"mep_pipe_capacity_table_du"] = [
            (dn_mm, _parse_float(control.Text)) for dn_mm, control in self._capacity_controls]
        material = (self._material_control.Text or u"").strip()
        data[u"mep_default_pipe_material"] = material or self._standard.mep_default_pipe_material
        pipe_type = (self._pipe_type_control.Text or u"").strip()
        data[u"mep_default_pipe_type_name"] = pipe_type or None
        return data

    def _current_standard(self):
        return Standard.from_dict(self.read_values())

    def validate(self):
        return self._current_standard().validate()

    def apply(self):
        standard = self._current_standard()
        errors = standard.validate()
        if errors:
            raise ValueError(u"Cannot apply invalid Office Standards:\n" + u"\n".join(errors))
        self._standard = standard
        settings = get_settings()
        settings.set(_SETTINGS_KEY, standard.to_dict(), layer=LAYER_OFFICE)
        settings.save_layer_to_json(LAYER_OFFICE, office_standards_path())

    def _populate_controls(self, standard):
        for field_name, control in self._scalar_controls.items():
            control.Text = _format_number(getattr(standard, field_name))
        for usage, control in self._frequency_controls.items():
            control.Text = _format_number(standard.mep_frequency_factor_by_usage.get(usage, 0.0))
        for fixture, control in self._discharge_controls.items():
            control.Text = _format_number(standard.mep_discharge_units_by_fixture_type.get(fixture, 0.0))
        min_slope_by_dn = dict(standard.mep_min_slope_table_percent)
        for dn_mm, control in self._min_slope_controls:
            control.Text = _format_number(min_slope_by_dn.get(dn_mm, 0.0))
        self._max_slope_control.Text = (
            u"" if standard.mep_max_slope_percent is None else _format_number(standard.mep_max_slope_percent))
        capacity_by_dn = dict(standard.mep_pipe_capacity_table_du)
        for dn_mm, control in self._capacity_controls:
            control.Text = _format_number(capacity_by_dn.get(dn_mm, 0.0))
        self._material_control.Text = standard.mep_default_pipe_material
        self._pipe_type_control.Text = standard.mep_default_pipe_type_name or u""

    def reset_to_defaults(self):
        """Resets the ALREADY-BUILT controls' displayed values to
        default_standard() - does not persist until apply() runs afterward."""
        self._populate_controls(default_standard())

    def export_to_file(self, path):
        with open(path, u"w") as f:
            json.dump(self.read_values(), f, indent=2, sort_keys=True)

    def import_from_file(self, path):
        with open(path, u"r") as f:
            data = json.load(f)
        imported = Standard.from_dict(data)
        errors = imported.validate()
        if errors:
            raise ValueError(u"Cannot import invalid Office Standards:\n" + u"\n".join(errors))
        self._standard = imported
        self._populate_controls(imported)


def register(registry):
    registry.register(SettingsPageDescriptor(
        page_id=u"office_standards",
        category=u"Office Standards",
        title=u"Office Standards",
        description=(
            u"Dimension offsets and spacing used by every dimensioning tool, plus "
            u"MEP sizing tables (flagged where values are un-validated placeholders, "
            u"not yet checked against a published standard)."),
        page_factory=OfficeStandardsPage,
        keywords=[u"dimension", u"offset", u"gap", u"spacing", u"mep", u"pipe",
                  u"slope", u"discharge", u"valve", u"standard"],
    ))


def register_manifest(registry):
    """Registered today per the platform design's own rule: only modules with
    a real settings page get a manifest - no mechanical backfill for the
    ~30 other existing buttons that have no settings yet."""
    registry.register(ModuleManifest(
        module_id=u"office_standards",
        name=u"Office Standards",
        version=u"0.1.0",
        description=u"Dimension offsets and MEP sizing tables, editable from Settings.",
        category=u"Office Standards",
        settings_pages=[u"office_standards"],
    ))
