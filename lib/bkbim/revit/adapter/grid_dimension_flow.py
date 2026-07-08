# -*- coding: utf-8 -*-
"""Runs the full Grid Dimensions flow (pick view(s) -> options window -> one
Transaction per view) - shared by AutoGridDimension.pushbutton and Smart
Dimension's Grid Dimensions path so both stay in sync (mirrors
wall_dimension_flow.py's shared-flow pattern, and fixes the near-duplicate
bodies those two scripts used to carry independently, including two
different literal Transaction names).

Multi-view batching (product owner, 2026-07-08: "every dimension option i
did like grids, columns and others let it do the same for every view...
put the select view option first") reuses ONE options window across every
selected view - same dimension style, offset, and gap applied identically
everywhere - then runs each view in its own Transaction inside one
TransactionGroup (via multi_view_batch.run_across_views), so the whole
batch undoes as a single step but one view's failure doesn't roll back the
others.

No manual/interactive picking anywhere in this flow (grids/walls/columns
are always auto-detected, never hand-picked), so - unlike walls - there is
no active-view-only constraint to work around; every view in a batch is
treated identically.

`target_views` is an optional pre-resolved override (skips the "pick
view(s)" prompt entirely), so SmartDimension's Auto-Detect mode can force
this flow to stay on the single current view instead of adding its own
"pick views?" prompt on top of Auto-Detect's own scan.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector, Grid, Transaction
from pyrevit import forms

from bkbim.app.commands import auto_grid_dimension_command
from bkbim.revit.adapter.dimension_type_reader import list_linear_dimension_types
from bkbim.revit.adapter.dimension_writer import DimensionWriter
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.existing_dimension_checker import RevitExistingDimensionChecker
from bkbim.revit.adapter.failure_policy import ScopedFailurePolicy
from bkbim.revit.adapter.multi_view_batch import alert_batch_results, run_across_views
from bkbim.revit.adapter.reference_provider import RevitReferenceProvider
from bkbim.revit.adapter.selection_reader import RevitSelectionReader
from bkbim.revit.adapter.view_selection_prompt import pick_target_views
from bkbim.ui.views.grid_dimension_options import show_grid_dimension_options

_TRANSACTION_LABEL = u"Auto Grid Dimension"


def _detected_elements(doc, view):
    """Auto-detects every grid, wall, and column visible in `view` - no user
    selection required (product owner feedback 2026-07-05: box-select was
    unwanted friction; grids should be found automatically).
    """
    grids = FilteredElementCollector(doc, view.Id).OfClass(Grid).ToElements()
    walls = FilteredElementCollector(doc, view.Id).OfCategory(
        BuiltInCategory.OST_Walls).WhereElementIsNotElementType().ToElements()
    structural_columns = FilteredElementCollector(doc, view.Id).OfCategory(
        BuiltInCategory.OST_StructuralColumns).WhereElementIsNotElementType().ToElements()
    architectural_columns = FilteredElementCollector(doc, view.Id).OfCategory(
        BuiltInCategory.OST_Columns).WhereElementIsNotElementType().ToElements()
    return list(grids) + list(walls) + list(structural_columns) + list(architectural_columns)


def run_grid_dimension_flow(doc, view, standard, title, target_views=None):
    """Runs collect -> pick view(s) -> options -> one Transaction per view ->
    one combined summary alert.
    """
    target_views = target_views or pick_target_views(doc, view, title)

    if not any(_detected_elements(doc, v) for v in target_views):
        forms.alert(u"No grids, walls, or columns found in the selected view(s).", title=title)
        return

    dimension_types = list_linear_dimension_types(doc)
    options = show_grid_dimension_options(
        dimension_types, type_name, standard.grid_chain_offset_mm, standard.grid_chain_gap_mm)
    if options is None:
        return  # user cancelled

    standard.grid_chain_offset_mm = options.offset_mm
    standard.grid_chain_gap_mm = options.gap_mm

    results = run_across_views(
        doc, target_views, _TRANSACTION_LABEL,
        lambda v: _run_one_view(doc, v, options, standard))
    alert_batch_results(results, title)


def _run_one_view(doc, v, options, standard):
    detected_elements = _detected_elements(doc, v)
    if not detected_elements:
        return v.Name, u"No grids, walls, or columns found in this view."

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
        result = auto_grid_dimension_command.run(
            detected_elements, selection_reader, existing_dimension_checker,
            writer, failure_tracker, standard)
    except Exception as e:
        t.RollBack()
        return v.Name, u"Error:\n{0}".format(str(e))

    if result.success:
        t.Commit()
    else:
        t.RollBack()
    return v.Name, result.message
