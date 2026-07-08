# -*- coding: utf-8 -*-
"""Resolves an element/type's display name across the various Revit API paths that
can fail for a given category (SAD Sec 4.3, revit2026-ironpython-quirks memory).

`Element.Name.GetValue(e)` - the previously-recorded fix for WallType.Name raising
AttributeError - does NOT work for DimensionType in this environment (verified live
2026-07-05: raises a different, unexpected error). SYMBOL_NAME_PARAM works instead
for DimensionType and is tried first here, with the old fixes kept as fallbacks for
element types where they do work.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import BuiltInParameter, Element


def type_name(element, fallback=u"Unnamed"):
    for bip in (BuiltInParameter.SYMBOL_NAME_PARAM, BuiltInParameter.ALL_MODEL_TYPE_NAME):
        try:
            param = element.get_Parameter(bip)
            if param is not None:
                value = param.AsString()
                if value:
                    return value
        except Exception:
            continue

    try:
        value = Element.Name.GetValue(element)
        if value:
            return value
    except Exception:
        pass

    try:
        value = element.Name
        if value:
            return value
    except Exception:
        pass

    return fallback
