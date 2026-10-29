# -*- coding: utf-8 -*-
__title__ = u"Master\nFilter"
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"Find elements by category, family, type, level and parameter rules. Preview, select, show or temporarily isolate matches."

from bkbim.revit.adapter.master_filter import run

run(__revit__.ActiveUIDocument)
