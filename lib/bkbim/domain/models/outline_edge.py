# -*- coding: utf-8 -*-
"""One straight, axis-aligned boundary segment of an element's real outline
(as opposed to AxisFaces, which only keeps the two EXTREME faces of an
axis-aligned bounding box). Produced by the Revit adapter reading an
element's actual side faces; consumed by the pure outline planner. Pure
domain data (ADR-0001) - `ref` is an opaque handle, same convention as
AxisFaces/GridInfo.
"""


class OutlineEdge(object):
    def __init__(self, ref, axis, coord, span_lo, span_hi, sign):
        self.ref = ref
        self.axis = axis  # "x" | "y" - this edge's own face-NORMAL axis
        self.coord = coord  # this edge's own constant coordinate along `axis`
        self.span_lo = span_lo  # this edge's real extent along the OTHER axis
        self.span_hi = span_hi
        self.sign = sign  # +1 or -1 - which way the face normal points along `axis`

    def __repr__(self):
        return u"<OutlineEdge axis={0} coord={1:.2f} span=[{2:.2f}..{3:.2f}]>".format(
            self.axis, float(self.coord), float(self.span_lo), float(self.span_hi))
