# -*- coding: utf-8 -*-
"""Ports: interfaces the domain declares and the Revit adapter implements.

This is the dependency-inversion seam (SAD Sec 2): keeping interfaces here, not in
`bkbim.revit`, is what lets `bkbim.app` depend only on the domain layer and never
import Revit adapter code directly.
"""


class IElementReader(object):
    """Reads facts about the live Revit selection/model.

    Implemented by bkbim.revit.adapter.model_reader.RevitElementReader.
    """

    def count_selected(self):
        """Returns a SelectionSummary describing the current selection.

        :rtype: bkbim.domain.models.selection_summary.SelectionSummary
        """
        raise NotImplementedError
