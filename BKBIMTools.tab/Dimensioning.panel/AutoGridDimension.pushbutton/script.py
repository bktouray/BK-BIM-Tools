# -*- coding: utf-8 -*-
__title__ = u"Grid\nDimensions"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Auto Grid Dimension.

Dimensions every grid in the view with a grid-to-grid string and an overall
string on all sides. Pick a style and spacing, then Run.
"""

from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector, Grid, Transaction, ViewPlan
from pyrevit import forms

from bkbim.app.commands import auto_grid_dimension_command
from bkbim.domain.standards.standard import default_standard
from bkbim.revit.adapter.dimension_type_reader import list_linear_dimension_types
from bkbim.revit.adapter.dimension_writer import DimensionWriter
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.existing_dimension_checker import RevitExistingDimensionChecker
from bkbim.revit.adapter.failure_policy import ScopedFailurePolicy
from bkbim.revit.adapter.reference_provider import RevitReferenceProvider
from bkbim.revit.adapter.selection_reader import RevitSelectionReader
from bkbim.ui.views.grid_dimension_options import show_grid_dimension_options

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
view = doc.ActiveView


def _collect_dimensionable_elements(doc, view):
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


def main():
    if not isinstance(view, ViewPlan):
        forms.alert(u"Please open a plan view.", title=__title__)
        return

    detected_elements = _collect_dimensionable_elements(doc, view)
    if not detected_elements:
        forms.alert(u"No grids, walls, or columns found in this view.", title=__title__)
        return

    dimension_types = list_linear_dimension_types(doc)
    standard = default_standard()

    options = show_grid_dimension_options(
        dimension_types, type_name, standard.grid_chain_offset_mm, standard.grid_chain_gap_mm)
    if options is None:
        return  # user cancelled

    standard.grid_chain_offset_mm = options.offset_mm
    standard.grid_chain_gap_mm = options.gap_mm

    reference_provider = RevitReferenceProvider(doc, view)
    selection_reader = RevitSelectionReader(view, reference_provider)
    writer = DimensionWriter(doc, view, dimension_type=options.dimension_type)
    existing_dimension_checker = RevitExistingDimensionChecker(doc, view)
    failure_tracker = ScopedFailurePolicy()

    t = Transaction(doc, u"Auto Grid Dimension")
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
        forms.alert(u"Error:\n{0}".format(str(e)), title=__title__)
        return

    if result.success:
        t.Commit()
    else:
        t.RollBack()
    forms.alert(result.message, title=__title__)


if __name__ == "__main__":
    main()
