# -*- coding: utf-8 -*-
"""Small pictogram glyphs for the Structural Element Dimensions category
picker (product owner, 2026-07-07: "add small icons to this page when I click
Structural Dimensions"). Built from plain WPF shapes, not image files - no
external assets or network fetch needed for a handful of simple silhouettes,
and they stay crisp at any DPI. Column/Beam/Footing/Slab only - Smart
Dimension's own top-level picker is untouched, matching the literal ask
("this page").
"""

import clr

clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore")
clr.AddReference("WindowsBase")

from System.Windows import HorizontalAlignment, VerticalAlignment
from System.Windows.Controls import Canvas, Grid, Viewbox
from System.Windows.Media import Color, SolidColorBrush
from System.Windows.Shapes import Rectangle

# Matches the lightened #333333 tone every ribbon icon was recolored to the
# same day ("make all the icons... a little less black") - keeps the picker's
# glyphs visually consistent with the buttons that led to it.
_GLYPH_COLOR = Color.FromRgb(0x33, 0x33, 0x33)


def _rect(width, height, radius=1.5):
    r = Rectangle()
    r.Width = width
    r.Height = height
    r.RadiusX = radius
    r.RadiusY = radius
    r.Fill = SolidColorBrush(_GLYPH_COLOR)
    return r


def _column_glyph():
    # Tall narrow bar - a column's elevation silhouette.
    return _rect(7, 20)


def _beam_glyph():
    # Wide short bar - a beam's elevation silhouette.
    return _rect(20, 7)


def _footing_glyph():
    # A column stub sitting on a wide spread pad - the classic footing
    # profile, distinguishing it from a plain beam/slab bar at a glance.
    grid = Grid()
    grid.Width = 22
    grid.Height = 20

    pad = _rect(22, 7)
    pad.VerticalAlignment = VerticalAlignment.Bottom
    grid.Children.Add(pad)

    stub = _rect(7, 12)
    stub.HorizontalAlignment = HorizontalAlignment.Center
    stub.VerticalAlignment = VerticalAlignment.Top
    grid.Children.Add(stub)

    return grid


def _slab_glyph():
    # A wide flat slab bar with two small downstand beams hanging from its
    # underside at each end - product owner, 2026-07-07: the plain thin bar
    # "looks the same as the beam," asked for "two small downstanding beams
    # on each side" to make the slab read as its own distinct silhouette.
    canvas = Canvas()
    canvas.Width = 22
    canvas.Height = 20

    slab = _rect(22, 5)
    Canvas.SetLeft(slab, 0)
    Canvas.SetTop(slab, 0)
    canvas.Children.Add(slab)

    left_beam = _rect(5, 9)
    Canvas.SetLeft(left_beam, 0)
    Canvas.SetTop(left_beam, 5)
    canvas.Children.Add(left_beam)

    right_beam = _rect(5, 9)
    Canvas.SetLeft(right_beam, 17)
    Canvas.SetTop(right_beam, 5)
    canvas.Children.Add(right_beam)

    return canvas


_GLYPHS = {
    u"Column": _column_glyph,
    u"Beam": _beam_glyph,
    u"Footing": _footing_glyph,
    u"Slab": _slab_glyph,
}


def structural_category_icon(choice):
    """Returns a small (24x24) WPF element for `choice`, or None if there's
    no glyph for it yet - keeps the picker usable for a future category added
    without a matching icon.
    """
    factory = _GLYPHS.get(choice)
    if factory is None:
        return None

    box = Viewbox()
    box.Width = 24
    box.Height = 24
    box.Child = factory()
    return box
