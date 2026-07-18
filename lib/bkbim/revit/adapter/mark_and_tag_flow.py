# -*- coding: utf-8 -*-
"""Runs Auto Mark immediately followed by Auto Tag for the same category -
the combined "Auto Mark & Tag" pushbutton (product owner, 2026-07-09: "this
combines the features of automark and autotag in one button"). Pure
orchestration - reuses both flows entirely unchanged (mark_flow.py,
tag_flow.py), so each step's own logic still lives in exactly one place;
this module owns none of it, just the sequencing.
"""

from bkbim.revit.adapter.mark_flow import run_auto_mark_flow
from bkbim.revit.adapter.mark_type_reader import CATEGORIES
from bkbim.revit.adapter.tag_flow import run_auto_tag_flow
from bkbim.ui.views.category_picker import show_category_picker
from bkbim.ui.views.result_dialog import show_result


def choose_category():
    """Shows the branded category picker. Returns one of
    mark_type_reader.CATEGORIES, or None if the user cancelled.
    """
    return show_category_picker(
        u"Auto Mark & Tag",
        u"Pick which category to mark and tag.",
        CATEGORIES)


def run_mark_and_tag_flow(doc, view, category, title):
    """Runs Auto Mark for `category` first (its own review/options window,
    doc-wide), then Auto Tag for the same category (its own view/tag-type
    prompts) - unless the user cancelled the Auto Mark step, or there was
    nothing of that category in the model at all (in which case there is
    nothing to tag either).
    """
    mark_result, mark_message = run_auto_mark_flow(doc, category, title)
    if mark_result is None and mark_message is None:
        return  # user cancelled the Auto Mark step

    if mark_message:
        show_result(title, mark_message)
    if mark_result is None:
        return  # nothing found for this category - nothing to tag either

    run_auto_tag_flow(doc, view, category, title)
