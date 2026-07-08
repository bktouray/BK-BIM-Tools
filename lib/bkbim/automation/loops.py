# -*- coding: utf-8 -*-
"""Build ordered closed loops from loose CAD curves.

Slab/room/ceiling outlines come in as a bag of disconnected, arbitrarily
oriented segments. This module walks them into ordered, head-to-tail closed
loops (preserving arcs), works out which loops sit inside which (so inner
loops become openings), and hands back Revit CurveLoops ready for
Floor.Create and friends.

Reused by Floors, Ceilings, Slab Footings and Rooms.

IronPython 2.7.
"""

from pyrevit import DB


def _key(p, tol):
    return (int(round(p.X / tol)), int(round(p.Y / tol)))


def build_loops(curves, tol=0.02):
    """Walk curves into closed loops.

    Returns a list of dicts: {"curves": [oriented DB.Curve...],
                              "pts": [DB.XYZ vertices...]}.
    """
    segs = [c for c in curves if c is not None and c.Length > tol]
    n = len(segs)
    if n == 0:
        return []

    nodes = []
    node_to = {}
    for i, c in enumerate(segs):
        a = _key(c.GetEndPoint(0), tol)
        b = _key(c.GetEndPoint(1), tol)
        nodes.append((a, b))
        node_to.setdefault(a, []).append(i)
        node_to.setdefault(b, []).append(i)

    used = set()
    loops = []
    for s in range(n):
        if s in used:
            continue
        a, b = nodes[s]
        chain = [(s, a)]          # (segment index, node we enter the seg from)
        used.add(s)
        start, current = a, b
        closed = False
        guard = 0
        while guard <= n + 2:
            guard += 1
            if current == start:
                closed = True
                break
            nxt = None
            nextnode = None
            for idx in node_to.get(current, []):
                if idx in used:
                    continue
                x, y = nodes[idx]
                if x == current:
                    nxt, nextnode = idx, y
                    break
                if y == current:
                    nxt, nextnode = idx, x
                    break
            if nxt is None:
                break
            used.add(nxt)
            chain.append((nxt, current))
            current = nextnode
        if closed and len(chain) >= 3:
            lp = _finalize(segs, chain, tol)
            if lp is not None:
                loops.append(lp)
    return loops


def _finalize(segs, chain, tol):
    oriented = []
    pts = []
    for idx, entry in chain:
        c = segs[idx]
        if _key(c.GetEndPoint(0), tol) == entry:
            oriented.append(c)
            pts.append(c.GetEndPoint(0))
        else:
            oriented.append(c.CreateReversed())
            pts.append(c.GetEndPoint(1))
    return {"curves": oriented, "pts": pts}


def flatten_curves(loop, z=0.0):
    """Return the loop's curves translated to a constant elevation z."""
    out = []
    for c in loop["curves"]:
        zc = c.GetEndPoint(0).Z
        if abs(zc - z) > 1e-9:
            t = DB.Transform.CreateTranslation(DB.XYZ(0, 0, z - zc))
            out.append(c.CreateTransformed(t))
        else:
            out.append(c)
    return out


def to_curveloop(curves):
    cl = DB.CurveLoop()
    for c in curves:
        cl.Append(c)
    return cl


def loop_area(loop):
    p = loop["pts"]
    n = len(p)
    s = 0.0
    for i in range(n):
        j = (i + 1) % n
        s += p[i].X * p[j].Y - p[j].X * p[i].Y
    return abs(s) / 2.0


def _point_in_poly(pt, poly_pts):
    x, y = pt.X, pt.Y
    inside = False
    n = len(poly_pts)
    j = n - 1
    for i in range(n):
        xi, yi = poly_pts[i].X, poly_pts[i].Y
        xj, yj = poly_pts[j].X, poly_pts[j].Y
        if ((yi > y) != (yj > y)) and \
                (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def point_in_poly(pt, poly_pts):
    """Public wrapper: is XYZ pt inside the polygon given by poly_pts (XY)?"""
    return _point_in_poly(pt, poly_pts)


def curveloop_from_points(pts, z=None):
    """Build a closed DB.CurveLoop of straight lines through pts."""
    cl = DB.CurveLoop()
    n = len(pts)
    for i in range(n):
        a = pts[i]
        b = pts[(i + 1) % n]
        if z is not None:
            a = DB.XYZ(a.X, a.Y, z)
            b = DB.XYZ(b.X, b.Y, z)
        cl.Append(DB.Line.CreateBound(a, b))
    return cl


def group_loops(loops):
    """Group loops into (outer, [holes]); inner loops become openings.

    A loop is a hole if its first vertex falls inside a larger loop.
    """
    order = sorted(loops, key=loop_area, reverse=True)
    assigned = set()
    groups = []
    for outer in order:
        if id(outer) in assigned:
            continue
        holes = []
        for inner in order:
            if inner is outer or id(inner) in assigned:
                continue
            if _point_in_poly(inner["pts"][0], outer["pts"]):
                holes.append(inner)
                assigned.add(id(inner))
        assigned.add(id(outer))
        groups.append((outer, holes))
    return groups
