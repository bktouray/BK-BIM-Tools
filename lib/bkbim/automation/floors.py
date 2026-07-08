# -*- coding: utf-8 -*-
"""Create Revit floors from closed CAD slab outlines.

Each outer loop on the chosen layer becomes a floor; loops nested inside it
become openings. Uses the modern Floor.Create API (Revit 2022+).

IronPython 2.7.
"""

from System.Collections.Generic import List
from pyrevit import DB

from bkbim.automation.loops import (
    build_loops, group_loops, flatten_curves, to_curveloop,
    point_in_poly, curveloop_from_points,
)


class FloorResult(object):
    def __init__(self):
        self.placed = 0
        self.openings = 0
        self.skipped = 0
        self.errors = []


def _wall_core_footprint(wall):
    """Rectangle (4 XYZ corners) of a straight wall's structural CORE layers."""
    loc = wall.Location
    if not isinstance(loc, DB.LocationCurve):
        return None
    crv = loc.Curve
    if not isinstance(crv, DB.Line):
        return None
    core = None
    try:
        cs = wall.WallType.GetCompoundStructure()
        if cs is not None:
            i0 = cs.GetFirstCoreLayerIndex()
            i1 = cs.GetLastCoreLayerIndex()
            core = 0.0
            for i in range(i0, i1 + 1):
                core += cs.GetLayerWidth(i)
    except Exception:
        core = None
    if not core or core <= 1e-6:
        core = wall.Width
    p0 = crv.GetEndPoint(0)
    p1 = crv.GetEndPoint(1)
    d = p1 - p0
    if d.GetLength() <= 1e-9:
        return None
    d = d.Normalize()
    nrm = DB.XYZ(-d.Y, d.X, 0.0)
    h = core / 2.0
    return [p0 + nrm * h, p1 + nrm * h, p1 - nrm * h, p0 - nrm * h]


def wall_core_footprints(doc, level_id):
    """Core-face footprints of straight walls based on the given level."""
    out = []
    walls = (DB.FilteredElementCollector(doc).OfClass(DB.Wall)
             .WhereElementIsNotElementType().ToElements())
    matched = []
    for w in walls:
        try:
            bp = w.get_Parameter(DB.BuiltInParameter.WALL_BASE_CONSTRAINT)
            if bp is not None and bp.AsElementId() == level_id:
                matched.append(w)
        except Exception:
            pass
    # If none are explicitly on this level, consider all walls.
    use = matched if matched else walls
    for w in use:
        fp = _wall_core_footprint(w)
        if fp:
            out.append(fp)
    return out


def create_floors(doc, curves, floor_type_id, level_id, offset_ft=0.0,
                  subtract_walls=False, skip_existing=True):
    """Create floors from CAD curves. Caller owns the transaction.

    subtract_walls: when True, interior walls (fully inside a floor loop) are
    cut out as openings at their structural core face.
    skip_existing: don't create a floor where one already covers that area.
    """
    from bkbim.automation.dedup import existing_floor_centroids, centroid_exists
    res = FloorResult()
    loops = build_loops(curves)
    if not loops:
        res.errors.append(u"No closed slab outlines found on this layer.")
        return res

    level = doc.GetElement(level_id)
    z = level.Elevation if level is not None else 0.0
    wall_fps = wall_core_footprints(doc, level_id) if subtract_walls else []
    have = existing_floor_centroids(doc, level_id) if skip_existing else []

    for outer, holes in group_loops(loops):
        try:
            pts = outer["pts"]
            cx = sum(p.X for p in pts) / len(pts)
            cy = sum(p.Y for p in pts) / len(pts)
            if skip_existing and centroid_exists(have, DB.XYZ(cx, cy, 0.0)):
                res.skipped += 1
                continue
            profile = List[DB.CurveLoop]()
            profile.Add(to_curveloop(flatten_curves(outer, z)))
            for h in holes:
                profile.Add(to_curveloop(flatten_curves(h, z)))
            # interior walls -> openings at the core face
            if subtract_walls:
                for fp in wall_fps:
                    if all(point_in_poly(c, outer["pts"]) for c in fp):
                        profile.Add(curveloop_from_points(fp, z))
                        res.openings += 1
            floor = DB.Floor.Create(doc, profile, floor_type_id, level_id)
            if offset_ft and floor is not None:
                p = floor.get_Parameter(
                    DB.BuiltInParameter.FLOOR_HEIGHTABOVELEVEL_PARAM)
                if p is not None and not p.IsReadOnly:
                    p.Set(offset_ft)
            res.placed += 1
        except Exception as e:
            res.errors.append(unicode(str(e)))
    return res
