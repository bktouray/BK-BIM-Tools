# -*- coding: utf-8 -*-
__title__ = u"Auto\nTag"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Tags marked doors, windows, columns, beams, or footings in the
views you pick. Choose a category, pick the tag family/type you want, and
every untagged element gets tagged - already-tagged elements are skipped.
"""

from bkbim.revit.adapter.tag_flow import choose_category, run_auto_tag_flow

doc = __revit__.ActiveUIDocument.Document
view = doc.ActiveView


def main():
    category = choose_category()
    if category is None:
        return  # user cancelled

    run_auto_tag_flow(doc, view, category, __title__)


if __name__ == "__main__":
    main()
