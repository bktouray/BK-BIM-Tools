# -*- coding: utf-8 -*-
"""Reads each grid's current datum-extent state (2D/3D) in a view, for the
Toggle Grid 2D/3D utility (2026-07-07).
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import DatumEnds, DatumExtentType, FilteredElementCollector, Grid

from bkbim.domain.models.grid_extent import EXTENT_MODEL, EXTENT_VIEW_SPECIFIC, GridExtentInfo


def _to_domain_extent(revit_extent):
    return EXTENT_MODEL if revit_extent == DatumExtentType.Model else EXTENT_VIEW_SPECIFIC


def list_grids_with_extent(doc, view):
    """Returns list[GridExtentInfo] for every grid visible in `view`. A grid
    whose extent can't be read (rare - e.g. not actually shown in this view)
    is skipped rather than guessed at.
    """
    grids = FilteredElementCollector(doc, view.Id).OfClass(Grid).ToElements()
    result = []
    for grid in grids:
        try:
            end0 = _to_domain_extent(grid.GetDatumExtentTypeInView(DatumEnds.End0, view))
            end1 = _to_domain_extent(grid.GetDatumExtentTypeInView(DatumEnds.End1, view))
        except Exception:
            continue
        result.append(GridExtentInfo(ref=grid, end0_extent=end0, end1_extent=end1))
    return result
