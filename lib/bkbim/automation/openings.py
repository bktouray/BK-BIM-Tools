# -*- coding: utf-8 -*-
"""Detect door/window openings in CAD and place wall-hosted families.

Each opening is drawn as two parallel CAD lines; the distance between them is
the opening WIDTH and the midpoint is the insertion point. Openings are
grouped by width, placed into the host wall found beneath each point, at a
chosen level, with a chosen / auto-sized family type and a lintel (head)
height.

Reuses the parallel-line pairing from walls.py.

IronPython 2.7.
"""

from pyrevit import DB
from bkbim.automation.walls import extract_wall_runs
from bkbim.automation.dedup import existing_instance_points, point_exists

_MM = 304.8


def _snap(v, step):
    return int(round(v / step) * step)


def _name(el):
    try:
        return el.Name
    except Exception:
        return DB.Element.Name.__get__(el)


class Opening(object):
    def __init__(self, center, width_ft):
        self.center = center        # DB.XYZ (z = 0)
        self.width_ft = width_ft

    def width_mm(self, snap=5.0):
        return _snap(self.width_ft * _MM, snap)


def extract_openings(curves, max_width_ft, min_width_ft=0.3):
    """Pair parallel CAD lines -> openings (distance between lines = width)."""
    runs = extract_wall_runs(curves, max_thickness_ft=max_width_ft,
                             min_thickness_ft=min_width_ft, min_overlap_ft=0.02)
    ops = []
    for r in runs:
        c0 = r.center.GetEndPoint(0)
        c1 = r.center.GetEndPoint(1)
        mid = DB.XYZ((c0.X + c1.X) / 2.0, (c0.Y + c1.Y) / 2.0, 0.0)
        ops.append(Opening(mid, r.thickness_ft))
    return ops


def extract_openings_from_markers(curves, min_width_ft=0.3):
    """Centre-line marker mode: each line = one opening (length = width).

    Robust for sliding doors / closely-spaced openings - the user draws one
    line per opening spanning jamb to jamb on a dedicated marker layer.
    """
    ops = []
    for c in curves:
        if not isinstance(c, DB.Line):
            continue
        if c.Length < min_width_ft:
            continue
        a = c.GetEndPoint(0)
        b = c.GetEndPoint(1)
        mid = DB.XYZ((a.X + b.X) / 2.0, (a.Y + b.Y) / 2.0, 0.0)
        ops.append(Opening(mid, c.Length))
    return ops


def group_by_width(ops, snap=5.0):
    """Return [(width_mm, [Opening,...]), ...] sorted by width."""
    buckets = {}
    for o in ops:
        buckets.setdefault(o.width_mm(snap), []).append(o)
    rows = list(buckets.items())
    rows.sort(key=lambda kv: kv[0])
    return rows


def find_host_wall(doc, point, max_dist_ft=2.0):
    """Nearest wall whose location curve passes under `point` (XY)."""
    best = None
    best_d = max_dist_ft + 1.0
    walls = (DB.FilteredElementCollector(doc).OfClass(DB.Wall)
             .WhereElementIsNotElementType().ToElements())
    for w in walls:
        loc = w.Location
        if not isinstance(loc, DB.LocationCurve):
            continue
        crv = loc.Curve
        try:
            p = DB.XYZ(point.X, point.Y, crv.GetEndPoint(0).Z)
            res = crv.Project(p)
        except Exception:
            res = None
        if res is None:
            continue
        d = res.Distance
        if d < best_d and d <= max_dist_ft:
            best_d = d
            best = w
    return best


# Width / Height are TYPE parameters on most door/window families.
_W_NAMES = (u"Width", u"width", u"W", u"Rough Width")
_H_NAMES = (u"Height", u"height", u"H", u"Rough Height")


def _set_first(symbol, names, value_ft):
    for nm in names:
        p = symbol.LookupParameter(nm)
        if p is not None and not p.IsReadOnly:
            try:
                p.Set(value_ft)
                return True
            except Exception:
                pass
    return False


