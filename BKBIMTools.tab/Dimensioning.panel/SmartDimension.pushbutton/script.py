# -*- coding: utf-8 -*-
__title__ = u"Smart\nDimension"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""One entry point for every dimensioning tool.

Pick Auto-Detect for a mixed working-drawing view (grids, walls, columns
all dimensioned in one pass), or pick a specific tool directly: Walls &
Openings, Grid Dimensions, Structural Elements, or Slab Dimensions.
"""

from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector, Grid, Transaction, ViewDiscipline, ViewPlan, Wall
from pyrevit import forms

from bkbim.app.commands import auto_grid_dimension_command, auto_wall_opening_dimension_command
from bkbim.domain.standards.standard import default_standard
from bkbim.revit.adapter.dimension_type_reader import list_linear_dimension_types
from bkbim.revit.adapter.dimension_writer import DimensionWriter
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.existing_dimension_checker import RevitExistingDimensionChecker
from bkbim.revit.adapter.failure_policy import ScopedFailurePolicy
from bkbim.revit.adapter.reference_provider import RevitReferenceProvider
from bkbim.revit.adapter.selection_reader import RevitSelectionReader
from bkbim.revit.adapter.stable_representation import element_id_token
from bkbim.revit.adapter.structural_dimension_flow import (
    CATEGORY_COLUMN,
    CATEGORY_SLAB,
    choose_category,
    run_structural_dimension_flow,
)
from bkbim.revit.adapter.wall_context_builder import build_walls_with_context
from bkbim.revit.adapter.wall_selection_prompt import pick_exterior_walls
from bkbim.revit.adapter.wall_type_reader import list_wall_types_in_view
from bkbim.ui.views.category_picker import show_category_picker
from bkbim.ui.views.grid_dimension_options import show_grid_dimension_options
from bkbim.ui.views.wall_opening_dimension_options import show_wall_opening_dimension_options

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
view = doc.ActiveView

AUTO_DETECT = u"Auto-Detect (working drawing: grids + walls + columns)"
WALLS = u"Walls & Openings"
GRIDS = u"Grid Dimensions"
STRUCTURAL = u"Structural Elements (columns/footings/beams)"
SLABS = u"Slab Dimensions"

# Add a new dimensioning tool here (and a matching _run_<x>() function below)
# to make it show up in Smart Dimension too - no other wiring needed.
CHOICES = [AUTO_DETECT, WALLS, GRIDS, STRUCTURAL, SLABS]


def _run_walls(standard):
    raw_walls = FilteredElementCollector(doc, view.Id).OfCategory(
        BuiltInCategory.OST_Walls).WhereElementIsNotElementType().ToElements()
    walls = [w for w in raw_walls if isinstance(w, Wall)]
    if not walls:
        forms.alert(u"No walls found in this view.", title=__title__)
        return

    dimension_types = list_linear_dimension_types(doc)
    wall_types = list_wall_types_in_view(doc, view)

    options = show_wall_opening_dimension_options(
        dimension_types, wall_types, type_name, standard.offset_first_mm, standard.wall_perimeter_gap_mm)
    if options is None:
        return  # user cancelled

    standard.offset_first_mm = options.offset_mm
    standard.wall_perimeter_gap_mm = options.perimeter_gap_mm

    selected_type_keys = set(element_id_token(wt.Id) for wt in options.selected_wall_types)
    dimensionable_walls = [w for w in walls if element_id_token(w.WallType.Id) in selected_type_keys]
    if not dimensionable_walls:
        forms.alert(u"No walls match the selected wall type(s).", title=__title__)
        return

    # Prompted AFTER the options window closes (2026-07-07 follow-up: "make
    # it after I select the autodimension walls and openings and after I
    # select dimension styles and other stuff, prompt me to select exterior
    # walls") - picking nothing (Esc) is a normal outcome, not an error.
    exterior_wall_ids = pick_exterior_walls(uidoc, __title__)

    walls_with_context = build_walls_with_context(
        doc, view, dimensionable_walls, exterior_wall_ids=exterior_wall_ids)
    if not walls_with_context:
        forms.alert(u"No dimensionable walls found in this view.", title=__title__)
        return

    reference_provider = RevitReferenceProvider(doc, view)
    writer = DimensionWriter(doc, view, dimension_type=options.dimension_type)
    existing_dimension_checker = RevitExistingDimensionChecker(doc, view)
    failure_tracker = ScopedFailurePolicy()

    t = Transaction(doc, u"Smart Dimension (Walls & Openings)")
    opts = t.GetFailureHandlingOptions()
    opts.SetFailuresPreprocessor(failure_tracker)
    t.SetFailureHandlingOptions(opts)
    t.Start()
    try:
        result = auto_wall_opening_dimension_command.run(
            walls_with_context, reference_provider, reference_provider,
            existing_dimension_checker, writer, failure_tracker, standard)
    except Exception as e:
        t.RollBack()
        forms.alert(u"Error:\n{0}".format(str(e)), title=__title__)
        return

    if result.success:
        t.Commit()
    else:
        t.RollBack()
    forms.alert(result.message, title=__title__)


def _run_grids(standard):
    grids = FilteredElementCollector(doc, view.Id).OfClass(Grid).ToElements()
    raw_walls = FilteredElementCollector(doc, view.Id).OfCategory(
        BuiltInCategory.OST_Walls).WhereElementIsNotElementType().ToElements()
    structural_columns = FilteredElementCollector(doc, view.Id).OfCategory(
        BuiltInCategory.OST_StructuralColumns).WhereElementIsNotElementType().ToElements()
    architectural_columns = FilteredElementCollector(doc, view.Id).OfCategory(
        BuiltInCategory.OST_Columns).WhereElementIsNotElementType().ToElements()
    detected_elements = list(grids) + list(raw_walls) + list(structural_columns) + list(architectural_columns)
    if not detected_elements:
        forms.alert(u"No grids, walls, or columns found in this view.", title=__title__)
        return

    dimension_types = list_linear_dimension_types(doc)

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

    t = Transaction(doc, u"Smart Dimension (Grid Dimensions)")
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


def _run_structural(standard):
    category = choose_category()
    if category is None:
        return  # user cancelled
    run_structural_dimension_flow(doc, view, standard, category, __title__)


def _run_slabs(standard):
    run_structural_dimension_flow(doc, view, standard, CATEGORY_SLAB, __title__)


INCLUDE_COLUMNS = u"Yes, include columns"
SKIP_COLUMNS = u"No, skip columns"


def _run_auto_detect(standard):
    """Working-drawing mode (2026-07-07): scans the view for grids, walls,
    and columns, and runs each detected category's own flow in turn - grids
    ALWAYS run if any are present, walls always run if any are present.
    Columns are asked about (2026-07-07 follow-up: "for the autodetect
    option, i want an option to do or not do column dimensions") - only when
    columns are actually detected, since there's nothing to ask about
    otherwise. No beams/footings/slabs here - matches the literal ask
    ("walls and columns in the same view like a working drawing"); those
    stay reachable via Structural Elements/Slab Dimensions directly.
    """
    grids = list(FilteredElementCollector(doc, view.Id).OfClass(Grid).ToElements())
    raw_walls = FilteredElementCollector(doc, view.Id).OfCategory(
        BuiltInCategory.OST_Walls).WhereElementIsNotElementType().ToElements()
    walls = [w for w in raw_walls if isinstance(w, Wall)]
    structural_columns = FilteredElementCollector(doc, view.Id).OfCategory(
        BuiltInCategory.OST_StructuralColumns).WhereElementIsNotElementType().ToElements()
    architectural_columns = FilteredElementCollector(doc, view.Id).OfCategory(
        BuiltInCategory.OST_Columns).WhereElementIsNotElementType().ToElements()
    has_columns = bool(list(structural_columns)) or bool(list(architectural_columns))

    if not grids and not walls and not has_columns:
        forms.alert(u"No grids, walls, or columns found in this view.", title=__title__)
        return

    include_columns = False
    if has_columns:
        choice = show_category_picker(
            u"Auto-Detect",
            u"Columns were also detected in this view. Include column dimensions in this run?",
            [INCLUDE_COLUMNS, SKIP_COLUMNS])
        if choice is None:
            return  # user cancelled the whole auto-detect run
        include_columns = (choice == INCLUDE_COLUMNS)

    if grids:
        _run_grids(standard)
    if walls:
        _run_walls(standard)
    if has_columns and include_columns:
        run_structural_dimension_flow(doc, view, standard, CATEGORY_COLUMN, __title__)


_RUNNERS = {
    AUTO_DETECT: _run_auto_detect,
    WALLS: _run_walls,
    GRIDS: _run_grids,
    STRUCTURAL: _run_structural,
    SLABS: _run_slabs,
}


def main():
    if not isinstance(view, ViewPlan):
        forms.alert(u"Please open a plan view.", title=__title__)
        return

    discipline_hint = u"Structural" if view.Discipline == ViewDiscipline.Structural else u"Architectural"
    choice = show_category_picker(
        u"Smart Dimension",
        u"Detected: {0} plan. Pick what to dimension.".format(discipline_hint),
        CHOICES)
    if choice is None:
        return  # user cancelled

    standard = default_standard()
    _RUNNERS[choice](standard)


if __name__ == "__main__":
    main()
