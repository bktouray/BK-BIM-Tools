# -*- coding: utf-8 -*-
"""Reads every straight grid's position/orientation across the whole
document, for the Renumber Grids utility. Grid Name is a document-wide
parameter (unlike datum extent, which is per-view), so this collects every
grid in the model rather than scoping to the active view.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import FilteredElementCollector, Grid, Line

from bkbim.domain.models.grid_info import ORIENTATION_HORIZONTAL, ORIENTATION_VERTICAL
from bkbim.domain.models.grid_position import GridPositionInfo


def list_all_grids(doc):
    """Returns list[GridPositionInfo] for every straight grid in `doc`.
    Angled/curved grids are skipped - they don't classify as vertical or
    horizontal, same convention as the dimensioning tools' grid reader.
    """
    grids = FilteredElementCollector(doc).OfClass(Grid).WhereElementIsNotElementType().ToElements()
    result = []
    for grid in grids:
        info = _grid_position(grid)
        if info is not None:
            result.append(info)
    return result


def _grid_position(grid):
    try:
        curve = grid.Curve
        if not isinstance(curve, Line):
            return None  # angled/curved grid - out of scope

        direction = curve.Direction.Normalize()
        p0 = curve.GetEndPoint(0)
        p1 = curve.GetEndPoint(1)

        if abs(direction.Y) < 0.1:
            orientation = ORIENTATION_HORIZONTAL
            coord = (p0.Y + p1.Y) / 2.0
        elif abs(direction.X) < 0.1:
            orientation = ORIENTATION_VERTICAL
            coord = (p0.X + p1.X) / 2.0
        else:
            return None  # angled grid - out of scope

        return GridPositionInfo(ref=grid, orientation=orientation, coord=coord)
    except Exception:
        return None