def get_or_create_sized_symbol(doc, base_symbol, width_ft, height_ft, snap, cache):
    """Family symbol sized to width x height, created once from base family."""
    wkey = _snap(width_ft * _MM, snap)
    hkey = _snap(height_ft * _MM, snap)
    key = (wkey, hkey)
    if key in cache:
        return cache[key]
    wanted = u"{0}x{1}mm".format(wkey, hkey)
    fam = base_symbol.Family
    for tid in fam.GetFamilySymbolIds():
        s = doc.GetElement(tid)
        if _name(s) == wanted:
            cache[key] = s
            return s
    try:
        new_el = base_symbol.Duplicate(wanted)
        ns = new_el if isinstance(new_el, DB.FamilySymbol) \
            else doc.GetElement(new_el.Id)
        _set_first(ns, _W_NAMES, width_ft)
        _set_first(ns, _H_NAMES, height_ft)
        cache[key] = ns
        return ns
    except Exception:
        cache[key] = base_symbol
        return base_symbol


class OpeningResult(object):
    def __init__(self):
        self.placed = 0
        self.no_host = 0
        self.skipped = 0
        self.errors = []


def place_openings(doc, ops_by_symbol, level, lintel_ft=None,
                   skip_existing=True, bic=None):
    """Place wall-hosted openings. ops_by_symbol: [(FamilySymbol,[Opening])].

    skip_existing: don't place where a door/window already sits (smart detect).
    """
    res = OpeningResult()
    existing = existing_instance_points(doc, bic) if (skip_existing and bic) else []
    placed = []  # list of (instance, host_wall)
    HEAD = DB.BuiltInParameter.INSTANCE_HEAD_HEIGHT_PARAM

    # --- Phase 1: create every instance (no head height yet) ---
    for symbol, ops in ops_by_symbol:
        if symbol is None:
            continue
        if not symbol.IsActive:
            symbol.Activate()
            doc.Regenerate()
        for o in ops:
            try:
                if skip_existing and point_exists(existing, o.center):
                    res.skipped += 1
                    continue
                host = find_host_wall(doc, o.center)
                if host is None:
                    res.no_host += 1
                    continue
                pt = DB.XYZ(o.center.X, o.center.Y, level.Elevation)
                inst = doc.Create.NewFamilyInstance(
                    pt, symbol, host, level,
                    DB.Structure.StructuralType.NonStructural)
                placed.append((inst, host))
                existing.append(o.center)
                res.placed += 1
            except Exception as e:
                res.errors.append(unicode(str(e)))

    if not placed:
        return res

    # --- Phase 2: realize the wall cuts, THEN set head heights ---
    # The cut must regenerate before the head height changes, else the opening
    # is left stale and does not survive the commit (openings look un-cut).
    doc.Regenerate()
    if lintel_ft is not None:
        for inst, _h in placed:
            p = inst.get_Parameter(HEAD)
            if p is not None and not p.IsReadOnly:
                p.Set(lintel_ft)
        doc.Regenerate()

    # --- Phase 3: SELF-HEAL - verify every opening actually cut its wall and
    # force-fix any that didn't (nudging the head height forces the host cut to
    # recompute). Guards against engine-timing quirks that leave a stale cut.
    def _not_cutting(inst, host):
        try:
            return isinstance(host, DB.Wall) and inst.Id not in \
                list(host.FindInserts(True, False, True, True))
        except Exception:
            return False

    stuck = [(i, h) for (i, h) in placed if _not_cutting(i, h)]
    if stuck:
        for inst, _h in stuck:
            p = inst.get_Parameter(HEAD)
            if p is not None and not p.IsReadOnly:
                p.Set(p.AsDouble() + 0.02)
        doc.Regenerate()
        for inst, _h in stuck:
            p = inst.get_Parameter(HEAD)
            if p is not None and not p.IsReadOnly:
                p.Set(p.AsDouble() - 0.02)
        doc.Regenerate()
    return res
