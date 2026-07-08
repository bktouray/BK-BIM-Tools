# -*- coding: utf-8 -*-
"""A planned dimension: which references to combine, in what order, where the line
goes. Pure domain data (ADR-0001) - `refs` are opaque handles (same convention as
ElementInfo.ref); the Revit adapter resolves them to real Reference objects and
calls doc.Create.NewDimension. The planner never touches Revit types.
"""


class DimensionPlan(object):
    KIND_OVERALL = u"overall"
    KIND_SNAP_ON_EDGE = u"snap_on_edge"
    KIND_INSIDE_CHAIN = u"inside_chain"
    KIND_OUTSIDE_CHAIN = u"outside_chain"
    KIND_GRID_SEQUENTIAL = u"grid_sequential"  # inner string: grid -> grid -> grid
    KIND_GRID_OVERALL = u"grid_overall"  # outer string: first grid -> last grid
    KIND_WALL_RUN = u"wall_run"  # wall-end -> opening jambs -> ... -> wall-end
    # column-edge -> column-edge -> ... across a row, no grid references at all
    KIND_COLUMN_ROW_CHAIN = u"column_row_chain"
    # one column's own two faces, no grid ref - sits further out than that same
    # column's detail (face-grid-face) dimension, not a span across a whole row
    KIND_COLUMN_OVERALL = u"column_overall"
    # one slab face -> its own closest grid (never a grid shared with the
    # opposite face) - Slab Dimensions' "Grid to slab edges" mode
    KIND_SLAB_EDGE_TO_GRID = u"slab_edge_to_grid"
    # one real outline edge's own length, referenced to its two adjacent
    # perpendicular edges (the ones sharing its two corners) - Slab
    # Dimensions' "All edges of the slab" mode, true perimeter tracing for
    # non-rectangular (notched/stepped) footprints, not a bounding-box guess
    KIND_SLAB_OUTLINE_EDGE = u"slab_outline_edge"
    # wall-end -> each perpendicular wall's own faces -> ... -> wall-end, one
    # continuous chain (never split, unlike KIND_WALL_RUN) - the "middle"
    # string of an exterior wall's 3-string perimeter dimensioning
    KIND_WALL_PERPENDICULAR_CHAIN = u"wall_perpendicular_chain"
    # a wall's own two end faces, no intermediate refs at all - the
    # "outermost" string of an exterior wall's 3-string perimeter
    # dimensioning, further out than KIND_WALL_PERPENDICULAR_CHAIN
    KIND_WALL_OVERALL = u"wall_overall"

    def __init__(self, kind, refs, axis, line_coord_lo, line_coord_hi, perp_pos):
        self.kind = kind
        self.refs = refs
        self.axis = axis
        self.line_coord_lo = line_coord_lo
        self.line_coord_hi = line_coord_hi
        self.perp_pos = perp_pos

    def __repr__(self):
        return u"<DimensionPlan {0} axis={1} refs={2}>".format(
            self.kind, self.axis, len(self.refs))
