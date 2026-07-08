# -*- coding: utf-8 -*-
"""Lists the distinct wall types actually in use in a view, for the "which walls to
use for dimensions" picker (product owner, 2026-07-05: moving to a modeling
convention with each layer - blockwork, plaster, tile - as its own wall element;
needs to choose which wall type(s) count as the dimension-worthy structure).
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector, Wall


def list_wall_types_in_view(doc, view):
    """Returns the distinct WallType elements used by walls visible in `view`,
    ordered by their Id (stable, arbitrary-but-consistent ordering).

    OST_Walls can include non-Wall elements (confirmed live 2026-07-05: a
    FamilyInstance, likely a curtain wall panel, raised AttributeError on
    .WallType) - explicitly skip anything that isn't a real Wall.
    """
    walls = FilteredElementCollector(doc, view.Id).OfCategory(
        BuiltInCategory.OST_Walls).WhereElementIsNotElementType().ToElements()

    seen_ids = set()
    wall_types = []
    for wall in walls:
        if not isinstance(wall, Wall):
            continue
        wall_type = wall.WallType
        if wall_type is None:
            continue
        id_value = wall_type.Id.Value if hasattr(wall_type.Id, "Value") else wall_type.Id.IntegerValue
        if id_value in seen_ids:
            continue
        seen_ids.add(id_value)
        wall_types.append(wall_type)

    return wall_types
