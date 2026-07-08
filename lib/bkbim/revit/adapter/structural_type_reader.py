# -*- coding: utf-8 -*-
"""Lists structural elements/types ONE CATEGORY at a time (Column, Beam,
Footing) in a view, for the "which types to dimension" multi-select filter -
mirrors wall_type_reader.py's pattern.

Originally listed all categories mixed together, but a mixed column/beam/
footing type list with no visual distinction was confusing (product owner,
2026-07-06: "I don't know what's what") - fixed by having the caller
(structural_dimension_flow.py) ask the user to pick ONE category first via
`forms.CommandSwitchWindow`, so this module only ever needs to list one
category's elements/types at a time. Slab isn't here - it's a Floor, not a
FamilyInstance, and lives in slab_type_reader.py with its own
GetTypeId()-based type lookup.

Beams (OST_StructuralFraming) added same day per product owner: "dimensions
between beams... taking in their widths... going from beam to beam" - no new
domain logic needed, `column_grid_planner.plan_structural_dimensions()` is
already generic over any element with an axis-aligned bounding box and
resolvable faces.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import BuiltInCategory, FamilyInstance, FilteredElementCollector

from bkbim.revit.adapter.stable_representation import element_id_token

CATEGORY_COLUMN = u"Column"
CATEGORY_BEAM = u"Beam"
CATEGORY_FOOTING = u"Footing"

CATEGORY_BUILTIN_CATEGORIES = {
    CATEGORY_COLUMN: (BuiltInCategory.OST_StructuralColumns, BuiltInCategory.OST_Columns),
    CATEGORY_BEAM: (BuiltInCategory.OST_StructuralFraming,),
    CATEGORY_FOOTING: (BuiltInCategory.OST_StructuralFoundation,),
}


def list_structural_elements_by_category(doc, view, category):
    """Returns every FamilyInstance from just ONE category ('Column' | 'Beam' |
    'Footing') visible in `view`.
    """
    elements = []
    for built_in_category in CATEGORY_BUILTIN_CATEGORIES[category]:
        collected = FilteredElementCollector(doc, view.Id).OfCategory(
            built_in_category).WhereElementIsNotElementType().ToElements()
        elements.extend([e for e in collected if isinstance(e, FamilyInstance)])
    return elements


def types_from_elements(elements):
    """Returns the distinct FamilySymbol types used by `elements`, ordered by
    first appearance.
    """
    seen_ids = set()
    types = []
    for elem in elements:
        symbol = elem.Symbol
        if symbol is None:
            continue
        id_value = element_id_token(symbol.Id)
        if id_value in seen_ids:
            continue
        seen_ids.add(id_value)
        types.append(symbol)

    return types
