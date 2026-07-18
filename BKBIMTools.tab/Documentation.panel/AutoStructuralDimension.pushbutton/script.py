# -*- coding: utf-8 -*-
__title__ = u"Structural\nDimensions"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Auto Dimension for Structural Elements.

Pick a category (Column, Beam, Footing, or Slab), then a dimension style
and mode. Optionally apply the same settings across several views at once.
"""

from Autodesk.Revit.DB import ViewPlan

from bkbim.domain.standards.standard import load_office_standard
from bkbim.revit.adapter.structural_dimension_flow import choose_category, run_structural_dimension_flow
from bkbim.ui.views.result_dialog import show_result

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
view = doc.ActiveView


def main():
    if not isinstance(view, ViewPlan):
        show_result(__title__, u"Please open a plan view.")
        return

    category = choose_category()
    if category is None:
        return  # user cancelled

    standard = load_office_standard()
    run_structural_dimension_flow(doc, view, standard, category, __title__)


if __name__ == "__main__":
    main()
