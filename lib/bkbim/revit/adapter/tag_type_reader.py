# -*- coding: utf-8 -*-
"""Reads loaded tag family types and taggable elements for ONE Auto Mark
category (Doors, Windows, Columns, Beams, Footings) at a time - reuses the
exact same category set Auto Mark already defines
(mark_type_reader.CATEGORIES/CATEGORY_BUILTIN_CATEGORIES) so "Doors" means
the same thing in both tools.

Columns is the one category with two distinct host categories
(architectural OST_Columns and structural OST_StructuralColumns), each with
its OWN tag category - a Column Tag can't tag a structural column and vice
versa. `list_tag_types` lists BOTH tag categories' loaded types together
(labeled via element_naming.type_name like any other type list); at write
time `list_taggable_elements` only returns elements whose own host category
matches the CHOSEN tag type's category, so a Column Tag never gets handed a
structural column and skips it silently rather than erroring.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import BuiltInCategory, FamilyInstance, FamilySymbol, FilteredElementCollector

from bkbim.revit.adapter.mark_type_reader import CATEGORIES, CATEGORY_BUILTIN_CATEGORIES

# Every host category Auto Mark/Auto Tag deals with, mapped to the tag
# category that can tag it. Some tag categories don't exist on very old
# Revit versions - getattr(..., None) below keeps this from ever throwing.
_HOST_TO_TAG_BIC_NAMES = {
    BuiltInCategory.OST_Doors: u"OST_DoorTags",
    BuiltInCategory.OST_Windows: u"OST_WindowTags",
    BuiltInCategory.OST_Columns: u"OST_ColumnTags",
    BuiltInCategory.OST_StructuralColumns: u"OST_StructuralColumnTags",
    BuiltInCategory.OST_StructuralFraming: u"OST_StructuralFramingTags",
    BuiltInCategory.OST_StructuralFoundation: u"OST_StructuralFoundationTags",
}


def _tag_bic(host_bic):
    name = _HOST_TO_TAG_BIC_NAMES.get(host_bic)
    return getattr(BuiltInCategory, name, None) if name else None


def _id_value(element_id):
    try:
        return element_id.Value
    except AttributeError:
        return element_id.IntegerValue


def _bic_int(bic):
    # Same cross-engine fallback as lib/bkbim/boq/rvt.py's bic_int() - plain
    # int() works for a .NET enum on IronPython/CPython here, but falls back
    # to System.Convert for engines where it doesn't.
    try:
        return int(bic)
    except (TypeError, ValueError):
        from System import Convert
        return Convert.ToInt32(bic)


def list_tag_types(doc, category):
    """Every loaded FamilySymbol from the tag category/categories that can
    tag `category`'s host elements, across all of them combined (e.g. both
    Column Tag and Structural Column Tag for "Columns").

    :rtype: list of Autodesk.Revit.DB.FamilySymbol
    """
    tag_types = []
    for host_bic in CATEGORY_BUILTIN_CATEGORIES[category]:
        tag_bic = _tag_bic(host_bic)
        if tag_bic is None:
            continue
        symbols = (FilteredElementCollector(doc).OfClass(FamilySymbol)
                   .OfCategory(tag_bic).ToElements())
        tag_types.extend(symbols)
    return tag_types


def list_taggable_elements(doc, view, category, tag_type):
    """Every placed FamilyInstance of `category`, visible in `view`, whose
    own host category matches `tag_type`'s tag category - i.e. the elements
    this specific tag type is actually able to tag.

    :rtype: list of Autodesk.Revit.DB.FamilyInstance
    """
    host_bics = CATEGORY_BUILTIN_CATEGORIES[category]
    tag_category_id_value = _id_value(tag_type.Category.Id)
    matching_host_bics = [bic for bic in host_bics
                           if _tag_bic(bic) is not None and _bic_int(_tag_bic(bic)) == tag_category_id_value]
    if not matching_host_bics:
        return []

    elements = []
    for host_bic in matching_host_bics:
        collected = (FilteredElementCollector(doc, view.Id).OfCategory(host_bic)
                     .WhereElementIsNotElementType().ToElements())
        for elem in collected:
            if isinstance(elem, FamilyInstance):
                elements.append(elem)
    return elements
