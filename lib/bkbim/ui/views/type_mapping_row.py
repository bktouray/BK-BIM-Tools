# -*- coding: utf-8 -*-
"""Shared "map this detected size-group to a family/type" row, built
programmatically the same way auto_mark_options.py's _build_family_row is -
there's no data-bound repeating XAML template anywhere in this codebase, so
this follows that exact idiom (System.Windows.Controls construction into a
caller-owned StackPanel) rather than introducing one.

Generalizes what AutoColumn (one row per section size), AutoWall (one row
per thickness), and the shared Door/Window opening window (one row per
width) all need: a ComboBox offering "Auto-generate" plus every existing
type, so the CAD-to-Revit redesign (2026-07-15) doesn't copy-paste the same
~40 lines of row-construction code four times.

Two base-family modes, matching what each tool's automation layer actually
supports:
  - per_row_base_family=False (Column, Wall): one base family/type is picked
    ONCE by the caller outside the loop of rows (get_or_create_sized_type /
    get_or_create_wall_type only ever take a single base symbol/type for the
    whole run) - so no base-family control appears in the row itself.
  - per_row_base_family=True (Door/Window): each width can size from its OWN
    base family (today's opening_tool.py already supports this per group) -
    so selecting Auto-generate reveals an inline "Base family: ... [Choose]"
    sub-row whose button invokes on_pick_base_family(), the existing
    familyutils.pick_family_symbol flow, unchanged.

show_height_field (Door/Window only) reveals a Height (mm) TextBox next to
the base-family control while Auto-generate is selected - only needed then,
since an existing type already carries its own height.
"""

import clr

clr.AddReference("PresentationFramework")

from System.Windows import CornerRadius, FontWeights, GridLength, GridUnitType, Thickness, Visibility
from System.Windows.Controls import (
    Border, Button, ColumnDefinition, ComboBox, Grid, Orientation, StackPanel, TextBlock, TextBox,
)

_AUTO_LABEL = u"⚙ Auto-generate"
_NO_BASE_FAMILY = u"(no base family chosen)"


class TypeMappingRow(object):
    """Live state for one size/thickness/width-group mapping row."""

    def __init__(self, group_key, combo, existing_types, base_family_label=None, height_box=None):
        self.group_key = group_key
        self.base_symbol = None  # set via set_base_family() when per_row_base_family
        self._combo = combo
        self._existing_types = existing_types  # parallel to combo items AFTER the Auto entry
        self._base_family_label = base_family_label
        self._height_box = height_box

    def is_auto(self):
        return self._combo.SelectedIndex == 0

    def set_base_family(self, symbol, label_text):
        self.base_symbol = symbol
        if self._base_family_label is not None:
            self._base_family_label.Text = label_text

    def get_selection(self):
        """Returns (kind, value, extra): kind is 'existing' or 'auto'.
        value is the picked FamilySymbol/WallType ('existing') or the base
        family/type to size from ('auto', may be None if never chosen).
        extra is {'height_mm': float|None} when a height field is present,
        else {}.
        """
        extra = {}
        if self._height_box is not None:
            try:
                extra[u"height_mm"] = float(self._height_box.Text)
            except (TypeError, ValueError):
                extra[u"height_mm"] = None
        if self.is_auto():
            return (u"auto", self.base_symbol, extra)
        idx = self._combo.SelectedIndex - 1
        type_obj = self._existing_types[idx] if 0 <= idx < len(self._existing_types) else None
        return (u"existing", type_obj, extra)


