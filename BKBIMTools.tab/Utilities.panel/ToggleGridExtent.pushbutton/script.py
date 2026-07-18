# -*- coding: utf-8 -*-
__title__ = u"Toggle Grid\n2D / 3D"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Flips every grid in the view between 2D and 3D extent. Run it
again to flip back.
"""

from Autodesk.Revit.DB import Transaction
from pyrevit import forms

from bkbim.app.commands import toggle_grid_extent_command
from bkbim.revit.adapter.grid_extent_reader import list_grids_with_extent
from bkbim.revit.adapter.grid_extent_writer import RevitGridExtentWriter
from bkbim.ui.views.result_dialog import show_result

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
view = doc.ActiveView


def main():
    grids = list_grids_with_extent(doc, view)
    if not grids:
        show_result(__title__, u"No grids found in this view.")
        return

    writer = RevitGridExtentWriter(doc, view)

    t = Transaction(doc, u"Toggle Grid 2D/3D")
    t.Start()
    try:
        result = toggle_grid_extent_command.run(grids, writer)
    except Exception as e:
        t.RollBack()
        show_result(__title__, u"Error:\n{0}".format(str(e)))
        return

    if result.success:
        t.Commit()
    else:
        t.RollBack()
    show_result(__title__, result.message)


if __name__ == "__main__":
    main()
