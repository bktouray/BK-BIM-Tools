# -*- coding: utf-8 -*-
"""Groups doors/windows by their host wall, scoped to a view - so wall-run
dimensioning can look up a wall's openings in O(1) instead of rescanning all
openings per wall (PHASE_1_PLAN follow-up: Walls & Openings dimensioning).
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector

from bkbim.revit.adapter.stable_representation import element_id_token


def group_openings_by_host(doc, view):
    """Returns dict[host_id_token] -> list of door/window FamilyInstance elements,
    for every door/window visible in `view` that has a host wall.
    """
    doors = FilteredElementCollector(doc, view.Id).OfCategory(
        BuiltInCategory.OST_Doors).WhereElementIsNotElementType().ToElements()
    windows = FilteredElementCollector(doc, view.Id).OfCategory(
        BuiltInCategory.OST_Windows).WhereElementIsNotElementType().ToElements()

    grouped = {}
    for opening in list(doors) + list(windows):
        host = getattr(opening, "Host", None)
        if host is None:
            continue
        key = element_id_token(host.Id)
        grouped.setdefault(key, []).append(opening)

    return grouped
