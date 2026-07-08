# -*- coding: utf-8 -*-
"""Detect double-line walls in CAD geometry and build Revit walls.

CAD walls are usually drawn as two parallel face lines. This module pairs
parallel, overlapping segments that sit within a plausible wall thickness,
recovers the centre line and thickness of each, groups them by thickness, and
builds Revit walls - optionally auto-generating a single-layer wall type per
thickness, bound between a base and top level.

IronPython 2.7.
"""

from pyrevit import DB

_MM = 304.8


def _snap(v, step):
    return int(round(v / step) * step)


class WallRun(object):
    def __init__(self, center_line, thickness_ft):
        self.center = center_line       # DB.Line, flattened to z = 0
        self.thickness_ft = thickness_ft

    def thickness_mm(self, snap=5.0):
        return _snap(self.thickness_ft * _MM, snap)


# ---------------------------------------------------------------------------
# Detection - pair parallel face lines into centre lines
# ---------------------------------------------------------------------------

def extract_wall_runs(curves, max_thickness_ft=1.5, min_thickness_ft=0.03,
                      min_overlap_ft=0.1):
    """Pair parallel CAD face lines into centre lines -> [WallRun]."""
    segs = [c for c in curves if isinstance(c, DB.Line) and c.Length > 0.05]
    info = []
    for s in segs:
        p0 = s.GetEndPoint(0)
        p1 = s.GetEndPoint(1)
        u = (p1 - p0).Normalize()
        info.append((p0, p1, u, s.Length))

    n = len(segs)
    used = [False] * n
    runs = []
    for i in range(n):
        if used[i]:
            continue
        p0i, p1i, ui, li = info[i]
        ni = DB.XYZ(-ui.Y, ui.X, 0.0)
        best = None
        for j in range(n):
            if j == i or used[j]:
                continue
            p0j, p1j, uj, lj = info[j]
            if abs(abs(ui.DotProduct(uj)) - 1.0) > 1e-2:
                continue  # not parallel
            dperp = (p0j - p0i).DotProduct(ni)
            ad = abs(dperp)
            if ad < min_thickness_ft or ad > max_thickness_ft:
                continue
            sj0 = (p0j - p0i).DotProduct(ui)
            sj1 = (p1j - p0i).DotProduct(ui)
            smin = max(0.0, min(sj0, sj1))
            smax = min(li, max(sj0, sj1))
            if smax - smin < min_overlap_ft:
                continue  # not enough shared length
            if best is None or ad < best[0]:
                best = (ad, j, smin, smax, dperp)
        if best is None:
            continue
        ad, j, smin, smax, dperp = best
        used[i] = True
        used[j] = True
        cs = p0i + ui * smin + ni * (dperp / 2.0)
        ce = p0i + ui * smax + ni * (dperp / 2.0)
        cs = DB.XYZ(cs.X, cs.Y, 0.0)
        ce = DB.XYZ(ce.X, ce.Y, 0.0)
        if cs.DistanceTo(ce) > min_overlap_ft:
            runs.append(WallRun(DB.Line.CreateBound(cs, ce), ad))
    return runs


def _try_merge(l1, l2, tol):
    """Merge two collinear, touching lines into one; else None."""
    a0, a1 = l1.GetEndPoint(0), l1.GetEndPoint(1)
    b0, b1 = l2.GetEndPoint(0), l2.GetEndPoint(1)
    d1 = (a1 - a0).Normalize()
    d2 = (b1 - b0).Normalize()
    if abs(abs(d1.DotProduct(d2)) - 1.0) > 1e-3:
        return None  # not parallel
    nrm = DB.XYZ(-d1.Y, d1.X, 0.0)
    if abs((b0 - a0).DotProduct(nrm)) > tol:
        return None  # parallel but offset -> not collinear

    def close(p, q):
        return p.DistanceTo(q) <= tol
    if close(a1, b0):
        return DB.Line.CreateBound(a0, b1)
    if close(a1, b1):
        return DB.Line.CreateBound(a0, b0)
    if close(a0, b0):
        return DB.Line.CreateBound(a1, b1)
    if close(a0, b1):
        return DB.Line.CreateBound(a1, b0)
    return None


def merge_collinear(lines, tol=0.02):
    """Join collinear, connected segments (e.g. exploded polylines) into runs."""
    work = list(lines)
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(work):
            j = i + 1
            while j < len(work):
                m = _try_merge(work[i], work[j], tol)
                if m is not None:
                    work[i] = m
                    work.pop(j)
                    changed = True
                else:
                    j += 1
            i += 1
    return work


