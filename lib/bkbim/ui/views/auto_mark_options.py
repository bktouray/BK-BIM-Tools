# -*- coding: utf-8 -*-
"""Code-behind for AutoMarkOptions.xaml - one family group per row, each with
its own prefix TextBox and a live preview of the mark each type would get
(recomputed as the user types, per family only) - every instance of a type
shares that one mark. Family rows are built programmatically
(StackPanel.Children.Add), the same idiom category_picker.py uses for its
choice buttons - there's no existing precedent in this codebase for a
data-bound repeating XAML template, and this keeps the same style.

Deliberately decoupled from the Revit adapter layer (dimension_a_label/
dimension_b_label are passed in by the caller, same as
structural_dimension_options.py takes a type_name_fn callback rather than
importing revit.adapter itself) - only bkbim.domain is imported here.
"""

import os

import clr

clr.AddReference("PresentationFramework")

from System.Windows import (
    CornerRadius, FontWeights, GridLength, GridUnitType, Thickness, VerticalAlignment,
)
from System.Windows.Controls import Border, ColumnDefinition, Grid, StackPanel, TextBlock, TextBox
from pyrevit import forms

from bkbim.domain.marking.mark_planner import sorted_type_groups


def _format_dim(value_mm):
    if value_mm is None:
        return u"?"
    # IronPython 2.7 quirk: ".Nf" format specs raise ValueError on int
    # operands (CPython auto-casts). Explicit float() keeps this safe on
    # both engines.
    return u"{0:.0f}".format(float(value_mm))


class AutoMarkOptionsResult(object):
    def __init__(self, prefixes):
        self.prefixes = prefixes  # dict {family_name: prefix string}


class _FamilyRow(object):
    def __init__(self, family_group, prefix_box, type_rows):
        self.family_group = family_group
        self.prefix_box = prefix_box
        self.type_rows = type_rows  # list of (MarkTypeGroup, TextBlock)


class AutoMarkOptionsWindow(forms.WPFWindow):
    def __init__(self, category, dimension_a_label, dimension_b_label, family_groups, default_prefixes):
        xaml_path = os.path.join(os.path.dirname(__file__), "AutoMarkOptions.xaml")
        forms.WPFWindow.__init__(self, xaml_path)

        self.result = None
        self._family_rows = []

        title = u"Auto Mark - {0}".format(category)
        self.Title = u"BK BIM Tools - {0}".format(title)
        self.TitleText.Text = title
        self.SubtitleText.Text = (
            u"Give each family a prefix - types are sorted by {0} x {1}, "
            u"largest to smallest, restarting the count at 1 per family."
        ).format(dimension_a_label, dimension_b_label)

        surface_brush = self.FindResource(u"Surface.Raised")
        border_brush = self.FindResource(u"Border.Default")
        text_secondary_brush = self.FindResource(u"Text.Secondary")

        # Alphabetical so re-opening the window doesn't reshuffle rows.
        ordered_families = sorted(family_groups, key=lambda fg: fg.family_name.lower())
        for family_group in ordered_families:
            row = self._build_family_row(
                family_group, default_prefixes, surface_brush, border_brush, text_secondary_brush)
            self.FamilyGroupsPanel.Children.Add(row)

        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

    def _build_family_row(self, family_group, default_prefixes, surface_brush, border_brush, text_secondary_brush):
        border = Border()
        border.Background = surface_brush
        border.BorderBrush = border_brush
        border.BorderThickness = Thickness(1)
        border.CornerRadius = CornerRadius(6)
        border.Padding = Thickness(12, 10, 12, 10)
        border.Margin = Thickness(0, 0, 0, 10)

        outer = StackPanel()

        header = Grid()
        header.ColumnDefinitions.Add(ColumnDefinition(Width=GridLength(1, GridUnitType.Star)))
        header.ColumnDefinitions.Add(ColumnDefinition(Width=GridLength(72)))

        name_stack = StackPanel()
        name_block = TextBlock()
        name_block.Text = family_group.family_name
        name_block.FontWeight = FontWeights.SemiBold
        name_block.FontSize = 14
        name_stack.Children.Add(name_block)

        count_block = TextBlock()
        count_block.Text = u"{0} type(s), {1} instance(s)".format(
            len(family_group.type_groups), family_group.instance_count)
        count_block.FontSize = 11
        count_block.Foreground = text_secondary_brush
        name_stack.Children.Add(count_block)

        Grid.SetColumn(name_stack, 0)
        header.Children.Add(name_stack)

        prefix_box = TextBox()
        prefix_box.Width = 64
        prefix_box.Height = 26
        prefix_box.VerticalContentAlignment = VerticalAlignment.Center
        prefix_box.Text = default_prefixes.get(family_group.family_name, u"") or u""
        Grid.SetColumn(prefix_box, 1)
        header.Children.Add(prefix_box)

        outer.Children.Add(header)

        type_rows = []
        for type_group in sorted_type_groups(family_group.type_groups):
            label = TextBlock()
            label.Margin = Thickness(0, 6, 0, 0)
            label.FontSize = 12
            outer.Children.Add(label)
            type_rows.append((type_group, label))

        border.Child = outer

        family_index = len(self._family_rows)
        self._family_rows.append(_FamilyRow(family_group, prefix_box, type_rows))
        self._update_family_preview(family_index)
        prefix_box.TextChanged += self._make_update_handler(family_index)

        return border

    def _make_update_handler(self, family_index):
        def handler(sender, args):
            self._update_family_preview(family_index)
        return handler

    def _update_family_preview(self, family_index):
        # One mark per type, shared by every instance of it (product owner:
        # "if the family name and type is the same, they should have the
        # same mark") - so the preview is a single value per row, not a
        # range, and n counts TYPES, not instances.
        row = self._family_rows[family_index]
        prefix = (row.prefix_box.Text or u"").strip()
        n = 0
        for type_group, label in row.type_rows:
            n += 1
            mark_text = u"(no prefix - skipped)" if not prefix else u"{0}{1}".format(prefix, n)
            label.Text = u"{0}    {1} x {2} mm    {3} pcs    {4}".format(
                type_group.type_name, _format_dim(type_group.dimension_a_mm),
                _format_dim(type_group.dimension_b_mm), type_group.instance_count, mark_text)

    def _on_run(self, sender, args):
        prefixes = {}
        for row in self._family_rows:
            prefix = (row.prefix_box.Text or u"").strip()
            if prefix:
                prefixes[row.family_group.family_name] = prefix
        self.result = AutoMarkOptionsResult(prefixes=prefixes)
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_auto_mark_options(category, dimension_a_label, dimension_b_label, family_groups, default_prefixes):
    """Shows the modal Auto Mark review window.

    Returns an AutoMarkOptionsResult, or None if the user cancelled.
    """
    window = AutoMarkOptionsWindow(
        category, dimension_a_label, dimension_b_label, family_groups, default_prefixes)
    window.ShowDialog()
    return window.result
