# -*- coding: utf-8 -*-
"""Runs the full Auto Tag flow: pick category -> pick view(s) -> pick a tag
type -> one Transaction per view tagging every untagged element of that
category. Placed right after Auto Mark in Documentation.panel's schedules
group - tagging what Auto Mark just numbered is the natural next step.

Reuses Auto Mark's own category set (mark_type_reader.CATEGORIES) so "Doors"/
"Windows"/etc mean exactly the same thing in both tools, and the existing
multi-view picker/batch-transaction helpers every dimensioning tool already
uses (view_selection_prompt.pick_target_views, multi_view_batch) instead of
building a new "pick the views" UI from scratch.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import Transaction

from bkbim.app.commands import auto_tag_command
from bkbim.revit.adapter.already_tagged_checker import RevitAlreadyTaggedChecker
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.mark_type_reader import CATEGORIES
from bkbim.revit.adapter.multi_view_batch import alert_batch_results, run_across_views
from bkbim.revit.adapter.tag_type_reader import list_tag_types, list_taggable_elements
from bkbim.revit.adapter.tag_writer import RevitTagWriter
from bkbim.revit.adapter.view_selection_prompt import pick_target_views
from bkbim.ui.views.auto_tag_options import show_auto_tag_options
from bkbim.ui.views.category_picker import show_category_picker
from bkbim.ui.views.result_dialog import show_result

_TRANSACTION_LABEL = u"Auto Tag"


def choose_category():
    """Shows the branded category picker. Returns one of
    mark_type_reader.CATEGORIES, or None if the user cancelled.
    """
    return show_category_picker(
        u"Auto Tag",
        u"Pick which category to tag.",
        CATEGORIES)


def run_auto_tag_flow(doc, view, category, title, target_views=None):
    """Runs the whole flow for one category. Shows its own alert(s); has no
    return value since the pushbutton entry point needs nothing further.
    """
    target_views = target_views or pick_target_views(doc, view, title)

    tag_types = list_tag_types(doc, category)
    if not tag_types:
        show_result(
            title,
            u"No {0} tag family is loaded in this project.".format(category.lower()))
        return

    options = show_auto_tag_options(tag_types, type_name)
    if options is None:
        return  # user cancelled

    results = run_across_views(
        doc, target_views, _TRANSACTION_LABEL,
        lambda v: _run_one_view(doc, v, category, options))
    alert_batch_results(results, title)


def _run_one_view(doc, v, category, options):
    elements = list_taggable_elements(doc, v, category, options.tag_type)
    if not elements:
        return v.Name, u"No {0} found in this view matching the chosen tag.".format(category.lower())

    writer = RevitTagWriter(doc, v, options.tag_type)
    already_tagged_checker = RevitAlreadyTaggedChecker(doc, v)

    t = Transaction(doc, u"{0} ({1})".format(_TRANSACTION_LABEL, v.Name))
    t.Start()
    try:
        result = auto_tag_command.run(elements, already_tagged_checker, writer)
    except Exception as e:
        t.RollBack()
        return v.Name, u"Error:\n{0}".format(str(e))

    if result.success:
        t.Commit()
    else:
        t.RollBack()
    return v.Name, result.message
