# -*- coding: utf-8 -*-
"""A grid line relevant to dimensioning: orientation, position, and bubble end.

Pure domain data (ADR-0001) - p0/p1 are plain (x, y) tuples, not Revit XYZ. `ref` is
an opaque handle the Revit adapter attaches and reads back.
"""

ORIENTATION_HORIZONTAL = u"horizontal"
ORIENTATION_VERTICAL = u"vertical"

BUBBLE_P0 = u"p0"
BUBBLE_P1 = u"p1"


class GridInfo(object):
    def __init__(self, ref, name, orientation, coord, p0, p1, bubble_end):
        self.ref = ref
        self.name = name
        self.orientation = orientation
        self.coord = coord
        self.p0 = p0
        self.p1 = p1
        self.bubble_end = bubble_end

    def __repr__(self):
        # IronPython 2.7 quirk: ".Nf" format specs raise ValueError on int operands
        # (CPython auto-casts). Explicit float() keeps this safe on both engines.
        return u"<GridInfo {0} {1} coord={2:.1f}>".format(
            self.name, self.orientation, float(self.coord))
