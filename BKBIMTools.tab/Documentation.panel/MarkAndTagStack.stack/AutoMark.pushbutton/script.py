# -*- coding: utf-8 -*-
__title__ = u"Auto\nMark"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Number doors, windows, columns, beams, or footings for
schedules. Pick a category, give each family a prefix, and every placed
instance gets a Mark - largest type first, numbered continuously per
family.
"""

from bkbim.revit.adapter.mark_flow import choose_category, run_auto_mark_flow
from bkbim.ui.views.result_dialog import show_result

doc = __revit__.ActiveUIDocument.Document


def main():
    category = choose_category()
    if category is None:
        return  # user cancelled

    result, message = run_auto_mark_flow(doc, category, __title__)
    if message:
        show_result(__title__, message)


if __name__ == "__main__":
    main()
