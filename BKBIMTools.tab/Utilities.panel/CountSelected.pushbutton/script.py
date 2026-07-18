# -*- coding: utf-8 -*-
__title__ = u"Count\nSelected"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Counts the currently selected elements, by category."""

from bkbim.app.commands import count_selected_command
from bkbim.core import di
from bkbim.revit.adapter.model_reader import RevitElementReader
from bkbim.ui.views.result_dialog import show_result

uidoc = __revit__.ActiveUIDocument

# Per-command wiring for Phase 0; graduates to a one-time extension-startup
# bootstrap once a second command needs the same registration (ADR-0002).
container = di.get_container()
container.register_instance(di.SERVICE_ELEMENT_READER, RevitElementReader(uidoc))

result = count_selected_command.run()

if result.success:
    show_result(__title__, result.message)
else:
    show_result(__title__, u"Error: {0}".format(result.message))
