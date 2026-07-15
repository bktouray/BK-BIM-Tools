# -*- coding: utf-8 -*-
__title__ = u"AutoColumn"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Scans a CAD layer for rectangular columns and places native
Revit columns, grouped by section size. Can auto-generate a correctly sized
family type per section.
"""

from pyrevit import revit

# Dev reload: always pick up the latest bkbim.automation/adapter/ui lib code
# on each click.
import sys as _sys
for _m in [_n for _n in list(_sys.modules)
          if _n.startswith("bkbim.automation") or _n.startswith("bkbim.revit.adapter")
          or _n.startswith("bkbim.ui.views")]:
    del _sys.modules[_m]

from bkbim.revit.adapter.auto_column_flow import run_auto_column_flow

doc = revit.doc


def main():
    run_auto_column_flow(doc, __title__)


if __name__ == "__main__":
    main()
