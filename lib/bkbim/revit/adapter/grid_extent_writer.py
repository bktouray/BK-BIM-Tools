# -*- coding: utf-8 -*-
"""Writes a grid's datum-extent state (2D/3D) back to Revit, for the Toggle
Grid 2D/3D utility (2026-07-07).
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import DatumEnds, DatumExtentType

from bkbim.domain.grids.ports import IGridExtentWriter
from bkbim.domain.models.grid_extent import EXTENT_MODEL


def _to_revit_extent(domain_extent):
    return DatumExtentType.Model if domain_extent == EXTENT_MODEL else DatumExtentType.ViewSpecific


class RevitGridExtentWriter(IGridExtentWriter):
    def __init__(self, doc, view):
        self._doc = doc
        self._view = view

    def set_extent(self, grid_ref, end0_extent, end1_extent):
        # The getter is GetDatumExtentTypeInView, but the setter is just
        # SetDatumExtentType (no "InView" suffix) - confirmed live 2026-07-07
        # after AttributeError: 'Grid' object has no attribute
        # 'SetDatumExtentTypeInView'. Same (datumEnd, view, extentMode) signature.
        grid_ref.SetDatumExtentType(DatumEnds.End0, self._view, _to_revit_extent(end0_extent))
        grid_ref.SetDatumExtentType(DatumEnds.End1, self._view, _to_revit_extent(end1_extent))
