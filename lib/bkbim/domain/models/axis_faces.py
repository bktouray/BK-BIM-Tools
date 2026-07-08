# -*- coding: utf-8 -*-
"""The two extreme face references of an element along one axis, with their
coordinate positions. Produced by the (Phase 1 Stage 4) reference provider adapter;
consumed by the pure dimension planner. Pure domain data (ADR-0001).
"""


class AxisFaces(object):
    def __init__(self, ref_lo, ref_hi, coord_lo, coord_hi):
        self.ref_lo = ref_lo
        self.ref_hi = ref_hi
        self.coord_lo = coord_lo
        self.coord_hi = coord_hi