def build_type_mapping_row(group_key, group_label, count_label, existing_type_labels, existing_types,
                            per_row_base_family=False, on_pick_base_family=None,
                            show_height_field=False, default_height_mm=None,
                            surface_brush=None, border_brush=None, text_secondary_brush=None):
    """Builds one mapping row. Returns (border, TypeMappingRow)."""
    border = Border()
    if surface_brush is not None:
        border.Background = surface_brush
    if border_brush is not None:
        border.BorderBrush = border_brush
    border.BorderThickness = Thickness(1)
    border.CornerRadius = CornerRadius(6)
    border.Padding = Thickness(12, 10, 12, 10)
    border.Margin = Thickness(0, 0, 0, 10)

    outer = StackPanel()

    header = Grid()
    header.ColumnDefinitions.Add(ColumnDefinition(Width=GridLength(1, GridUnitType.Star)))
    header.ColumnDefinitions.Add(ColumnDefinition(Width=GridLength(220)))

    name_stack = StackPanel()
    name_block = TextBlock()
    name_block.Text = group_label
    name_block.FontWeight = FontWeights.SemiBold
    name_block.FontSize = 14
    name_stack.Children.Add(name_block)

    count_block = TextBlock()
    count_block.Text = count_label
    count_block.FontSize = 11
    if text_secondary_brush is not None:
        count_block.Foreground = text_secondary_brush
    name_stack.Children.Add(count_block)

    Grid.SetColumn(name_stack, 0)
    header.Children.Add(name_stack)

    combo = ComboBox()
    combo.Height = 28
    combo.Items.Add(_AUTO_LABEL)
    for label in existing_type_labels:
        combo.Items.Add(label)
    combo.SelectedIndex = 0
    Grid.SetColumn(combo, 1)
    header.Children.Add(combo)

    outer.Children.Add(header)

    base_family_label = None
    height_box = None
    sub_row = None
    if per_row_base_family or show_height_field:
        sub_row = Grid()
        sub_row.Margin = Thickness(0, 8, 0, 0)
        sub_row.ColumnDefinitions.Add(ColumnDefinition(Width=GridLength(1, GridUnitType.Star)))
        if show_height_field:
            sub_row.ColumnDefinitions.Add(ColumnDefinition(Width=GridLength(110)))

        if per_row_base_family:
            base_stack = StackPanel()
            base_stack.Orientation = Orientation.Horizontal
            base_label_caption = TextBlock()
            base_label_caption.Text = u"Base family: "
            base_label_caption.FontSize = 11
            if text_secondary_brush is not None:
                base_label_caption.Foreground = text_secondary_brush
            base_stack.Children.Add(base_label_caption)

            base_family_label = TextBlock()
            base_family_label.Text = _NO_BASE_FAMILY
            base_family_label.FontSize = 11
            base_stack.Children.Add(base_family_label)

            choose_button = Button()
            choose_button.Content = u"Choose…"
            choose_button.Margin = Thickness(8, 0, 0, 0)
            choose_button.Padding = Thickness(10, 2, 10, 2)
            base_stack.Children.Add(choose_button)

            Grid.SetColumn(base_stack, 0)
            sub_row.Children.Add(base_stack)

        if show_height_field:
            height_stack = StackPanel()
            height_caption = TextBlock()
            height_caption.Text = u"Height (mm)"
            height_caption.FontSize = 11
            if text_secondary_brush is not None:
                height_caption.Foreground = text_secondary_brush
            height_stack.Children.Add(height_caption)

            height_box = TextBox()
            height_box.Height = 26
            height_box.Text = unicode(int(default_height_mm)) if default_height_mm else u""
            height_stack.Children.Add(height_box)

            Grid.SetColumn(height_stack, 1 if per_row_base_family else 0)
            sub_row.Children.Add(height_stack)

        outer.Children.Add(sub_row)
        sub_row.Visibility = Visibility.Visible if combo.SelectedIndex == 0 else Visibility.Collapsed

    border.Child = outer

    row = TypeMappingRow(group_key, combo, existing_types,
                         base_family_label=base_family_label, height_box=height_box)

    if per_row_base_family and on_pick_base_family is not None:
        def _on_choose_base_family(sender, args):
            symbol, label_text = on_pick_base_family()
            if symbol is not None:
                row.set_base_family(symbol, label_text)
        choose_button.Click += _on_choose_base_family

    if sub_row is not None:
        def _on_selection_changed(sender, args):
            sub_row.Visibility = Visibility.Visible if row.is_auto() else Visibility.Collapsed
        combo.SelectionChanged += _on_selection_changed

    return border, row
