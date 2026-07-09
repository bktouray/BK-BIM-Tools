# -*- coding: utf-8 -*-
"""Reads every family type actually placed in the document for ONE Auto Mark
category (Doors, Windows, Columns, Beams, Footings) at a time - doc-wide, not
view-scoped, since Mark numbering should account for every placed instance
regardless of which view is active.

Dimension reading differs by category since there's no single Revit
parameter scheme that covers all of them:
- Doors/Windows have real BuiltInParameters (DOOR_WIDTH/DOOR_HEIGHT etc.),
  read off the type first, same convention as lib/bkbim/boq/extractors.py's
  door/window fields.
- Columns/Beams/Footings have no universal BuiltInParameter for their
  section/plan dimensions - family authors use all sorts of display names
  ("b"/"h", "Width"/"Depth", "bf"/"d", ...), so these fall back to a list of
  candidate LookupParameter name pairs, extending the same idea already used
  (write-side) by lib/bkbim/automation/columns.py's _BH_NAMES.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import (
    BuiltInCategory, BuiltInParameter, FamilyInstance, FilteredElementCollector,
)

from bkbim.domain.geometry.units import ft_to_mm
from bkbim.domain.models.mark_family_group import MarkFamilyGroup
from bkbim.domain.models.mark_type_group import MarkTypeGroup
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.stable_representation import element_id_token

CATEGORY_DOORS = u"Doors"
CATEGORY_WINDOWS = u"Windows"
CATEGORY_COLUMNS = u"Columns"
CATEGORY_BEAMS = u"Beams"
CATEGORY_FOOTINGS = u"Footings"

CATEGORIES = (CATEGORY_DOORS, CATEGORY_WINDOWS, CATEGORY_COLUMNS,
              CATEGORY_BEAMS, CATEGORY_FOOTINGS)

CATEGORY_BUILTIN_CATEGORIES = {
    CATEGORY_DOORS: (BuiltInCategory.OST_Doors,),
    CATEGORY_WINDOWS: (BuiltInCategory.OST_Windows,),
    CATEGORY_COLUMNS: (BuiltInCategory.OST_StructuralColumns, BuiltInCategory.OST_Columns),
    CATEGORY_BEAMS: (BuiltInCategory.OST_StructuralFraming,),
    CATEGORY_FOOTINGS: (BuiltInCategory.OST_StructuralFoundation,),
}

# Dimension-A label shown in the review window per category (Dimension-B is
# always "Height" for Doors/Windows, "H"/"Depth" for Columns/Beams, "Width"
# for Footings - the flow module derives that label from the category too).
DIMENSION_A_LABEL = {
    CATEGORY_DOORS: u"Width",
    CATEGORY_WINDOWS: u"Width",
    CATEGORY_COLUMNS: u"B",
    CATEGORY_BEAMS: u"B",
    CATEGORY_FOOTINGS: u"Length",
}
DIMENSION_B_LABEL = {
    CATEGORY_DOORS: u"Height",
    CATEGORY_WINDOWS: u"Height",
    CATEGORY_COLUMNS: u"H",
    CATEGORY_BEAMS: u"H",
    CATEGORY_FOOTINGS: u"Width",
}

_DOOR_WIDTH_BIPS = (u"DOOR_WIDTH", u"FAMILY_WIDTH_PARAM", u"GENERIC_WIDTH")
_DOOR_HEIGHT_BIPS = (u"DOOR_HEIGHT", u"FAMILY_HEIGHT_PARAM", u"GENERIC_HEIGHT")
_WINDOW_WIDTH_BIPS = (u"WINDOW_WIDTH", u"FAMILY_WIDTH_PARAM", u"GENERIC_WIDTH")
_WINDOW_HEIGHT_BIPS = (u"WINDOW_HEIGHT", u"FAMILY_HEIGHT_PARAM", u"GENERIC_HEIGHT")

# Candidate (b, h) display-name pairs across rectangular/I-shape structural
# families - same list lib/bkbim/automation/columns.py writes with, plus
# "bf"/"d" for I-shaped beam sections.
_COLUMN_BEAM_BH_PAIRS = [(u"b", u"h"), (u"Width", u"Depth"), (u"w", u"d"),
                         (u"B", u"H"), (u"Width", u"Height"), (u"bf", u"d")]

# Candidate (length, width) display-name pairs for footing families.
_FOOTING_LW_PAIRS = [(u"Length", u"Width"), (u"L", u"B"), (u"Width", u"Length")]

def _bip(name):
    return getattr(BuiltInParameter, name, None)


def _double_by_bip(element, bip_names):
    if element is None:
        return None
    for name in bip_names:
        bip = _bip(name)
        if bip is None:
            continue
        try:
            p = element.get_Parameter(bip)
            if p is not None:
                v = p.AsDouble()
                if v:
                    return v
        except Exception:
            continue
    return None


def _type_dim_bip_pair_mm(symbol, a_bips, b_bips):
    a_ft = _double_by_bip(symbol, a_bips)
    b_ft = _double_by_bip(symbol, b_bips)
    return (ft_to_mm(a_ft) if a_ft is not None else None,
            ft_to_mm(b_ft) if b_ft is not None else None)


def _lookup_pair_mm(symbol, name_pairs):
    for a_name, b_name in name_pairs:
        try:
            pa = symbol.LookupParameter(a_name)
            pb = symbol.LookupParameter(b_name)
        except Exception:
            continue
        if pa is None or pb is None:
            continue
        try:
            a_ft = pa.AsDouble()
            b_ft = pb.AsDouble()
        except Exception:
            continue
        return ft_to_mm(a_ft), ft_to_mm(b_ft)
    return None, None


_DIMENSION_READERS = {
    CATEGORY_DOORS: lambda symbol: _type_dim_bip_pair_mm(symbol, _DOOR_WIDTH_BIPS, _DOOR_HEIGHT_BIPS),
    CATEGORY_WINDOWS: lambda symbol: _type_dim_bip_pair_mm(symbol, _WINDOW_WIDTH_BIPS, _WINDOW_HEIGHT_BIPS),
    CATEGORY_COLUMNS: lambda symbol: _lookup_pair_mm(symbol, _COLUMN_BEAM_BH_PAIRS),
    CATEGORY_BEAMS: lambda symbol: _lookup_pair_mm(symbol, _COLUMN_BEAM_BH_PAIRS),
    CATEGORY_FOOTINGS: lambda symbol: _lookup_pair_mm(symbol, _FOOTING_LW_PAIRS),
}


def _family_name(symbol, fallback=u"Unnamed Family"):
    try:
        name = symbol.Family.Name
        if name:
            return name
    except Exception:
        pass
    return fallback


def read_family_groups(doc, category):
    """Every family+type of `category` with at least one placed instance,
    grouped as MarkFamilyGroup -> MarkTypeGroup, each holding the ElementIds
    of every instance of that type (every one of which will get the same
    mark - see mark_planner.py).

    :rtype: list of bkbim.domain.models.mark_family_group.MarkFamilyGroup
    """
    dimension_reader = _DIMENSION_READERS[category]

    elements_by_symbol_id = {}
    symbol_by_id = {}
    for built_in_category in CATEGORY_BUILTIN_CATEGORIES[category]:
        collected = (FilteredElementCollector(doc).OfCategory(built_in_category)
                     .WhereElementIsNotElementType().ToElements())
        for elem in collected:
            if not isinstance(elem, FamilyInstance):
                continue
            symbol = elem.Symbol
            if symbol is None:
                continue
            key = element_id_token(symbol.Id)
            symbol_by_id[key] = symbol
            elements_by_symbol_id.setdefault(key, []).append(elem)

    families = {}
    for key, elements in elements_by_symbol_id.items():
        symbol = symbol_by_id[key]
        family_name = _family_name(symbol)
        dimension_a_mm, dimension_b_mm = dimension_reader(symbol)

        type_group = MarkTypeGroup(
            type_name=type_name(symbol), dimension_a_mm=dimension_a_mm,
            dimension_b_mm=dimension_b_mm,
            instance_refs=[elem.Id for elem in elements])
        families.setdefault(family_name, []).append(type_group)

    return [MarkFamilyGroup(name, groups) for name, groups in families.items()]
