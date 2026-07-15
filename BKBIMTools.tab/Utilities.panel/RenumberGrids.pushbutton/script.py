# -*- coding: utf-8 -*-
__title__ = u"Renumber\nGrids"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Renumbers every grid in the model. Vertical grids get letters
(A, B, C... AA, AB...) left to right; horizontal grids get numbers (1, 2,
3...) top to bottom.
"""

from Autodesk.Revit.DB import Transaction
from pyrevit import forms

from bkbim.app.commands import renumber_grids_command
from bkbim.revit.adapter.grid_name_writer import RevitGridRenumberWriter
from bkbim.revit.adapter.grid_position_reader import list_all_grids

doc = __revit__.ActiveUIDocument.Document


def main():
    grids = list_all_grids(doc)
    if not grids:
        forms.alert(u"No grids found in this project.", title=__title__)
        return

    proceed = forms.alert(
        u"Renumber all {0} grid(s) in the model?\n\n"
        u"Vertical grids -> letters, left to right (A, B, C...)\n"
        u"Horizontal grids -> numbers, top to bottom (1, 2, 3...)".format(len(grids)),
        title=__title__, yes=True, no=True)
    if not proceed:
        return

    writer = RevitGridRenumberWriter()

    t = Transaction(doc, u"Renumber Grids")
    t.Start()
    try:
        result = renumber_grids_command.run(grids, writer)
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
