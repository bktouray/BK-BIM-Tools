# -*- coding: utf-8 -*-
"""Places one IndependentTag per element for the Auto Tag flow. No leader
(head sits right at the element), horizontal orientation - a plain, safe
default; the tag type itself is the only thing the user picks per run.

No Transaction handling here - same convention as every other writer in this
codebase (SAD Sec 4.4): the caller (tag_flow.py) owns the Transaction, this
class just performs one IndependentTag.Create per call and reports whether
it worked.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import IndependentTag, Reference, TagOrientation

from bkbim.domain.tagging.ports import ITagWriter


def _tag_point(element):
    location = getattr(element, u"Location", None)
    point = getattr(location, u"Point", None) if location is not None else None
    if point is not None:
        return point

    curve = getattr(location, u"Curve", None) if location is not None else None
    if curve is not None:
        try:
            return curve.Evaluate(0.5, True)
        except Exception:
            pass

    try:
        bbox = element.get_BoundingBox(None)
        if bbox is not None:
            return (bbox.Min + bbox.Max) * 0.5
    except Exception:
        pass
    return None


class RevitTagWriter(ITagWriter):
    def __init__(self, doc, view, tag_type):
        self._doc = doc
        self._view = view
        self._tag_type_id = tag_type.Id

    def write(self, element):
        point = _tag_point(element)
        if point is None:
            return None
        try:
            return IndependentTag.Create(
                self._doc, self._tag_type_id, self._view.Id, Reference(element),
                False, TagOrientation.Horizontal, point)
        except Exception:
            return None
