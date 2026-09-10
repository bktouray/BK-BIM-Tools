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
clr.AddReference("PresentationCore")

from System.Windows import (
    CornerRadius, FontWeights, GridLength, GridUnitType, Thickness, Visibility, VerticalAlignment,
)
from System.Windows.Controls import Border, ColumnDefinition, Grid, StackPanel, TextBlock, TextBox
from System.Windows.Documents import Run
from System.Windows.Media import Color, SolidColorBrush
from pyrevit import forms

from bkbim.domain.marking.mark_planner import (
    MODE_SIZE_AND_REINFORCEMENT, MODE_SIZE_ONLY, reinforcement_sorted_groups, sorted_type_group_clusters,
)
from bkbim.domain.marking.reinforcement_signature import (
    SOURCE_MODELED_REBAR, SOURCE_NAVIATE_TEXT, SOURCE_NONE, SOURCE_TEKLA_TEXT,
)
from bkbim.ui.tokens import resolve_tokens_path

# Product owner, 2026-07-15: "how do i know if it is using tekla exported
# text, nv rebar or modelled rebar? make me notice that difference when
# marking." Color-coded by trust level, not just labeled - modeled rebar
# is the most reliable (real geometry, not an export snapshot), exported
# text least (product owner's own words: "the export data isn't always
# correct"), no-data is neutral. No matching semantic tokens exist yet in
# Tokens.xaml (only Brand/Text/Surface/Border) - defined here rather than
# adding new global tokens for a need that's localized to this one window.
_SOURCE_COLORS = {
    SOURCE_MODELED_REBAR: Color.FromRgb(0x1B, 0x8A, 0x5A),   # green - most trusted
    SOURCE_TEKLA_TEXT: Color.FromRgb(0xC2, 0x6A, 0x00),      # amber - exported text
    SOURCE_NAVIATE_TEXT: Color.FromRgb(0xC2, 0x6A, 0x00),    # amber - exported text
    SOURCE_NONE: Color.FromRgb(0x8A, 0x8A, 0x8A),            # gray - no rebar data
}
_MIXED_SOURCE_COLOR = Color.FromRgb(0x6B, 0x46, 0xC1)  # purple - flags a group blending 2+ sources


def _source_run(sources):
    """A colored Run naming the reinforcement data source(s) for one
    group. Usually one source; if a group blends more than one (a modeled-
    rebar instance and a text-only instance landed on the identical real
    design and merged - see MarkReinforcementGroup's own docstring), shows
    all of them in a distinct "mixed" color rather than picking just one
    and hiding the blend.
    """
    if not sources:
        text, color = SOURCE_NONE, _SOURCE_COLORS[SOURCE_NONE]
    elif len(sources) == 1:
        text, color = sources[0], _SOURCE_COLORS.get(sources[0], _MIXED_SOURCE_COLOR)
    else:
        text, color = u" + ".join(sources), _MIXED_SOURCE_COLOR
    run = Run(u"[{0}]".format(text))
    run.Foreground = SolidColorBrush(color)
    return run


def _format_dim(value_mm):
    if value_mm is None:
        return u"?"
    # IronPython 2.7 quirk: ".Nf" format specs raise ValueError on int
    # operands (CPython auto-casts). Explicit float() keeps this safe on
    # both engines.
    return u"{0:.0f}".format(float(value_mm))


class AutoMarkOptionsResult(object):
    def __init__(self, prefixes, mode=MODE_SIZE_ONLY):
        self.prefixes = prefixes  # dict {family_name: prefix string}
        self.mode = mode


class _FamilyRow(object):
    def __init__(self, family_group, prefix_box, type_rows):
        self.family_group = family_group
        self.prefix_box = prefix_box
        self.type_rows = type_rows  # list of (MarkTypeGroup, container StackPanel)


