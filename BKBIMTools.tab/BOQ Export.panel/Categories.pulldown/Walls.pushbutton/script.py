# -*- coding: utf-8 -*-
__title__ = u"Walls"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Export wall types with full layer breakdown, thickness per layer, total thickness, and aggregated count/area/volume/length per type."""

from bkbim.boq import service
service.run_export(['Walls'], default_name='BKDesigns_Walls')
