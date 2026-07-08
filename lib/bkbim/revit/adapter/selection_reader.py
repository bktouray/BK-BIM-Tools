# -*- coding: utf-8 -*-
"""Classifies a pre-picked list of Revit elements/grids into domain models
(SAD Sec 4.3). The interactive box-select prompt itself is a UI concern and lives in
the pushbutton entry point, not here - this only classifies whatever was already
picked.

Ports the problem-space knowledge from the v5 reference implementation (minimum
dimensionable size, nested-family-instance skip, grid orientation/bubble detection),
re-verified against the live model rather than assumed correct (PHASE_1_PLAN Sec 1).

Grid references are resolved to real Reference objects immediately (via the injected
IReferenceProvider), since a grid needs exactly one Reference regardless of axis.
Element references are NOT resolved here - ElementInfo.ref stays the raw Element,
because faces differ per axis and are resolved later by the caller, per axis, via
IReferenceProvider.faces_for(element.ref, axis).
"""

import clr

clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")

from Autodesk.Revit.DB import BuiltInCategory, DatumEnds, ElementId, FamilyInstance, Grid, Line

from bkbim.domain.dimensioning.ports import ISelectionReader
from bkbim.domain.geometry.units import ft_to_mm
from bkbim.domain.models.element_info import ElementInfo
from bkbim.domain.models.grid_info import (
    BUBBLE_P0,
    BUBBLE_P1,
    ORIENTATION_HORIZONTAL,
    ORIENTATION_VERTICAL,
    GridInfo,
)

MIN_DIMENSIONABLE_SIZE_MM = 50.0


class RevitSelectionReader(ISelectionReader):
    def __init__(self, view, reference_provider):
        self._view = view
        self._reference_provider = reference_provider

    def read(self, selected_elements):
        elements = []
        grids = []
        seen_ids = set()

        wall_cat_id = ElementId(BuiltInCategory.OST_Walls)
        str_col_cat_id = ElementId(BuiltInCategory.OST_StructuralColumns)
        col_cat_id = ElementId(BuiltInCategory.OST_Columns)
        foundation_cat_id = ElementId(BuiltInCategory.OST_StructuralFoundation)
        framing_cat_id = ElementId(BuiltInCategory.OST_StructuralFraming)
        floor_cat_id = ElementId(BuiltInCategory.OST_Floors)

        for e in selected_elements:
            if isinstance(e, Grid):
                grid_info = self._grid_info(e)
                if grid_info is not None:
                    grids.append(grid_info)
                continue

            eid = e.Id
            if eid in seen_ids:
                continue
            seen_ids.add(eid)

            try:
                cat_id = e.Category.Id if e.Category is not None else None
            except Exception:
                continue

            if cat_id == wall_cat_id:
                info = self._element_info(e, u"Wall")
            elif cat_id == str_col_cat_id or cat_id == col_cat_id:
                if isinstance(e, FamilyInstance) and e.SuperComponent is not None:
                    continue  # nested/shared instance, not a real placed column
                info = self._element_info(e, u"Column")
            elif cat_id == foundation_cat_id:
                if isinstance(e, FamilyInstance) and e.SuperComponent is not None:
                    continue
                info = self._element_info(e, u"Footing")
            elif cat_id == framing_cat_id:
                if isinstance(e, FamilyInstance) and e.SuperComponent is not None:
                    continue
                info = self._element_info(e, u"Beam")
            elif cat_id == floor_cat_id:
                info = self._element_info(e, u"Slab")
            else:
                info = None

            if info is not None:
                elements.append(info)

        return elements, grids

    def _element_info(self, elem, category_label):
        try:
            bb = elem.get_BoundingBox(self._view) or elem.get_BoundingBox(None)
        except Exception:
            bb = None
        if bb is None:
            return None

        width_mm = ft_to_mm(abs(bb.Max.X - bb.Min.X))
        depth_mm = ft_to_mm(abs(bb.Max.Y - bb.Min.Y))
        if width_mm < MIN_DIMENSIONABLE_SIZE_MM or depth_mm < MIN_DIMENSIONABLE_SIZE_MM:
            return None

        return ElementInfo(
            ref=elem, category=category_label,
            min_x=bb.Min.X, max_x=bb.Max.X, min_y=bb.Min.Y, max_y=bb.Max.Y,
        )

    def _grid_info(self, grid):
        try:
            curve = grid.Curve
            if not isinstance(curve, Line):
                return None  # angled/curved grid - out of scope this iteration

            direction = curve.Direction.Normalize()
            p0 = curve.GetEndPoint(0)
            p1 = curve.GetEndPoint(1)

            if abs(direction.Y) < 0.1:
                orientation = ORIENTATION_HORIZONTAL
                coord = (p0.Y + p1.Y) / 2.0
            elif abs(direction.X) < 0.1:
                orientation = ORIENTATION_VERTICAL
                coord = (p0.X + p1.X) / 2.0
            else:
                return None  # angled grid - out of scope this iteration

            grid_ref = self._reference_provider.grid_reference(grid)
            if grid_ref is None:
                return None

            bubble_end = self._bubble_end(grid, p0, p1)

            return GridInfo(
                ref=grid_ref, name=grid.Name, orientation=orientation, coord=coord,
                p0=(p0.X, p0.Y), p1=(p1.X, p1.Y), bubble_end=bubble_end,
            )
        except Exception:
            return None

    def _bubble_end(self, grid, p0, p1):
        try:
            bubble_0_visible = grid.IsBubbleVisibleInView(DatumEnds.End0, self._view)
            bubble_1_visible = grid.IsBubbleVisibleInView(DatumEnds.End1, self._view)
            if bubble_1_visible and not bubble_0_visible:
                return BUBBLE_P1
            return BUBBLE_P0
        except Exception:
            return BUBBLE_P0