class AutoMarkOptionsWindow(forms.WPFWindow):
    def __init__(self, category, dimension_a_label, dimension_b_label, family_groups, default_prefixes,
                 supports_reinforcement=False, default_mode=MODE_SIZE_ONLY):
        xaml_path = os.path.join(os.path.dirname(__file__), "AutoMarkOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self.result = None
        self._family_rows = []

        title = u"Auto Mark - {0}".format(category)
        self.Title = u"BK BIM Tools - {0}".format(title)
        self.TitleText.Text = title
        sort_note = u"{0} x {1}".format(dimension_a_label, dimension_b_label)
        has_host_wall_variants = any(
            getattr(tg, "host_thickness_mm", None) is not None
            for fg in family_groups for tg in fg.type_groups)
        if category in (u"Doors", u"Windows") and has_host_wall_variants:
            sort_note = u"{0}; wall thickness variants get A/B suffixes, thickest first".format(sort_note)
        self.SubtitleText.Text = (
            u"Give each family a prefix - types are sorted by {0}, largest "
            u"to smallest, restarting the count at 1 per family."
        ).format(sort_note)

        # Categories with no rebar concept (Doors/Windows) never show the
        # grouping-mode choice at all, rather than showing a mode with no
        # effect on them.
        if supports_reinforcement:
            self.ModeGroupPanel.Visibility = Visibility.Visible
            self.SizeAndReinforcementRadio.IsChecked = (default_mode == MODE_SIZE_AND_REINFORCEMENT)
            self.SizeOnlyRadio.IsChecked = (default_mode != MODE_SIZE_AND_REINFORCEMENT)
        else:
            self.ModeGroupPanel.Visibility = Visibility.Collapsed

        surface_brush = self.FindResource(u"Surface.Raised")
        border_brush = self.FindResource(u"Border.Default")
        text_secondary_brush = self.FindResource(u"Text.Secondary")
        self._text_secondary_brush = text_secondary_brush

        # Alphabetical so re-opening the window doesn't reshuffle rows.
        ordered_families = sorted(family_groups, key=lambda fg: fg.family_name.lower())
        for family_group in ordered_families:
            row = self._build_family_row(
                family_group, default_prefixes, surface_brush, border_brush, text_secondary_brush)
            self.FamilyGroupsPanel.Children.Add(row)

        self.SizeOnlyRadio.Checked += self._on_mode_changed
        self.SizeAndReinforcementRadio.Checked += self._on_mode_changed
        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

    def _current_mode(self):
        return MODE_SIZE_AND_REINFORCEMENT if self.SizeAndReinforcementRadio.IsChecked else MODE_SIZE_ONLY

    def _on_mode_changed(self, sender, args):
        for i in range(len(self._family_rows)):
            self._update_family_preview(i)

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
        count_block.Text = u"{0} mark group(s), {1} instance(s)".format(
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
        for cluster in sorted_type_group_clusters(family_group.type_groups):
            container = StackPanel()
            container.Margin = Thickness(0, 6, 0, 0)
            outer.Children.Add(container)
            type_rows.append((cluster, container))

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
        # One base mark per type/size. Doors/Windows can split that same
        # base mark into wall-thickness suffixes (D2-A/D2-B, thickest first);
        # structural categories can split by reinforcement in the existing
        # size+reinforcement mode. n counts base groups, not variants.
        row = self._family_rows[family_index]
        prefix = (row.prefix_box.Text or u"").strip()
        mode = self._current_mode()
        n = 0
        for cluster, container in row.type_rows:
            n += 1
            container.Children.Clear()
            base_mark = u"(no prefix - skipped)" if not prefix else u"{0}{1}".format(prefix, n)
            type_group = cluster[0]
            cluster_instance_count = sum(tg.instance_count for tg in cluster)
            has_host_variants = (
                len(cluster) > 1 and any(getattr(tg, "host_thickness_mm", None) is not None for tg in cluster))

            reinforcement_groups = type_group.reinforcement_groups

            # Aggregate source badge for the header line (product owner,
            # 2026-07-15: "make me notice that difference when marking") -
            # shown regardless of mode, since the underlying rebar data was
            # read either way; union of every sub-group's sources for this
            # type, first-appearance order.
            aggregate_sources = []
            if reinforcement_groups:
                for sub_group in reinforcement_groups:
                    for source in sub_group.sources:
                        if source not in aggregate_sources:
                            aggregate_sources.append(source)

            header_line = TextBlock()
            header_line.FontSize = 12
            host_thickness = getattr(type_group, "host_thickness_mm", None)
            host_text = u""
            if has_host_variants:
                host_text = u"    {0} wall thicknesses".format(len(cluster))
            elif host_thickness is not None:
                host_text = u"    Wall {0} mm".format(_format_dim(host_thickness))
            header_line.Inlines.Add(Run(u"{0}    {1} x {2} mm{3}    {4} pcs    ".format(
                type_group.type_name, _format_dim(type_group.dimension_a_mm),
                _format_dim(type_group.dimension_b_mm), host_text, cluster_instance_count)))
            header_line.Inlines.Add(_source_run(aggregate_sources))
            container.Children.Add(header_line)

            if has_host_variants:
                for i, variant in enumerate(cluster):
                    letter = chr(ord(u"A") + i) if i < 26 else u"?"
                    sub_line = TextBlock()
                    sub_line.FontSize = 11
                    sub_line.Margin = Thickness(12, 2, 0, 0)
                    sub_line.Foreground = self._text_secondary_brush
                    wall_text = _format_dim(getattr(variant, "host_thickness_mm", None))
                    mark_text = base_mark if not prefix else u"{0}-{1}".format(base_mark, letter)
                    sub_line.Text = u"Wall {0} mm    {1} pcs    {2}".format(
                        wall_text, variant.instance_count, mark_text)
                    container.Children.Add(sub_line)
            elif mode == MODE_SIZE_AND_REINFORCEMENT and reinforcement_groups and len(reinforcement_groups) > 1:
                for i, sub_group in enumerate(reinforcement_sorted_groups(reinforcement_groups)):
                    letter = chr(ord(u"A") + i) if i < 26 else u"?"
                    sub_line = TextBlock()
                    sub_line.FontSize = 11
                    sub_line.Margin = Thickness(12, 2, 0, 0)
                    sub_line.Foreground = self._text_secondary_brush
                    mark_text = base_mark if not prefix else u"{0}-{1}".format(base_mark, letter)
                    sub_line.Inlines.Add(Run(u"{0} pcs    {1}    [{2}]    ".format(
                        sub_group.instance_count, mark_text, sub_group.signature)))
                    sub_line.Inlines.Add(_source_run(sub_group.sources))
                    container.Children.Add(sub_line)
            else:
                mark_line = TextBlock()
                mark_line.FontSize = 12
                mark_line.Margin = Thickness(12, 2, 0, 0)
                mark_line.Text = base_mark
                container.Children.Add(mark_line)

    def _on_run(self, sender, args):
        prefixes = {}
        for row in self._family_rows:
            prefix = (row.prefix_box.Text or u"").strip()
            if prefix:
                prefixes[row.family_group.family_name] = prefix
        self.result = AutoMarkOptionsResult(prefixes=prefixes, mode=self._current_mode())
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_auto_mark_options(category, dimension_a_label, dimension_b_label, family_groups, default_prefixes,
                            supports_reinforcement=False, default_mode=MODE_SIZE_ONLY):
    """Shows the modal Auto Mark review window.

    Returns an AutoMarkOptionsResult, or None if the user cancelled.
    """
    window = AutoMarkOptionsWindow(
        category, dimension_a_label, dimension_b_label, family_groups, default_prefixes,
        supports_reinforcement=supports_reinforcement, default_mode=default_mode)
    window.ShowDialog()
    return window.result
