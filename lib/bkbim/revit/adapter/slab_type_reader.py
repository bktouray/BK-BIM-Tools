# -*- coding: utf-8 -*-
"""Lists Floor (slab) elements/types in a view, for Slab Dimensions - mirrors
structural_type_reader.py's pattern, but `Floor` isn't a `FamilyInstance` (no
`.Symbol`), so type lookup goes through `GetTypeId()`/`doc.GetElement()`
instead.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector, Floor

from bkbim.revit.adapter.stable_representation import element_id_token


def list_slab_elements_in_view(doc, view):
    """Returns every Floor visible in `view`."""
    collected = FilteredElementCollector(doc, view.Id).OfCategory(
        BuiltInCategory.OST_Floors).WhereElementIsNotElementType().ToElements()
    return [e for e in collected if isinstance(e, Floor)]


def list_slab_types_in_view(doc, view):
    """Returns the distinct FloorType elements used by slabs visible in `view`,
    ordered by first appearance.
    """
    seen_ids = set()
    types = []
    for slab in list_slab_elements_in_view(doc, view):
        type_id = slab.GetTypeId()
        floor_type = doc.GetElement(type_id)
        if floor_type is None:
            continue
        id_value = element_id_token(type_id)
        if id_value in seen_ids:
            continue
        seen_ids.add(id_value)
        types.append(floor_type)
    return types
