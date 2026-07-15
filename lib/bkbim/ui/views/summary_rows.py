# -*- coding: utf-8 -*-
"""Shared "here's what was detected" checkmark-bulleted row list, used by any
options/result window that wants to show a short summary before or after a
run (BOQResult's per-sheet export summary, TypicalSectionOptions' per-Mark
group breakdown). The window must define a "SummaryRow" TextBlock style and
a "Brand.Primary" brush in its own resources (same convention every window in
this suite already follows for its other local Styles).
"""

from System.Windows import FontWeights, TextWrapping, Thickness
from System.Windows.Controls import Orientation, StackPanel, TextBlock


def render_summary_rows(window, panel, lines):
    """Adds one bulleted row per line in `lines` to `panel` (a StackPanel)."""
    for text in lines:
        panel.Children.Add(_make_row(window, text))


def _make_row(window, text):
    row = StackPanel()
    row.Orientation = Orientation.Horizontal
    row.Margin = Thickness(0, 0, 0, 4)

    bullet = TextBlock()
    bullet.Text = u"✓"
    bullet.Margin = Thickness(0, 0, 8, 0)
    bullet.Foreground = window.FindResource("Brand.Primary")
    bullet.FontWeight = FontWeights.SemiBold
    row.Children.Add(bullet)

    label = TextBlock()
    label.Text = text
    label.TextWrapping = TextWrapping.Wrap
    label.Style = window.FindResource("SummaryRow")
    row.Children.Add(label)
    return row
