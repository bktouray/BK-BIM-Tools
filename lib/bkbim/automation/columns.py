# -*- coding: utf-8 -*-
"""Detect column rectangles in CAD geometry and place Revit columns.

Detection works purely on straight line segments (cadreader already explodes
PolyLines into segments), so it handles columns drawn either as closed
polylines or as four separate lines. Connected segments are grouped into
closed loops; a 4-corner loop is a rectangular column, from which we recover
the section size (short x long), centre point, and rotation.

Placement creates Revit structural or architectural columns, optionally
auto-generating a correctly sized family type per distinct CAD section
("Auto-Generate from CAD"), bound between a base and top level.

IronPython 2.7 - no f-strings, no Python 3 stdlib.
"""

import math
from pyrevit import DB

_MM = 304.8  # mm per foot


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

class Rect(object):
    def __init__(self, center, short_ft, long_ft, angle):
        self.center = center        # DB.XYZ, z carried from CAD
        self.short_ft = short_ft    # smaller section dimension (b)
        self.long_ft = long_ft      # larger section dimension (h)
        self.angle = angle          # radians, direction of the LONG side

    def size_mm(self, snap=5.0):
        s = _snap(self.short_ft * _MM, snap)
        l = _snap(self.long_ft * _MM, snap)
        return (s, l)


def _snap(v, step):
    return int(round(v / step) * step)


def _node_key(pt, tol):
    return (int(round(pt.X / tol)), int(round(pt.Y / tol)))


def extract_rectangles(lines, tol=0.02):
    """Group connected line segments into closed rectangles -> [Rect]."""
    segs = [s for s in lines if isinstance(s, DB.Line)]
    n = len(segs)
    if n == 0:
        return []

    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    node_map = {}
    seg_nodes = []
    for idx, s in enumerate(segs):
        a = _node_key(s.GetEndPoint(0), tol)
        b = _node_key(s.GetEndPoint(1), tol)
        seg_nodes.append((a, b))
        node_map.setdefault(a, []).append(idx)
        node_map.setdefault(b, []).append(idx)

    for _node, idxs in node_map.items():
        first = idxs[0]
        for j in range(1, len(idxs)):
            union(first, idxs[j])

    comps = {}
    for idx in range(n):
        comps.setdefault(find(idx), []).append(idx)

    rects = []
    for _root, idxs in comps.items():
        pts = []
        deg = {}
        for idx in idxs:
            a, b = seg_nodes[idx]
            deg[a] = deg.get(a, 0) + 1
            deg[b] = deg.get(b, 0) + 1
            pts.append(segs[idx].GetEndPoint(0))
            pts.append(segs[idx].GetEndPoint(1))
        closed = len(deg) > 0 and all(d == 2 for d in deg.values())
        if not closed:
            continue
        corners = _cluster(pts, tol)
        if len(corners) == 4:
            r = _rect_from_corners(corners)
        elif len(corners) >= 4:
            r = _rect_from_bbox(corners)
        else:
            r = None
        if r is not None:
            rects.append(r)
    return rects


def _cluster(pts, tol):
    out = []
    for p in pts:
        dup = False
        for q in out:
            if abs(p.X - q.X) <= tol and abs(p.Y - q.Y) <= tol:
                dup = True
                break
        if not dup:
            out.append(p)
    return out


def _rect_from_corners(c):
    cx = sum(p.X for p in c) / 4.0
    cy = sum(p.Y for p in c) / 4.0
    cz = sum(p.Z for p in c) / 4.0
    order = sorted(c, key=lambda p: math.atan2(p.Y - cy, p.X - cx))
    e0 = order[1] - order[0]
    e1 = order[2] - order[1]
    a = e0.GetLength()
    b = e1.GetLength()
    if a <= 1e-6 or b <= 1e-6:
        return None
    if a >= b:
        long_v, long_d, short_v = a, e0, b
    else:
        long_v, long_d, short_v = b, e1, a
    angle = math.atan2(long_d.Y, long_d.X)
    return Rect(DB.XYZ(cx, cy, cz), short_v, long_v, angle)


def _rect_from_bbox(c):
    xs = [p.X for p in c]
    ys = [p.Y for p in c]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    if w <= 1e-6 or h <= 1e-6:
        return None
    center = DB.XYZ((max(xs) + min(xs)) / 2.0,
                    (max(ys) + min(ys)) / 2.0, c[0].Z)
    if w >= h:
        return Rect(center, h, w, 0.0)
    return Rect(center, w, h, math.pi / 2.0)


def group_by_size(rects, snap=5.0):
    """Return [((short_mm,long_mm), [Rect,...]), ...] sorted by size."""
    buckets = {}
    for r in rects:
        buckets.setdefault(r.size_mm(snap), []).append(r)
    rows = list(buckets.items())
    rows.sort(key=lambda kv: (kv[0][0], kv[0][1]))
    return rows


# ---------------------------------------------------------------------------
# Family types
# ---------------------------------------------------------------------------

