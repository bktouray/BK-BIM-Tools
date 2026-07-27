# -*- coding: utf-8 -*-
__title__ = u"Highlight\nShafts"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Highlight Shaft Openings in plan views.

Fills every Shaft Opening in the chosen view(s), optionally adds diagonal
X-lines, and can group the generated detail elements per view. Re-run after
moving, resizing, or adding shafts: previous BK BIM shaft highlights are
rebuilt, while manually drawn filled regions over a shaft are left alone.
"""

from bkbim.revit.adapter.shaft_highlight_flow import run_highlight_shafts_flow

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
view = doc.ActiveView


if __name__ == "__main__":
    run_highlight_shafts_flow(doc, uidoc, view, __title__.replace(u"\n", u" "))