def extract_centerlines(curves, tol=0.02):
    """Treat each CAD line as a wall centre line -> [WallRun] (thickness 0)."""
    lines = [c for c in curves if isinstance(c, DB.Line) and c.Length > 0.05]
    runs = []
    for ln in merge_collinear(lines, tol):
        a = ln.GetEndPoint(0)
        b = ln.GetEndPoint(1)
        a = DB.XYZ(a.X, a.Y, 0.0)
        b = DB.XYZ(b.X, b.Y, 0.0)
        if a.DistanceTo(b) > 0.1:
            runs.append(WallRun(DB.Line.CreateBound(a, b), 0.0))
    return runs


def group_by_thickness(runs, snap=5.0):
    """Return [(thickness_mm, [WallRun,...]), ...] sorted by thickness."""
    buckets = {}
    for r in runs:
        buckets.setdefault(r.thickness_mm(snap), []).append(r)
    rows = list(buckets.items())
    rows.sort(key=lambda kv: kv[0])
    return rows


# ---------------------------------------------------------------------------
# Wall types
# ---------------------------------------------------------------------------

def _name(el):
    try:
        return el.Name
    except Exception:
        return DB.Element.Name.__get__(el)


def basic_wall_types(doc):
    """dict {name -> WallType} of basic (editable) wall types."""
    out = {}
    for wt in DB.FilteredElementCollector(doc).OfClass(DB.WallType).ToElements():
        try:
            if wt.Kind == DB.WallKind.Basic:
                out[_name(wt)] = wt
        except Exception:
            pass
    return out


def get_or_create_wall_type(doc, base_type, thickness_ft, material_id,
                            snap, cache):
    """Single-layer wall type sized to thickness_ft, created once."""
    key = _snap(thickness_ft * _MM, snap)
    if key in cache:
        return cache[key]
    wanted = u"{0}mm".format(key)
    for wt in DB.FilteredElementCollector(doc).OfClass(DB.WallType).ToElements():
        if _name(wt) == wanted:
            cache[key] = wt
            return wt
    try:
        new_t = base_type.Duplicate(wanted)
        mat = material_id if material_id is not None \
            else DB.ElementId.InvalidElementId
        cs = DB.CompoundStructure.CreateSingleLayerCompoundStructure(
            DB.MaterialFunctionAssignment.Structure, thickness_ft, mat)
        new_t.SetCompoundStructure(cs)
        cache[key] = new_t
        return new_t
    except Exception:
        cache[key] = base_type
        return base_type


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------

class WallResult(object):
    def __init__(self):
        self.placed = 0
        self.skipped = 0
        self.errors = []


def place_walls(doc, runs_by_type, base_level, top_level, structural=False,
                location_line=None, skip_existing=True):
    """Place walls. runs_by_type: list of (WallType, [WallRun,...]).

    location_line: a DB.WallLocationLine (e.g. WallCenterline, CoreCenterline)
    controlling which reference of the wall sits on the CAD line. Used to honor
    'parallel lines are finish vs core faces'.
    """
    from bkbim.automation.dedup import existing_wall_lines, segment_overlaps_existing
    res = WallResult()
    have = existing_wall_lines(doc) if skip_existing else []
    for wt, runs in runs_by_type:
        if wt is None:
            continue
        for run in runs:
            try:
                if skip_existing and segment_overlaps_existing(have, run.center):
                    res.skipped += 1
                    continue
                w = DB.Wall.Create(doc, run.center, wt.Id, base_level.Id,
                                   10.0, 0.0, False, structural)
                _set(w, DB.BuiltInParameter.WALL_BASE_CONSTRAINT, base_level.Id)
                _set(w, DB.BuiltInParameter.WALL_HEIGHT_TYPE, top_level.Id)
                _set_d(w, DB.BuiltInParameter.WALL_TOP_OFFSET, 0.0)
                _set_d(w, DB.BuiltInParameter.WALL_BASE_OFFSET, 0.0)
                if location_line is not None:
                    _set_i(w, DB.BuiltInParameter.WALL_KEY_REF_PARAM,
                           int(location_line))
                have.append(run.center)
                res.placed += 1
            except Exception as e:
                res.errors.append(unicode(str(e)))
    return res


def _set_i(elem, bip, value):
    try:
        p = elem.get_Parameter(bip)
        if p is not None and not p.IsReadOnly:
            p.Set(value)
    except Exception:
        pass


def _set(elem, bip, value_id):
    try:
        p = elem.get_Parameter(bip)
        if p is not None and not p.IsReadOnly:
            p.Set(value_id)
    except Exception:
        pass


def _set_d(elem, bip, value):
    try:
        p = elem.get_Parameter(bip)
        if p is not None and not p.IsReadOnly:
            p.Set(value)
    except Exception:
        pass
