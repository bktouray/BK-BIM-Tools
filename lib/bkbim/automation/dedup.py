# -*- coding: utf-8 -*-
"""Smart-detection helpers: skip CAD features already built in the model.

Every generator checks new geometry against what already exists in the Revit
model (not a saved ledger), so re-running a tool after adding new CAD lines
only creates the *new* elements - no duplicates, no overlaps. It also avoids
clashing with elements the user modelled by hand.

IronPython 2.7.
"""

from pyrevit import DB


# --- point-based (columns, doors, windows) -------------------------------

def existing_instance_points(doc, bic):
    pts = []
    col = (DB.FilteredElementCollector(doc).OfClass(DB.FamilyInstance)
           .OfCategory(bic).WhereElementIsNotElementType().ToElements())
    for fi in col:
        loc = fi.Location
        if isinstance(loc, DB.LocationPoint):
            pts.append(loc.Point)
    return pts


def point_exists(points, pt, tol=0.5):
    for p in points:
        if abs(p.X - pt.X) <= tol and abs(p.Y - pt.Y) <= tol:
            return True
    return False


# --- line-based (grids, walls) -------------------------------------------

def _parallel(a, b):
    da = (a.GetEndPoint(1) - a.GetEndPoint(0)).Normalize()
    db = (b.GetEndPoint(1) - b.GetEndPoint(0)).Normalize()
    return abs(abs(da.DotProduct(db)) - 1.0) <= 1e-2, da


def existing_grid_lines(doc):
    out = []
    for g in DB.FilteredElementCollector(doc).OfClass(DB.Grid).ToElements():
        try:
            c = g.Curve
            if isinstance(c, DB.Line):
                out.append(c)
        except Exception:
            pass
    return out


def grid_exists(existing, line, tol=0.1):
    """A grid already lies on the same infinite line (any overlap)."""
    for e in existing:
        ok, da = _parallel(e, line)
        if not ok:
            continue
        n = DB.XYZ(-da.Y, da.X, 0.0)
        if abs((e.GetEndPoint(0) - line.GetEndPoint(0)).DotProduct(n)) <= tol:
            return True
    return False


def existing_wall_lines(doc):
    out = []
    walls = (DB.FilteredElementCollector(doc).OfClass(DB.Wall)
             .WhereElementIsNotElementType().ToElements())
    for w in walls:
        loc = w.Location
        if isinstance(loc, DB.LocationCurve) and isinstance(loc.Curve, DB.Line):
            out.append(loc.Curve)
    return out


def segment_overlaps_existing(existing, line, perp_tol=0.1, min_overlap=0.5):
    """A wall already lies collinear with and overlapping `line`."""
    a0 = line.GetEndPoint(0)
    a1 = line.GetEndPoint(1)
    da = (a1 - a0).Normalize()
    n = DB.XYZ(-da.Y, da.X, 0.0)
    la = (a1 - a0).GetLength()
    for e in existing:
        ok, _d = _parallel(e, line)
        if not ok:
            continue
        b0 = e.GetEndPoint(0)
        b1 = e.GetEndPoint(1)
        if abs((b0 - a0).DotProduct(n)) > perp_tol:
            continue  # parallel but offset
        sb0 = (b0 - a0).DotProduct(da)
        sb1 = (b1 - a0).DotProduct(da)
        lo = max(0.0, min(sb0, sb1))
        hi = min(la, max(sb0, sb1))
        if hi - lo > min_overlap:
            return True
    return False


# --- area-based (floors) --------------------------------------------------

def existing_floor_centroids(doc, level_id=None):
    cs = []
    floors = (DB.FilteredElementCollector(doc).OfClass(DB.Floor)
              .WhereElementIsNotElementType().ToElements())
    for f in floors:
        if level_id is not None:
            try:
                if f.LevelId != level_id:
                    continue
            except Exception:
                pass
        bb = f.get_BoundingBox(None)
        if bb is not None:
            cs.append(DB.XYZ((bb.Min.X + bb.Max.X) / 2.0,
                             (bb.Min.Y + bb.Max.Y) / 2.0, 0.0))
    return cs


def centroid_exists(centroids, pt, tol=1.0):
    for c in centroids:
        if abs(c.X - pt.X) <= tol and abs(c.Y - pt.Y) <= tol:
            return True
    return False