def _name(el):
    try:
        return el.Name
    except Exception:
        return DB.Element.Name.__get__(el)


# Common (b, h) parameter name pairs across rectangular column families.
_BH_NAMES = [("b", "h"), ("Width", "Depth"), ("w", "d"),
             ("B", "H"), ("Width", "Height")]


def _set_bh(symbol, short_ft, long_ft):
    """Try to write the section dimensions onto a duplicated type."""
    for bname, hname in _BH_NAMES:
        pb = symbol.LookupParameter(bname)
        ph = symbol.LookupParameter(hname)
        if pb is not None and ph is not None and not pb.IsReadOnly and not ph.IsReadOnly:
            try:
                pb.Set(short_ft)
                ph.Set(long_ft)
                return True
            except Exception:
                return False
    return False


def get_or_create_sized_type(doc, base_symbol, short_ft, long_ft, snap, cache):
    """Return a family symbol sized to (short,long), creating it once."""
    key = (_snap(short_ft * _MM, snap), _snap(long_ft * _MM, snap))
    if key in cache:
        return cache[key]
    # Type name is the section size in millimetres only, e.g. "200x500mm".
    wanted = u"{0}x{1}mm".format(key[0], key[1])

    fam = base_symbol.Family
    for tid in fam.GetFamilySymbolIds():
        s = doc.GetElement(tid)
        if _name(s) == wanted:
            cache[key] = s
            return s

    try:
        new_id_el = base_symbol.Duplicate(wanted)
    except Exception:
        cache[key] = base_symbol
        return base_symbol
    new_sym = new_id_el if isinstance(new_id_el, DB.FamilySymbol) \
        else doc.GetElement(new_id_el.Id)
    _set_bh(new_sym, short_ft, long_ft)
    cache[key] = new_sym
    return new_sym


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------

class ColumnResult(object):
    def __init__(self):
        self.placed = 0
        self.skipped = 0
        self.errors = []


def place_columns(doc, rects_by_type, base_level, top_level,
                  structural=True, material_id=None, skip_existing=True):
    """Place columns. rects_by_type: list of (family_symbol, [Rect,...]).

    material_id (DB.ElementId or None) is applied to every column.
    skip_existing: don't place where a column already sits (smart detect).
    """
    from bkbim.automation.dedup import existing_instance_points, point_exists
    res = ColumnResult()
    st = (DB.Structure.StructuralType.Column if structural
          else DB.Structure.StructuralType.NonStructural)
    bic = (DB.BuiltInCategory.OST_StructuralColumns if structural
           else DB.BuiltInCategory.OST_Columns)
    existing = existing_instance_points(doc, bic) if skip_existing else []

    for symbol, rects in rects_by_type:
        if symbol is None:
            continue
        if not symbol.IsActive:
            symbol.Activate()
            doc.Regenerate()
        # Material is usually a type parameter - set it once per type.
        _apply_material(None, symbol, material_id)
        for r in rects:
            try:
                if skip_existing and point_exists(existing, r.center):
                    res.skipped += 1
                    continue
                pt = DB.XYZ(r.center.X, r.center.Y, base_level.Elevation)
                inst = doc.Create.NewFamilyInstance(pt, symbol, base_level, st)
                _set_level(inst, DB.BuiltInParameter.FAMILY_BASE_LEVEL_PARAM,
                           base_level.Id)
                _set_level(inst, DB.BuiltInParameter.FAMILY_TOP_LEVEL_PARAM,
                           top_level.Id)
                _apply_material(inst, symbol, material_id)
                # rotate so the family's depth (h) aligns with the long side
                angle = r.angle - math.pi / 2.0
                if abs(angle) > 1e-6:
                    axis = DB.Line.CreateBound(pt, pt + DB.XYZ(0, 0, 1))
                    DB.ElementTransformUtils.RotateElement(
                        doc, inst.Id, axis, angle)
                existing.append(r.center)
                res.placed += 1
            except Exception as e:
                res.errors.append(unicode(str(e)))
    return res


def _apply_material(inst, symbol, material_id):
    """Set the structural material on the instance, falling back to the type."""
    if material_id is None:
        return
    # 1) instance-level structural material
    if inst is not None:
        try:
            p = inst.get_Parameter(DB.BuiltInParameter.STRUCTURAL_MATERIAL_PARAM)
            if p is not None and not p.IsReadOnly:
                p.Set(material_id)
                return
        except Exception:
            pass
    # 2) type-level material parameter (by common names)
    if symbol is not None:
        for pn in (u"Structural Material", u"Material", u"Column Material"):
            sp = symbol.LookupParameter(pn)
            if sp is not None and not sp.IsReadOnly:
                try:
                    sp.Set(material_id)
                    return
                except Exception:
                    pass


def _set_level(inst, bip, level_id):
    try:
        p = inst.get_Parameter(bip)
        if p is not None and not p.IsReadOnly:
            p.Set(level_id)
    except Exception:
        pass
