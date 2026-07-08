# -*- coding: utf-8 -*-
"""Runs the full Structural Elements / Slab dimensioning flow (collect elements
for ONE category -> options window -> run command -> transaction) - shared by
AutoStructuralDimension.pushbutton and SmartDimension.pushbutton so both stay
in sync (2026-07-06: product owner found the mixed column/beam/footing type
list confusing - "I don't know what's what" - fixed by picking ONE category
first via `forms.CommandSwitchWindow`, so this flow only ever shows types from
that one category. Also folds in Slab Dimensions as a 4th category, per
product owner: "maybe even add the slab dimensions there").

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
(`_run_slab_outline` / `auto_slab_outline_dimension_command`) on 2026-07-07,
after a screenshot of a real notched/stepped footprint made clear the
bounding-box approximation was wrong for anything non-rectangular: "I want
dimensions to follow every slab face." It reads each slab's REAL boundary
edges (not just 4 bounding-box faces) and never needs grids at all, unlike
every other path through this flow - `_run_command`/
`auto_structural_dimension_command` stays exactly as-is for Column/Beam/
Footing and Slab's MODE_GRID_ONLY.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import FilteredElementCollector, Grid, Transaction
from pyrevit import forms

from bkbim.app.commands import auto_slab_outline_dimension_command, auto_structural_dimension_command
from bkbim.domain.dimensioning.column_grid_planner import MODE_OVERALL_ONLY
from bkbim.revit.adapter.dimension_type_reader import list_linear_dimension_types
from bkbim.revit.adapter.dimension_writer import DimensionWriter
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.existing_dimension_checker import RevitExistingDimensionChecker
from bkbim.revit.adapter.failure_policy import ScopedFailurePolicy
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
from bkbim.ui.views.category_picker import show_category_picker
from bkbim.ui.views.slab_dimension_options import show_slab_dimension_options
from bkbim.ui.views.structural_category_icons import structural_category_icon
from bkbim.ui.views.structural_dimension_options import show_structural_dimension_options

CATEGORY_SLAB = u"Slab"
CATEGORIES = [CATEGORY_COLUMN, CATEGORY_BEAM, CATEGORY_FOOTING, CATEGORY_SLAB]


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


def run_structural_dimension_flow(doc, view, standard, category, title):
    """Runs collect -> options -> command -> transaction for ONE category
    ('Column' | 'Beam' | 'Footing' | 'Slab').
    """
    if category == CATEGORY_SLAB:
        _run_slab(doc, view, standard, title)
    else:
        _run_category(doc, view, standard, category, title)


def _run_category(doc, view, standard, category, title):
    grids = list(FilteredElementCollector(doc, view.Id).OfClass(Grid).ToElements())
    elements = list_structural_elements_by_category(doc, view, category)
    if not elements:
        forms.alert(u"No {0} elements found in this view.".format(category.lower()), title=title)
        return
    if not grids:
        forms.alert(u"No grids found in this view.", title=title)
        return

    dimension_types = list_linear_dimension_types(doc)
    types_in_view = types_from_elements(elements)

    options = show_structural_dimension_options(
        dimension_types, types_in_view, type_name,
        standard.structural_chain_offset_mm, standard.structural_chain_gap_mm,
        category_label=category)
    if options is None:
        return  # user cancelled

    standard.structural_chain_offset_mm = options.offset_mm
    standard.offset_first_mm = options.offset_mm
    standard.structural_chain_gap_mm = options.gap_mm

    selected_type_keys = set(element_id_token(st.Id) for st in options.selected_types)
    dimensionable_elements = [
        e for e in elements if element_id_token(e.Symbol.Id) in selected_type_keys]
    if not dimensionable_elements:
        forms.alert(u"No elements match the selected type(s).", title=title)
        return

    detected_elements = grids + dimensionable_elements
    _run_command(doc, view, standard, detected_elements, options, title)


def _run_slab(doc, view, standard, title):
    slabs = list_slab_elements_in_view(doc, view)
    if not slabs:
        forms.alert(u"No slabs found in this view.", title=title)
        return

    dimension_types = list_linear_dimension_types(doc)
    slab_types = list_slab_types_in_view(doc, view)

    options = show_slab_dimension_options(
        dimension_types, slab_types, type_name, standard.structural_chain_offset_mm)
    if options is None:
        return  # user cancelled

    standard.structural_chain_offset_mm = options.offset_mm
    standard.offset_first_mm = options.offset_mm

    selected_type_keys = set(element_id_token(st.Id) for st in options.selected_types)
    dimensionable_slabs = [s for s in slabs if element_id_token(s.GetTypeId()) in selected_type_keys]
    if not dimensionable_slabs:
        forms.alert(u"No slabs match the selected type(s).", title=title)
        return

    if options.mode == MODE_OVERALL_ONLY:
        # "All edges of the slab" traces the REAL outline (product owner,
        # 2026-07-07, screenshot of a notched footprint: "I want dimensions
        # to follow every slab face") - a fundamentally different pipeline
        # from the grid-referenced mode below, since it needs every real
        # boundary edge, not just the bounding-box's 4 extreme faces, and
        # never needs grids at all.
        _run_slab_outline(doc, view, standard, dimensionable_slabs, options, title)
        return

    grids = list(FilteredElementCollector(doc, view.Id).OfClass(Grid).ToElements())
    if not grids:
        forms.alert(u"No grids found in this view.", title=title)
        return

    detected_elements = grids + dimensionable_slabs
    _run_command(doc, view, standard, detected_elements, options, title)


def _run_slab_outline(doc, view, standard, slabs, options, title):
    reference_provider = RevitReferenceProvider(doc, view)
    writer = DimensionWriter(doc, view, dimension_type=options.dimension_type)
    existing_dimension_checker = RevitExistingDimensionChecker(doc, view)
    failure_tracker = ScopedFailurePolicy()

    t = Transaction(doc, u"Auto Dimension Slab Outline")
    opts = t.GetFailureHandlingOptions()
    opts.SetFailuresPreprocessor(failure_tracker)
    t.SetFailureHandlingOptions(opts)
    t.Start()
    try:
        result = auto_slab_outline_dimension_command.run(
            slabs, reference_provider, existing_dimension_checker, writer, failure_tracker, standard)
    except Exception as e:
        t.RollBack()
        forms.alert(u"Error:\n{0}".format(str(e)), title=title)
        return

    if result.success:
        t.Commit()
    else:
        t.RollBack()
    forms.alert(result.message, title=title)


def _run_command(doc, view, standard, detected_elements, options, title):
    reference_provider = RevitReferenceProvider(doc, view)
    selection_reader = RevitSelectionReader(view, reference_provider)
    writer = DimensionWriter(doc, view, dimension_type=options.dimension_type)
    existing_dimension_checker = RevitExistingDimensionChecker(doc, view)
    failure_tracker = ScopedFailurePolicy()

    t = Transaction(doc, u"Auto Dimension Structural Elements")
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
        forms.alert(u"Error:\n{0}".format(str(e)), title=title)
        return

    if result.success:
        t.Commit()
    else:
        t.RollBack()
    forms.alert(result.message, title=title)
