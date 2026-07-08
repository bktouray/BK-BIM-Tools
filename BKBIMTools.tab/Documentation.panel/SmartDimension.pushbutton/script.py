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

from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector, Grid, ViewDiscipline, ViewPlan, Wall
from pyrevit import forms

from bkbim.domain.standards.standard import default_standard
from bkbim.revit.adapter.grid_dimension_flow import run_grid_dimension_flow
from bkbim.revit.adapter.structural_dimension_flow import (
    CATEGORY_COLUMN,
    CATEGORY_SLAB,
    choose_category,
    run_structural_dimension_flow,
)
from bkbim.revit.adapter.view_selection_prompt import pick_target_views
from bkbim.revit.adapter.wall_dimension_flow import run_wall_dimension_flow
from bkbim.ui.views.category_picker import show_category_picker

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


def _run_walls(standard, target_views=None):
    run_wall_dimension_flow(doc, uidoc, view, standard, __title__, target_views=target_views)


def _run_grids(standard, target_views=None):
    run_grid_dimension_flow(doc, view, standard, __title__, target_views=target_views)


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
    """Working-drawing mode (2026-07-07): scans the view(s) for grids, walls,
    and columns, and runs each detected category's own flow in turn - grids
    ALWAYS run if any are present, walls always run if any are present.
    Columns are asked about (2026-07-07 follow-up: "for the autodetect
    option, i want an option to do or not do column dimensions") - only when
    columns are actually detected, since there's nothing to ask about
    otherwise. No beams/footings/slabs here - matches the literal ask
    ("walls and columns in the same view like a working drawing"); those
    stay reachable via Structural Elements/Slab Dimensions directly.

    Picks view(s) ONCE up front (2026-07-08 follow-up - product owner tried
    Auto-Detect expecting the same multi-view batching Walls/Grids/
    Structural already got, and got confused when it stayed single-view:
    "every dimension option i did like grids, columns and others let it do
    the same for every view") and threads that same list into every
    sub-flow, so grids/walls/columns all run across the same selected views
    without each sub-flow asking again.
    """
    target_views = pick_target_views(doc, view, u"Auto-Detect")

    grids_present = any(
        list(FilteredElementCollector(doc, v.Id).OfClass(Grid).ToElements())
        for v in target_views)
    walls_present = any(
        any(isinstance(w, Wall) for w in FilteredElementCollector(doc, v.Id).OfCategory(
            BuiltInCategory.OST_Walls).WhereElementIsNotElementType().ToElements())
        for v in target_views)
    has_columns = any(
        bool(list(FilteredElementCollector(doc, v.Id).OfCategory(
            BuiltInCategory.OST_StructuralColumns).WhereElementIsNotElementType().ToElements()))
        or bool(list(FilteredElementCollector(doc, v.Id).OfCategory(
            BuiltInCategory.OST_Columns).WhereElementIsNotElementType().ToElements()))
        for v in target_views)

    if not grids_present and not walls_present and not has_columns:
        forms.alert(u"No grids, walls, or columns found in the selected view(s).", title=__title__)
        return

    include_columns = False
    if has_columns:
        choice = show_category_picker(
            u"Auto-Detect",
            u"Columns were also detected. Include column dimensions in this run?",
            [INCLUDE_COLUMNS, SKIP_COLUMNS])
        if choice is None:
            return  # user cancelled the whole auto-detect run
        include_columns = (choice == INCLUDE_COLUMNS)

    if grids_present:
        _run_grids(standard, target_views=target_views)
    if walls_present:
        _run_walls(standard, target_views=target_views)
    if has_columns and include_columns:
        run_structural_dimension_flow(doc, view, standard, CATEGORY_COLUMN, __title__, target_views=target_views)


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
