# -*- coding: utf-8 -*-
"""Auto-dimension grids in the active plan view.

For each run of parallel grids the tool lays down two dimension strings:
  1. a chained string measuring grid-to-grid (every bay), and
  2. an overall string, offset further out, from the first grid to the
     furthest grid.

Both vertical grids (dimensioned across the top) and horizontal grids
(dimensioned down the side) are handled. The caller owns the transaction.

IronPython 2.7.
"""

from pyrevit import DB

_AXIS_TOL = 1e-4


class DimResult(object):
    def __init__(self):
        self.created = 0
        self.errors = []


def get_view_grids(doc, view):
    """Linear grids visible in the given view, paired with their curve."""
    grids = (
        DB.FilteredElementCollector(doc, view.Id)
        .OfClass(DB.Grid)
        .WhereElementIsNotElementType()
        .ToElements()
    )
    out = []
    for g in grids:
        try:
            crv = g.Curve
        except Exception:
            crv = None
        if isinstance(crv, DB.Line):
            out.append((g, crv))
    return out


def _classify(pairs):
    """Split linear grids into (verticals, horizontals) by run direction.

    vertical  = grid runs along Y (dx ~ 0), positioned at different X
    horizontal= grid runs along X (dy ~ 0), positioned at different Y
    """
    verticals = []
    horizontals = []
    for g, crv in pairs:
        d = (crv.GetEndPoint(1) - crv.GetEndPoint(0)).Normalize()
        if abs(d.X) <= 1e-3 and abs(d.Y) > 1e-3:
            verticals.append((g, crv))
        elif abs(d.Y) <= 1e-3 and abs(d.X) > 1e-3:
            horizontals.append((g, crv))
    return verticals, horizontals


def _endpoints(pairs):
    pts = []
    for _g, crv in pairs:
        pts.append(crv.GetEndPoint(0))
        pts.append(crv.GetEndPoint(1))
    return pts


def _ref_array(grids):
    arr = DB.ReferenceArray()
    for g in grids:
        arr.Append(DB.Reference(g))
    return arr


def _new_dim(doc, view, line, grids, dim_type, res):
    if len(grids) < 2:
        return
    arr = _ref_array(grids)
    try:
        if dim_type is not None:
            doc.Create.NewDimension(view, line, arr, dim_type)
        else:
            doc.Create.NewDimension(view, line, arr)
        res.created += 1
    except Exception as e:
        res.errors.append(unicode(str(e)))


def _place_pair(doc, view, grids_sorted, make_line,
                chained_val, overall_val, dim_type, res):
    """Place a chained string and (if 3+ grids) an overall string on one side.

    make_line(coord) builds the dimension line at the given offset coordinate.
    """
    _new_dim(doc, view, make_line(chained_val), grids_sorted, dim_type, res)
    if len(grids_sorted) >= 3:
        _new_dim(doc, view, make_line(overall_val),
                 [grids_sorted[0], grids_sorted[-1]], dim_type, res)


def auto_dimension(doc, view, spacing_ft, dim_type=None,
                   do_vertical=True, do_horizontal=True):
    """Create chained + overall dimension strings for the view's grids."""
    res = DimResult()
    pairs = get_view_grids(doc, view)
    if len(pairs) < 2:
        res.errors.append(u"Need at least 2 linear grids in the view.")
        return res

    verticals, horizontals = _classify(pairs)

    # ---- Vertical grids: dimension across the TOP and the BOTTOM ----
    # (dimension line is horizontal, measuring distances along X)
    if do_vertical and len(verticals) >= 2:
        verticals.sort(key=lambda p: p[1].GetEndPoint(0).X)
        pts = _endpoints(verticals)
        top_y = max(p.Y for p in pts)
        bot_y = min(p.Y for p in pts)
        min_x = min(p.X for p in pts)
        max_x = max(p.X for p in pts)
        z = verticals[0][1].GetEndPoint(0).Z
        grids_sorted = [g for g, _c in verticals]

        def make_h_line(y):
            return DB.Line.CreateBound(DB.XYZ(min_x, y, z), DB.XYZ(max_x, y, z))

        # top side: chained at +spacing, overall further out at +2*spacing
        _place_pair(doc, view, grids_sorted, make_h_line,
                    top_y + spacing_ft, top_y + 2.0 * spacing_ft, dim_type, res)
        # bottom side: chained at -spacing, overall further out at -2*spacing
        _place_pair(doc, view, grids_sorted, make_h_line,
                    bot_y - spacing_ft, bot_y - 2.0 * spacing_ft, dim_type, res)

    # ---- Horizontal grids: dimension down the RIGHT and the LEFT ----
    # (dimension line is vertical, measuring distances along Y)
    if do_horizontal and len(horizontals) >= 2:
        horizontals.sort(key=lambda p: p[1].GetEndPoint(0).Y)
        pts = _endpoints(horizontals)
        right_x = max(p.X for p in pts)
        left_x = min(p.X for p in pts)
        min_y = min(p.Y for p in pts)
        max_y = max(p.Y for p in pts)
        z = horizontals[0][1].GetEndPoint(0).Z
        grids_sorted = [g for g, _c in horizontals]

        def make_v_line(x):
            return DB.Line.CreateBound(DB.XYZ(x, min_y, z), DB.XYZ(x, max_y, z))

        # right side
        _place_pair(doc, view, grids_sorted, make_v_line,
                    right_x + spacing_ft, right_x + 2.0 * spacing_ft, dim_type, res)
        # left side
        _place_pair(doc, view, grids_sorted, make_v_line,
                    left_x - spacing_ft, left_x - 2.0 * spacing_ft, dim_type, res)

    if res.created == 0 and not res.errors:
        res.errors.append(u"No grid runs with 2+ parallel grids were found.")
    return res
