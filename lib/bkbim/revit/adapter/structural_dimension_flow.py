# -*- coding: utf-8 -*-
"""Runs the full Structural Elements / Slab dimensioning flow (pick view(s)
-> collect elements for ONE category across them -> options window -> one
Transaction per view) - shared by AutoStructuralDimension.pushbutton and
SmartDimension.pushbutton so both stay in sync (2026-07-06: product owner
found the mixed column/beam/footing type list confusing - "I don't know
what's what" - fixed by picking ONE category first via
`forms.CommandSwitchWindow`, so this flow only ever shows types from that
one category. Also folds in Slab Dimensions as a 4th category, per product
owner: "maybe even add the slab dimensions there").

Slab is the one category that does NOT reuse `show_structural_dimension_options`
- it has its own MODE_GRID_ONLY/MODE_OVERALL_ONLY two-mode window
(`slab_dimension_options.py`), added 2026-07-06 when the product owner asked
for "two options, one from grid to slab edges, and another measuring all edges
of the slab" instead of the bundled detail+overall MODE_GRID_AND_COLUMN that
Column/Beam/Footing use. Reaching Slab only through this flow (and Smart
Dimension) is deliberate too - the standalone SlabDimension.pushbutton was
removed the same day as redundant ("having its own pushbutton is seems
useless" once it's already one click inside Structural Element Dimensions).

MODE_OVERALL_ONLY ("All edges of the slab") got its own SEPARATE pipeline
(`_run_slab_outline_one_view` / `auto_slab_outline_dimension_command`) on
2026-07-07, after a screenshot of a real notched/stepped footprint made
clear the bounding-box approximation was wrong for anything non-rectangular:
"I want dimensions to follow every slab face." It reads each slab's REAL
boundary edges (not just 4 bounding-box faces) and never needs grids at
all, unlike every other path through this flow - `_run_command_one_view`/
`auto_structural_dimension_command` stays exactly as-is for Column/Beam/
Footing and Slab's MODE_GRID_ONLY.

Multi-view batching (product owner, 2026-07-08: "every dimension option i
did like grids, columns and others let it do the same for every view...
put the select view option first") reuses ONE options window (and, for
Column/Beam/Footing/Slab-grid-mode, ONE unioned type list) across every
selected view, then runs each view through multi_view_batch.run_across_views
- same shared TransactionGroup/per-view-Transaction/combined-alert shape
`wall_dimension_flow.py` and `grid_dimension_flow.py` already use. No
interactive/manual picking exists anywhere in this flow (category/type
selection is always checkboxes, never PickObjects), so - unlike walls -
there's no active-view-only constraint to work around.

`target_views` is an optional pre-resolved override (skips the "pick
view(s)" prompt entirely), so SmartDimension's Auto-Detect mode can force
the Column path to stay on the single current view instead of adding its
own "pick views?" prompt on top of Auto-Detect's own scan.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import FilteredElementCollector, Grid, Transaction
from pyrevit import forms

from bkbim.app.commands import auto_slab_outline_dimension_command, auto_structural_dimension_command
from bkbim.core.tool_memory import recall, remember
from bkbim.domain.dimensioning.column_grid_planner import MODE_OVERALL_ONLY
from bkbim.revit.adapter.dimension_type_reader import list_linear_dimension_types
from bkbim.revit.adapter.dimension_writer import DimensionWriter
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.existing_dimension_checker import RevitExistingDimensionChecker
from bkbim.revit.adapter.failure_policy import ScopedFailurePolicy
from bkbim.revit.adapter.multi_view_batch import alert_batch_results, run_across_views
from bkbim.revit.adapter.reference_provider import RevitReferenceProvider
from bkbim.revit.adapter.selection_reader import RevitSelectionReader
from bkbim.revit.adapter.slab_type_reader import list_slab_elements_in_view, list_slab_types_in_view
from bkbim.revit.adapter.stable_representation import element_id_token
from bkbim.revit.adapter.structural_type_reader import (
    CATEGORY_BEAM,
    CATEGORY_COLUMN,
    CATEGORY_FOOTING,
    list_structural_elements_by_category,
    types_from_elements,
)
from bkbim.revit.adapter.view_selection_prompt import pick_target_views
from bkbim.ui.views.category_picker import show_category_picker
from bkbim.ui.views.options_memory import to_remembered
from bkbim.ui.views.slab_dimension_options import show_slab_dimension_options
from bkbim.ui.views.structural_category_icons import structural_category_icon
from bkbim.ui.views.structural_dimension_options import show_structural_dimension_options

CATEGORY_SLAB = u"Slab"
CATEGORIES = [CATEGORY_COLUMN, CATEGORY_BEAM, CATEGORY_FOOTING, CATEGORY_SLAB]

_TRANSACTION_LABEL = u"Auto Dimension Structural Elements"
_SLAB_OUTLINE_TRANSACTION_LABEL = u"Auto Dimension Slab Outline"


def _offset_key(category):
    # Per-category (Column/Beam/Footing/Slab preferences are independent -
    # tuning one shouldn't silently change what the others remember).
    return u"structural_dimension.{0}.offset_mm".format(category.lower())


def _gap_key(category):
    return u"structural_dimension.{0}.gap_mm".format(category.lower())


def _style_key(category):
    return u"structural_dimension.{0}.dimension_type_name".format(category.lower())


def _types_key(category):
    return u"structural_dimension.{0}.selected_type_names".format(category.lower())


def choose_category():
    """Shows the branded category picker (product owner, 2026-07-06: "I don't
    like the default pyRevit interface... make it nice"; 2026-07-07: "add
    small icons to this page"). Returns one of CATEGORIES, or None if the
    user cancelled.
    """
    return show_category_picker(
        u"Structural Element Dimensions",
        u"Pick which category to dimension - the options that follow are "
        u"tailored to whichever you choose.",
        CATEGORIES,
        icon_factory=structural_category_icon)


def run_structural_dimension_flow(doc, view, standard, category, title, target_views=None):
    """Runs pick view(s) -> collect -> options -> transaction(s) for ONE
    category ('Column' | 'Beam' | 'Footing' | 'Slab').
    """
    target_views = target_views or pick_target_views(doc, view, title)
    if category == CATEGORY_SLAB:
        _run_slab(doc, target_views, standard, title)
    else:
        _run_category(doc, target_views, standard, category, title)


def _run_category(doc, target_views, standard, category, title):
    combined_types = {}
    any_elements = False
    any_grids = False
    for v in target_views:
        elements = list_structural_elements_by_category(doc, v, category)
        if elements:
            any_elements = True
        for st in types_from_elements(elements):
            combined_types.setdefault(element_id_token(st.Id), st)
        if list(FilteredElementCollector(doc, v.Id).OfClass(Grid).ToElements()):
            any_grids = True

    if not any_elements:
        forms.alert(u"No {0} elements found in the selected view(s).".format(category.lower()), title=title)
        return
    if not any_grids:
        forms.alert(u"No grids found in the selected view(s).", title=title)
        return

    default_offset_mm = recall(_offset_key(category), default=standard.structural_chain_offset_mm, doc=doc)
    default_gap_mm = recall(_gap_key(category), default=standard.structural_chain_gap_mm, doc=doc)
    default_style_name = recall(_style_key(category), doc=doc)
    default_type_names = recall(_types_key(category), doc=doc)

    dimension_types = list_linear_dimension_types(doc)
    options = show_structural_dimension_options(
        dimension_types, list(combined_types.values()), type_name,
        default_offset_mm, default_gap_mm, category_label=category,
        default_dimension_type_name=default_style_name,
        default_selected_type_names=default_type_names)
    if options is None:
        return  # user cancelled

    standard.structural_chain_offset_mm = options.offset_mm
    standard.offset_first_mm = options.offset_mm
    standard.structural_chain_gap_mm = options.gap_mm
    remember(_offset_key(category), options.offset_mm, doc=doc)
    remember(_gap_key(category), options.gap_mm, doc=doc)
    if options.dimension_type is not None:
        remember(_style_key(category), to_remembered(
            options.dimension_type, type_name, lambda dt: element_id_token(dt.Id)), doc=doc)
    remember(_types_key(category), [
        to_remembered(st, type_name, lambda t: element_id_token(t.Id)) for st in options.selected_types], doc=doc)
    selected_type_keys = set(element_id_token(st.Id) for st in options.selected_types)

    results = run_across_views(
        doc, target_views, _TRANSACTION_LABEL,
        lambda v: _run_category_one_view(doc, v, standard, category, selected_type_keys, options))
    alert_batch_results(results, title)


def _run_category_one_view(doc, v, standard, category, selected_type_keys, options):
    grids = list(FilteredElementCollector(doc, v.Id).OfClass(Grid).ToElements())
    if not grids:
        return v.Name, u"No grids found in this view."

    elements = list_structural_elements_by_category(doc, v, category)
    dimensionable_elements = [e for e in elements if element_id_token(e.Symbol.Id) in selected_type_keys]
    if not dimensionable_elements:
        return v.Name, u"No elements match the selected type(s)."

    detected_elements = grids + dimensionable_elements
    return _run_command_one_view(doc, v, standard, detected_elements, options)


def _run_slab(doc, target_views, standard, title):
    combined_types = {}
    any_slabs = False
    for v in target_views:
        slabs = list_slab_elements_in_view(doc, v)
        if slabs:
            any_slabs = True
        for st in list_slab_types_in_view(doc, v):
            combined_types.setdefault(element_id_token(st.Id), st)

    if not any_slabs:
        forms.alert(u"No slabs found in the selected view(s).", title=title)
        return

    default_offset_mm = recall(_offset_key(CATEGORY_SLAB), default=standard.structural_chain_offset_mm, doc=doc)
    default_style_name = recall(_style_key(CATEGORY_SLAB), doc=doc)
    default_type_names = recall(_types_key(CATEGORY_SLAB), doc=doc)

    dimension_types = list_linear_dimension_types(doc)
    options = show_slab_dimension_options(
        dimension_types, list(combined_types.values()), type_name, default_offset_mm,
        default_dimension_type_name=default_style_name,
        default_selected_type_names=default_type_names)
    if options is None:
        return  # user cancelled

    standard.structural_chain_offset_mm = options.offset_mm
    standard.offset_first_mm = options.offset_mm
    remember(_offset_key(CATEGORY_SLAB), options.offset_mm, doc=doc)
    if options.dimension_type is not None:
        remember(_style_key(CATEGORY_SLAB), to_remembered(
            options.dimension_type, type_name, lambda dt: element_id_token(dt.Id)), doc=doc)
    remember(_types_key(CATEGORY_SLAB), [
        to_remembered(st, type_name, lambda t: element_id_token(t.Id)) for st in options.selected_types], doc=doc)
    selected_type_keys = set(element_id_token(st.Id) for st in options.selected_types)

    if options.mode == MODE_OVERALL_ONLY:
        # "All edges of the slab" traces the REAL outline (product owner,
        # 2026-07-07, screenshot of a notched footprint: "I want dimensions
        # to follow every slab face") - a fundamentally different pipeline
        # from the grid-referenced mode below, since it needs every real
        # boundary edge, not just the bounding-box's 4 extreme faces, and
        # never needs grids at all.
        results = run_across_views(
            doc, target_views, _SLAB_OUTLINE_TRANSACTION_LABEL,
            lambda v: _run_slab_outline_one_view(doc, v, standard, selected_type_keys, options))
    else:
        results = run_across_views(
            doc, target_views, _TRANSACTION_LABEL,
            lambda v: _run_slab_grid_one_view(doc, v, standard, selected_type_keys, options))

    alert_batch_results(results, title)


def _run_slab_outline_one_view(doc, v, standard, selected_type_keys, options):
    slabs = list_slab_elements_in_view(doc, v)
    dimensionable_slabs = [s for s in slabs if element_id_token(s.GetTypeId()) in selected_type_keys]
    if not dimensionable_slabs:
        return v.Name, u"No slabs match the selected type(s)."

    reference_provider = RevitReferenceProvider(doc, v)
    writer = DimensionWriter(doc, v, dimension_type=options.dimension_type)
    existing_dimension_checker = RevitExistingDimensionChecker(doc, v)
    failure_tracker = ScopedFailurePolicy()

    t = Transaction(doc, u"{0} ({1})".format(_SLAB_OUTLINE_TRANSACTION_LABEL, v.Name))
    opts = t.GetFailureHandlingOptions()
    opts.SetFailuresPreprocessor(failure_tracker)
    t.SetFailureHandlingOptions(opts)
    t.Start()
    try:
        result = auto_slab_outline_dimension_command.run(
            dimensionable_slabs, reference_provider, existing_dimension_checker, writer, failure_tracker, standard)
    except Exception as e:
        t.RollBack()
        return v.Name, u"Error:\n{0}".format(str(e))

    if result.success:
        t.Commit()
    else:
        t.RollBack()
    return v.Name, result.message


def _run_slab_grid_one_view(doc, v, standard, selected_type_keys, options):
    grids = list(FilteredElementCollector(doc, v.Id).OfClass(Grid).ToElements())
    if not grids:
        return v.Name, u"No grids found in this view."

    slabs = list_slab_elements_in_view(doc, v)
    dimensionable_slabs = [s for s in slabs if element_id_token(s.GetTypeId()) in selected_type_keys]
    if not dimensionable_slabs:
        return v.Name, u"No slabs match the selected type(s)."

    detected_elements = grids + dimensionable_slabs
    return _run_command_one_view(doc, v, standard, detected_elements, options)


def _run_command_one_view(doc, v, standard, detected_elements, options):
    reference_provider = RevitReferenceProvider(doc, v)
    selection_reader = RevitSelectionReader(v, reference_provider)
    writer = DimensionWriter(doc, v, dimension_type=options.dimension_type)
    existing_dimension_checker = RevitExistingDimensionChecker(doc, v)
    failure_tracker = ScopedFailurePolicy()

    t = Transaction(doc, u"{0} ({1})".format(_TRANSACTION_LABEL, v.Name))
    opts = t.GetFailureHandlingOptions()
    opts.SetFailuresPreprocessor(failure_tracker)
    t.SetFailureHandlingOptions(opts)
    t.Start()
    try:
        result = auto_structural_dimension_command.run(
            detected_elements, selection_reader, reference_provider,
            existing_dimension_checker, writer, failure_tracker, options.mode, standard)
    except Exception as e:
        t.RollBack()
        return v.Name, u"Error:\n{0}".format(str(e))

    if result.success:
        t.Commit()
    else:
        t.RollBack()
    return v.Name, result.message
