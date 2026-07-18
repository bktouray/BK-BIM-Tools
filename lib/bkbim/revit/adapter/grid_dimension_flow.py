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

from bkbim.app.commands import auto_grid_dimension_command
from bkbim.core.tool_memory import recall, remember
from bkbim.revit.adapter.dimension_type_reader import list_linear_dimension_types
from bkbim.revit.adapter.dimension_writer import DimensionWriter
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.existing_dimension_checker import RevitExistingDimensionChecker
from bkbim.revit.adapter.failure_policy import ScopedFailurePolicy
from bkbim.revit.adapter.multi_view_batch import alert_batch_results, run_across_views
from bkbim.revit.adapter.reference_provider import RevitReferenceProvider
from bkbim.revit.adapter.selection_reader import RevitSelectionReader
from bkbim.revit.adapter.stable_representation import element_id_token
from bkbim.revit.adapter.view_selection_prompt import pick_target_views
from bkbim.ui.views.grid_dimension_options import show_grid_dimension_options
from bkbim.ui.views.options_memory import to_remembered
from bkbim.ui.views.result_dialog import show_result

_TRANSACTION_LABEL = u"Auto Grid Dimension"
_OFFSET_KEY = u"grid_dimension.offset_mm"
_GAP_KEY = u"grid_dimension.gap_mm"
_STYLE_KEY = u"grid_dimension.dimension_type_name"


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
        show_result(title, u"No grids, walls, or columns found in the selected view(s).")
        return

    # Tool Memory (PROJECT layer - a chosen offset/gap is a project habit):
    # last run's actual values win over the Office Standard default, which
    # only applies the very first time this tool runs on a given project.
    default_offset_mm = recall(_OFFSET_KEY, default=standard.grid_chain_offset_mm, doc=doc)
    default_gap_mm = recall(_GAP_KEY, default=standard.grid_chain_gap_mm, doc=doc)

    default_style_name = recall(_STYLE_KEY, doc=doc)

    dimension_types = list_linear_dimension_types(doc)
    options = show_grid_dimension_options(
        dimension_types, type_name, default_offset_mm, default_gap_mm,
        default_dimension_type_name=default_style_name)
    if options is None:
        return  # user cancelled

    standard.grid_chain_offset_mm = options.offset_mm
    standard.grid_chain_gap_mm = options.gap_mm
    remember(_OFFSET_KEY, options.offset_mm, doc=doc)
    remember(_GAP_KEY, options.gap_mm, doc=doc)
    if options.dimension_type is not None:
        remember(_STYLE_KEY, to_remembered(
            options.dimension_type, type_name, lambda dt: element_id_token(dt.Id)), doc=doc)

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
