# -*- coding: utf-8 -*-
"""Lists usable DimensionType elements for the options-window style picker.

Real bug caught live (2026-07-05): FilteredElementCollector(doc).OfClass(DimensionType)
returns EVERY dimension style - Linear, Angular, Radial, SpotElevation, etc. Passing
a non-Linear type into NewDimension() for a linear dimension raises "The dimension
type is a non-linear dimension type." Only Linear types are usable for the
element/grid/wall-run dimensioning this suite creates.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import DimensionStyleType, DimensionType, FilteredElementCollector


def list_linear_dimension_types(doc):
    all_types = FilteredElementCollector(doc).OfClass(DimensionType).ToElements()
    return [dt for dt in all_types if dt.StyleType == DimensionStyleType.Linear]
