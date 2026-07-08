# -*- coding: utf-8 -*-
"""Axis-aligned bounding-box summary of a dimensionable element (wall, column, ...).

Pure domain data - no Revit types (ADR-0001). `ref` is an opaque handle the Revit
adapter attaches (e.g. an ElementId) and later reads back when writing dimensions;
domain code never inspects what `ref` actually is.
"""


class ElementInfo(object):
    def __init__(self, ref, category, min_x, max_x, min_y, max_y):
        self.ref = ref
        self.category = category
        self.min_x = min_x
        self.max_x = max_x
        self.min_y = min_y
        self.max_y = max_y

    @property
    def width_x(self):
        return abs(self.max_x - self.min_x)

    @property
    def width_y(self):
        return abs(self.max_y - self.min_y)

    @property
    def center_x(self):
        return (self.min_x + self.max_x) / 2.0

    @property
    def center_y(self):
        return (self.min_y + self.max_y) / 2.0

    def __repr__(self):
        # IronPython 2.7 quirk: ".Nf" format specs raise ValueError on int operands
        # (CPython auto-casts). Explicit float() keeps this safe on both engines.
        return u"<ElementInfo {0} x[{1:.1f}..{2:.1f}] y[{3:.1f}..{4:.1f}]>".format(
            self.category, float(self.min_x), float(self.max_x),
            float(self.min_y), float(self.max_y))
