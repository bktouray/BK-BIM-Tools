# -*- coding: utf-8 -*-
"""Writes a grid's Name back to Revit, for the Renumber Grids utility."""

from bkbim.domain.grids.ports import IGridRenumberWriter


class RevitGridRenumberWriter(IGridRenumberWriter):
    def set_name(self, grid_ref, new_name):
        grid_ref.Name = new_name
