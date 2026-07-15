# -*- coding: utf-8 -*-
"""Grid datum-extent writer port (SAD Sec 4.2).

Implemented by bkbim.revit.adapter.grid_extent_writer.RevitGridExtentWriter.
Domain/app code depends on this interface only - never on Revit's
DatumExtentType/DatumEnds directly (ADR-0001).
"""


class IGridExtentWriter(object):
    def set_extent(self, grid_ref, end0_extent, end1_extent):
        """Applies `end0_extent`/`end1_extent` (domain EXTENT_* strings, see
        bkbim.domain.models.grid_extent) to `grid_ref`'s two ends in the
        current view. Raises on failure - the caller counts that as a
        per-grid skip, not a fatal error for the whole run.
        """
        raise NotImplementedError


class IGridRenumberWriter(object):
    def set_name(self, grid_ref, new_name):
        """Sets `grid_ref`'s Name to `new_name`. Raises on failure (e.g. a
        name collision) - the caller counts that as a per-grid skip, not a
        fatal error for the whole run.
        """
        raise NotImplementedError
