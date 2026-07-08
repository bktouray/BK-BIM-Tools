# -*- coding: utf-8 -*-
"""Turn CAD grid lines into native Revit grids.

Strategy
--------
1. Keep only straight lines on the chosen layer.
2. Collapse the usual CAD mess (doubled / segmented lines) by grouping
   vertical lines on a shared X and horizontal lines on a shared Y, then
   rebuilding one clean line per group spanning the full extent.
3. Create one DB.Grid per group, optionally extended past the building.
4. Auto-label: vertical grids left->right as A,B,C...; horizontal grids
   top->bottom as 1,2,3... (house convention).

IronPython 2.7.
"""

from pyrevit import DB
from bkbim.automation.cadreader import line_orientation, flatten_z
from bkbim.automation.common import column_letter
from bkbim.automation.dedup import existing_grid_lines, grid_exists


class GridResult(object):
    def __init__(self):
        self.created = 0
        self.skipped = 0
        self.exists = 0
        self.errors = []
        self.names = []


def _straight_lines(curves):
    out = []
    for c in curves:
        if isinstance(c, DB.Line):
            out.append(c)
    return out


def _group_axis_lines(lines, tol):
    """Bucket vertical lines by X and horizontal lines by Y.

    Returns (verticals, horizontals) where each is a list of dicts:
        {coord, min, max}
    'coord' is the shared X (vertical) or Y (horizontal); min/max are the
    span along the other axis so the rebuilt grid covers all segments.
    """
    vbuckets = []  # vertical: keyed on X
    hbuckets = []  # horizontal: keyed on Y

    for ln in lines:
        o = line_orientation(ln)
        p0 = ln.GetEndPoint(0)
        p1 = ln.GetEndPoint(1)
        if o == "V":
            x = (p0.X + p1.X) / 2.0
            lo = min(p0.Y, p1.Y)
            hi = max(p0.Y, p1.Y)
            _merge_into(vbuckets, x, lo, hi, tol)
        elif o == "H":
            y = (p0.Y + p1.Y) / 2.0
            lo = min(p0.X, p1.X)
            hi = max(p0.X, p1.X)
            _merge_into(hbuckets, y, lo, hi, tol)
        # diagonal lines are ignored for grid generation
    return vbuckets, hbuckets


def _merge_into(buckets, coord, lo, hi, tol):
    for b in buckets:
        if abs(b["coord"] - coord) <= tol:
            b["min"] = min(b["min"], lo)
            b["max"] = max(b["max"], hi)
            # running average keeps the coordinate stable against jitter
            b["coord"] = (b["coord"] * b["n"] + coord) / (b["n"] + 1)
            b["n"] += 1
            return
    buckets.append({"coord": coord, "min": lo, "max": hi, "n": 1})


def _unique_grid_name(doc, desired, used):
    """Grid names must be unique in the document. Suffix if needed."""
    name = desired
    i = 1
    existing = used
    while name in existing:
        i += 1
        name = u"{0}.{1}".format(desired, i)
    existing.add(name)
    return name


def generate_grids(doc, curves, extend_ft=0.0, tol=0.02, auto_number=True,
                   skip_existing=True):
    """Create Revit grids from CAD curves. Caller owns the transaction."""
    res = GridResult()
    lines = _straight_lines(curves)
    if not lines:
        res.errors.append(u"No straight lines found on this layer.")
        return res

    have = existing_grid_lines(doc) if skip_existing else []
    verticals, horizontals = _group_axis_lines(lines, tol)

    # Labelling convention (per user):
    #   vertical grids   -> letters, left -> right        (A, B, C ...)
    #   horizontal grids -> numbers, top -> bottom        (1, 2, 3 ...)
    verticals.sort(key=lambda b: b["coord"])            # ascending X = left->right
    horizontals.sort(key=lambda b: b["coord"], reverse=True)  # descending Y = top->bottom

    # Collect names already in the model so we never collide.
    used = set()
    for g in DB.FilteredElementCollector(doc).OfClass(DB.Grid).ToElements():
        used.add(g.Name)

    # Vertical grids -> letters A,B,C... (left to right)
    for i, b in enumerate(verticals):
        desired = column_letter(i) if auto_number else None
        line = DB.Line.CreateBound(
            flatten_z(DB.XYZ(b["coord"], b["min"] - extend_ft, 0.0)),
            flatten_z(DB.XYZ(b["coord"], b["max"] + extend_ft, 0.0)),
        )
        _make_grid(doc, line, desired, used, res, have)

    # Horizontal grids -> numbers 1,2,3... (top to bottom)
    for i, b in enumerate(horizontals):
        desired = unicode(i + 1) if auto_number else None
        line = DB.Line.CreateBound(
            flatten_z(DB.XYZ(b["min"] - extend_ft, b["coord"], 0.0)),
            flatten_z(DB.XYZ(b["max"] + extend_ft, b["coord"], 0.0)),
        )
        _make_grid(doc, line, desired, used, res, have)

    return res


def _make_grid(doc, line, desired_name, used, res, have):
    try:
        if line.Length < 1e-4:
            res.skipped += 1
            return
        if have and grid_exists(have, line):
            res.exists += 1
            return
        grid = DB.Grid.Create(doc, line)
        if desired_name:
            name = _unique_grid_name(doc, desired_name, used)
            try:
                grid.Name = name
            except Exception:
                # Name may still clash with an auto-name; leave Revit's default.
                name = grid.Name
            res.names.append(name)
        else:
            res.names.append(grid.Name)
        res.created += 1
    except Exception as e:
        res.errors.append(unicode(str(e)))
