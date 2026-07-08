# -*- coding: utf-8 -*-
"""Prompts the user to interactively pick exterior perimeter walls, for the
3-string exterior wall dimensioning. Shown AFTER the options window (product
owner: "make it after I select the autodimension walls and openings and
after I select dimension styles and other stuff, prompt me to select
exterior walls").

Two-step prompt (2026-07-07, same-day follow-up - the original single
status-bar hint was "kinda subtle"): first a branded Yes/No choice ("give me
an option to say yes or no to dimension the exterior walls or just do the
conventional dimension"), then, only if Yes, a real `forms.alert()` popup
("make a visible prompt alerting the user that its time to select the
exterior walls") before the interactive pick starts.
"""

import clr

clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")

from Autodesk.Revit.DB import Wall
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
from pyrevit import forms

from bkbim.revit.adapter.stable_representation import element_id_token
from bkbim.ui.views.category_picker import show_category_picker

DIMENSION_EXTERIOR = u"Yes, dimension exterior walls (3 strings)"
SKIP_EXTERIOR = u"No, just conventional dimensioning"


class _WallOnlyFilter(ISelectionFilter):
    def AllowElement(self, elem):
        return isinstance(elem, Wall)

    def AllowReference(self, reference, point):
        return False


def pick_exterior_walls(uidoc, title):
    """Asks whether to do exterior-wall perimeter dimensioning at all, and if
    so, interactively prompts for which walls. Returns a set of
    element-id-token strings - empty if the user chose "just conventional
    dimensioning," pressed Escape while picking, or finished with nothing
    picked. Every one of those is a normal, expected outcome (every wall
    just gets the usual single-string treatment), never an error.
    """
    choice = show_category_picker(
        title,
        u"Also dimension exterior walls with the extra perimeter strings "
        u"(openings / perpendicular walls / overall), or just run the "
        u"normal single-string dimensioning for every wall?",
        [DIMENSION_EXTERIOR, SKIP_EXTERIOR])
    if choice != DIMENSION_EXTERIOR:
        return set()

    forms.alert(
        u"It's time to select the exterior walls.\n\n"
        u"Click each exterior wall in the view (Ctrl+click or drag a box for "
        u"more than one), then click Finish on the ribbon/status bar.\n\n"
        u"Press Escape instead to skip - every wall will just get the "
        u"normal single-string dimensioning.",
        title=title)

    try:
        picked_refs = uidoc.Selection.PickObjects(
            ObjectType.Element, _WallOnlyFilter(),
            u"{0}: click exterior walls, then Finish".format(title))
    except Exception:
        return set()

    return set(element_id_token(ref.ElementId) for ref in picked_refs)
