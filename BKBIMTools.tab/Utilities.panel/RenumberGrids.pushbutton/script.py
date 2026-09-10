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
__doc__ = u"""Renumbers every grid in the model with a selectable naming
direction.
"""

from Autodesk.Revit.DB import Transaction

from bkbim.app.commands import renumber_grids_command
from bkbim.domain.models.grid_position import (
    SCHEME_LETTERS_LEFT_NUMBERS_TOP, SCHEME_LETTERS_TOP_NUMBERS_LEFT,
)
from bkbim.revit.adapter.grid_name_writer import RevitGridRenumberWriter
from bkbim.revit.adapter.grid_position_reader import list_all_grids
from bkbim.ui.views.confirmation_dialog import show_confirmation
from bkbim.ui.views.list_picker import show_list_picker
from bkbim.ui.views.result_dialog import show_result

doc = __revit__.ActiveUIDocument.Document

_SCHEME_LABEL_DEFAULT = u"Letters left to right; numbers top to bottom"
_SCHEME_LABEL_SWAPPED = u"Letters top to bottom; numbers left to right"
_SCHEME_BY_LABEL = {
    _SCHEME_LABEL_DEFAULT: SCHEME_LETTERS_LEFT_NUMBERS_TOP,
    _SCHEME_LABEL_SWAPPED: SCHEME_LETTERS_TOP_NUMBERS_LEFT,
}
_CONFIRM_TEXT_BY_LABEL = {
    _SCHEME_LABEL_DEFAULT: (
        u"Vertical grids -> letters, left to right (A, B, C...)\n"
        u"Horizontal grids -> numbers, top to bottom (1, 2, 3...)"),
    _SCHEME_LABEL_SWAPPED: (
        u"Horizontal grids -> letters, top to bottom (A, B, C...)\n"
        u"Vertical grids -> numbers, left to right (1, 2, 3...)"),
}


def main():
    grids = list_all_grids(doc)
    if not grids:
        show_result(__title__, u"No grids found in this project.")
        return

    scheme_label = show_list_picker(
        __title__,
        u"Choose how the grid names should run.",
        [_SCHEME_LABEL_DEFAULT, _SCHEME_LABEL_SWAPPED],
        default_label=_SCHEME_LABEL_DEFAULT)
    if scheme_label is None:
        return

    proceed = show_confirmation(
        __title__,
        u"Renumber all {0} grid(s) in the model?\n\n{1}".format(
            len(grids), _CONFIRM_TEXT_BY_LABEL[scheme_label]))
    if not proceed:
        return

    writer = RevitGridRenumberWriter()

    t = Transaction(doc, u"Renumber Grids")
    t.Start()
    try:
        result = renumber_grids_command.run(grids, writer, scheme=_SCHEME_BY_LABEL[scheme_label])
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
