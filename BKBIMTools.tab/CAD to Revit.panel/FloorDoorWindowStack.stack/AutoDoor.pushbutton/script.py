# -*- coding: utf-8 -*-
__title__ = u"AutoDoor"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Place wall-hosted doors from a CAD layer. The distance between
each pair of parallel lines sets the opening width; pick the family type,
host level and lintel height.
"""

from pyrevit import revit, DB

# Dev reload: always pick up the latest bkbim.automation/adapter/ui lib code
# on each click.
import sys as _sys
for _m in [_n for _n in list(_sys.modules)
          if _n.startswith("bkbim.automation") or _n.startswith("bkbim.revit.adapter")
          or _n.startswith("bkbim.ui.views")]:
    del _sys.modules[_m]

from bkbim.revit.adapter.opening_flow import run_opening_flow

run_opening_flow(revit.doc, DB.BuiltInCategory.OST_Doors, "Door",
                 default_width_mm=900, default_lintel_mm=2100, default_height_mm=2100)
