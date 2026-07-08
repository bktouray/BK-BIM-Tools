# -*- coding: utf-8 -*-
"""Walking-skeleton model only (Phase 0). Real domain models - Element, Reference,
DimensionPlan, Standard - land in Phase 1 when Auto Dimension is ported (SAD Sec 4.2).
"""


class SelectionSummary(object):
    """Result of counting the current Revit selection."""

    def __init__(self, count, category_counts=None):
        self.count = count
        self.category_counts = category_counts or {}

    def __repr__(self):
        return u"<SelectionSummary count={0}>".format(self.count)
