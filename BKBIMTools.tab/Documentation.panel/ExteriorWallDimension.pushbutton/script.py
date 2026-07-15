# -*- coding: utf-8 -*-
__title__ = u"Ext. Wall\nDimension"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Exterior Wall Dimension (3 strings).

Pick a dimension style and spacing, then click each exterior wall yourself
- always facing outward, no auto-detect. To dimension every wall in the
view instead, use Wall & Openings.
"""

from Autodesk.Revit.DB import Transaction, ViewPlan
from pyrevit import forms

from bkbim.app.commands import auto_wall_opening_dimension_command
from bkbim.core.tool_memory import recall, remember
from bkbim.domain.standards.standard import load_office_standard
from bkbim.revit.adapter.dimension_type_reader import list_linear_dimension_types
from bkbim.revit.adapter.dimension_writer import DimensionWriter
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.existing_dimension_checker import RevitExistingDimensionChecker
from bkbim.revit.adapter.failure_policy import ScopedFailurePolicy
from bkbim.revit.adapter.reference_provider import RevitReferenceProvider
from bkbim.revit.adapter.stable_representation import element_id_token
from bkbim.revit.adapter.wall_context_builder import build_walls_with_context
from bkbim.revit.adapter.wall_selection_prompt import pick_walls_manually
from bkbim.ui.views.exterior_wall_dimension_options import show_exterior_wall_dimension_options
from bkbim.ui.views.options_memory import to_remembered

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
view = doc.ActiveView


def main():
    if not isinstance(view, ViewPlan):
        forms.alert(u"Please open a plan view.", title=__title__)
        return

    standard = load_office_standard()
    dimension_types = list_linear_dimension_types(doc)

    default_offset_mm = recall(u"exterior_wall_dimension.offset_mm", default=standard.offset_first_mm, doc=doc)
    default_gap_mm = recall(u"exterior_wall_dimension.gap_mm", default=standard.wall_perimeter_gap_mm, doc=doc)
    default_style_name = recall(u"exterior_wall_dimension.dimension_type_name", doc=doc)

    options = show_exterior_wall_dimension_options(
        dimension_types, type_name, default_offset_mm, default_gap_mm,
        default_dimension_type_name=default_style_name)
    if options is None:
        return  # user cancelled

    standard.offset_first_mm = options.offset_mm
    standard.wall_perimeter_gap_mm = options.perimeter_gap_mm
    remember(u"exterior_wall_dimension.offset_mm", options.offset_mm, doc=doc)
    remember(u"exterior_wall_dimension.gap_mm", options.perimeter_gap_mm, doc=doc)
    if options.dimension_type is not None:
        remember(u"exterior_wall_dimension.dimension_type_name", to_remembered(
            options.dimension_type, type_name, lambda dt: element_id_token(dt.Id)), doc=doc)

    picked_walls = pick_walls_manually(uidoc, doc, __title__)
    if not picked_walls:
        return  # Escape / nothing picked - a normal outcome, not an error

    exterior_wall_ids = set(element_id_token(w.Id) for w in picked_walls)
    walls_with_context = build_walls_with_context(
        doc, view, picked_walls, exterior_wall_ids=exterior_wall_ids)
    if not walls_with_context:
        forms.alert(u"None of the selected walls are long enough to dimension.", title=__title__)
        return

    reference_provider = RevitReferenceProvider(doc, view)
    writer = DimensionWriter(doc, view, dimension_type=options.dimension_type)
    existing_dimension_checker = RevitExistingDimensionChecker(doc, view)
    failure_tracker = ScopedFailurePolicy()

    t = Transaction(doc, u"Exterior Wall Dimension")
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
