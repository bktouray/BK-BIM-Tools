# -*- coding: utf-8 -*-
"""A grid's current datum-extent state (Revit calls this a grid's "3D"/"2D"
toggle - Model extent is shared/propagated across every view that shows the
grid, ViewSpecific extent only affects the current view). Pure domain data
(ADR-0001) - `ref` is an opaque handle the Revit adapter attaches and reads
back, same convention as GridInfo/ElementInfo.
"""

EXTENT_VIEW_SPECIFIC = u"view_specific"  # Revit UI calls this "2D"
EXTENT_MODEL = u"model"  # Revit UI calls this "3D"


def toggle_extent(current):
    """Flips VIEW_SPECIFIC <-> MODEL - a plain toggle, not a one-way
    conversion, so running the command twice returns every grid to where it
    started (product owner, 2026-07-07: "change all 3D grids to 2D grids and
    versi versa").
    """
    return EXTENT_MODEL if current == EXTENT_VIEW_SPECIFIC else EXTENT_VIEW_SPECIFIC


class GridExtentInfo(object):
    """One grid's current extent state, both ends independently - a grid can
    have its two ends set differently (e.g. only one end nudged to 2D), so
    this never collapses them into a single flag.
    """

    def __init__(self, ref, end0_extent, end1_extent):
        self.ref = ref
        self.end0_extent = end0_extent
        self.end1_extent = end1_extent
