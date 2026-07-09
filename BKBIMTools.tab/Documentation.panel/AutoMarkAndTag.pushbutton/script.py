# -*- coding: utf-8 -*-
__title__ = u"Auto Mark\n& Tag"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Numbers AND tags doors, windows, columns, beams, or footings
in one run. Pick a category - Auto Mark assigns the Marks first, then Auto
Tag places tags in the view(s) you choose. Use the separate Auto Mark /
Auto Tag buttons if you only need one step.
"""

from bkbim.revit.adapter.mark_and_tag_flow import choose_category, run_mark_and_tag_flow

doc = __revit__.ActiveUIDocument.Document
view = doc.ActiveView


def main():
    category = choose_category()
    if category is None:
        return  # user cancelled

    run_mark_and_tag_flow(doc, view, category, __title__)


if __name__ == "__main__":
    main()
