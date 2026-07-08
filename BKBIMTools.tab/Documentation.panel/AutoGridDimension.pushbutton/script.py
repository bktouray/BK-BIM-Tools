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
string on all sides. Optionally apply the same settings across several
views at once - pick a style and spacing, then Run.
"""

from Autodesk.Revit.DB import ViewPlan
from pyrevit import forms

from bkbim.domain.standards.standard import default_standard
from bkbim.revit.adapter.grid_dimension_flow import run_grid_dimension_flow

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
view = doc.ActiveView


def main():
    if not isinstance(view, ViewPlan):
        forms.alert(u"Please open a plan view.", title=__title__)
        return

    standard = default_standard()
    run_grid_dimension_flow(doc, view, standard, __title__)


if __name__ == "__main__":
    main()
