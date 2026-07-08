# -*- coding: utf-8 -*-
__title__ = u"Wall &\nOpenings"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Auto Dimension for Walls and Openings.

Dimensions every wall in the view, broken at each door/window and every
crossing wall. Optionally add exterior-perimeter dimensioning (3 strings
per wall, always facing outward) - you'll be asked after Run.
"""

from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector, Transaction, ViewPlan, Wall
from pyrevit import forms

from bkbim.app.commands import auto_wall_opening_dimension_command
from bkbim.domain.standards.standard import default_standard
from bkbim.revit.adapter.dimension_type_reader import list_linear_dimension_types
from bkbim.revit.adapter.dimension_writer import DimensionWriter
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.existing_dimension_checker import RevitExistingDimensionChecker
from bkbim.revit.adapter.failure_policy import ScopedFailurePolicy
from bkbim.revit.adapter.reference_provider import RevitReferenceProvider
from bkbim.revit.adapter.stable_representation import element_id_token
from bkbim.revit.adapter.wall_context_builder import build_walls_with_context
from bkbim.revit.adapter.wall_selection_prompt import pick_exterior_walls
from bkbim.revit.adapter.wall_type_reader import list_wall_types_in_view
from bkbim.ui.views.wall_opening_dimension_options import show_wall_opening_dimension_options

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
view = doc.ActiveView


def main():
    if not isinstance(view, ViewPlan):
        forms.alert(u"Please open a plan view.", title=__title__)
        return

    raw_walls = FilteredElementCollector(doc, view.Id).OfCategory(
        BuiltInCategory.OST_Walls).WhereElementIsNotElementType().ToElements()
    # OST_Walls can include non-Wall elements (confirmed live 2026-07-05: a
    # FamilyInstance, likely a curtain wall panel) - only real Walls are dimensioned.
    walls = [w for w in raw_walls if isinstance(w, Wall)]
    if not walls:
        forms.alert(u"No walls found in this view.", title=__title__)
        return

    dimension_types = list_linear_dimension_types(doc)
    wall_types = list_wall_types_in_view(doc, view)
    standard = default_standard()

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

    t = Transaction(doc, u"Auto Dimension Walls & Openings")
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


if __name__ == "__main__":
    main()
