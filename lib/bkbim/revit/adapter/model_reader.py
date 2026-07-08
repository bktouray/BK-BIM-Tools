# -*- coding: utf-8 -*-
"""Implements IElementReader against a live Revit UIDocument (SAD Sec 4.3).

This is the walking-skeleton adapter (Phase 0): it proves the dependency-inversion
seam works end to end. Real model-reading logic (grids, walls, columns, bounding
boxes) is ported from the AutoDims monolith in Phase 1.
"""

import clr

clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")

from bkbim.domain.models.selection_summary import SelectionSummary
from bkbim.domain.ports import IElementReader


def _category_name(element):
    try:
        return element.Category.Name if element.Category is not None else u"(no category)"
    except Exception:
        return u"(no category)"


class RevitElementReader(IElementReader):
    """Reads the current selection from a live UIDocument.

    uidoc is passed in explicitly (constructor injection) rather than read from a
    global - matches the convention already used by lib/bkd_walllegend.py, and keeps
    this class testable with a fake uidoc.
    """

    def __init__(self, uidoc):
        self._uidoc = uidoc

    def count_selected(self):
        doc = self._uidoc.Document
        ids = self._uidoc.Selection.GetElementIds()

        count = 0
        category_counts = {}
        for eid in ids:
            element = doc.GetElement(eid)
            if element is None:
                continue
            count += 1
            cat_name = _category_name(element)
            category_counts[cat_name] = category_counts.get(cat_name, 0) + 1

        return SelectionSummary(count=count, category_counts=category_counts)
