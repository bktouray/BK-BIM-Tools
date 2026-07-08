# -*- coding: utf-8 -*-
"""Prompts for which view(s) to run a dimensioning flow on - lets the same
dimension style/settings apply across several views of a similar drawing in
one run (product owner, 2026-07-08: "I sometimes have different views with a
similar drawing, I want an option where I can select the views I want to
apply similar dimension styles").
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import FilteredElementCollector, ViewPlan
from pyrevit import forms

from bkbim.ui.views.category_picker import show_category_picker

JUST_THIS_VIEW = u"Just this view"
MULTIPLE_VIEWS = u"Apply to multiple views"


def pick_target_views(doc, current_view, title):
    """Returns a non-empty list[View] to run the flow on. Defaults to
    [current_view] if the user picks "just this view," cancels, or the
    multi-select comes back empty - running on the current view only is
    always a safe, expected outcome, never an error.
    """
    choice = show_category_picker(
        title,
        u"Run this on just the current view, or apply the same settings "
        u"across multiple views?",
        [JUST_THIS_VIEW, MULTIPLE_VIEWS])
    if choice != MULTIPLE_VIEWS:
        return [current_view]

    candidate_views = [
        v for v in FilteredElementCollector(doc).OfClass(ViewPlan).ToElements()
        if not v.IsTemplate]

    name_map = {}
    for v in candidate_views:
        label = u"{0}  [{1}]".format(v.Name, v.ViewType)
        if v.Id == current_view.Id:
            label += u" (current)"
        name_map[label] = v

    picked_names = forms.SelectFromList.show(
        sorted(name_map.keys()),
        title=u"Pick the views to run \"{0}\" on".format(title),
        multiselect=True)
    if not picked_names:
        return [current_view]

    return [name_map[name] for name in picked_names]
