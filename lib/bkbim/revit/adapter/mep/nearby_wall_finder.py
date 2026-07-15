# -*- coding: utf-8 -*-
"""Finds which wall each fixture sits closest to (product owner request,
2026-07-10, alongside room selection). Informational only for now - NOT
wired into routing (MEP_SAD.md Sec 5's direct-point-to-point routing is
unchanged); this exists so a future options window can show "this WC is
against the North wall" and so routing-along-a-wall can be built later once
this detection itself has been used and trusted, matching the same
ship-the-read-before-the-write discipline as every other adapter here.

Uses `Curve.Project()` on each wall's own location line - a standard, low-
risk Revit API technique already used elsewhere in this suite's dimensioning
tools for point-to-curve proximity, not a new/speculative geometry approach.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector, Wall, XYZ

from bkbim.domain.geometry.units import ft_to_mm, mm_to_ft
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.stable_representation import element_id_token

DEFAULT_MAX_DISTANCE_MM = 1500.0  # ~1.5m - generous for "is this against a wall"


class NearestWall(object):
    def __init__(self, wall_ref, wall_type_name, distance_mm):
        self.wall_ref = wall_ref
        self.wall_type_name = wall_type_name
        self.distance_mm = distance_mm

    def __repr__(self):
        return u"<NearestWall {0} at {1}mm>".format(self.wall_type_name, round(self.distance_mm, 1))


def _collect_walls(doc):
    elements = (FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Walls)
                .WhereElementIsNotElementType().ToElements())
    return [w for w in elements if isinstance(w, Wall)]


def find_nearest_wall(doc, point_mm, walls=None, max_distance_mm=DEFAULT_MAX_DISTANCE_MM):
    """point_mm: (x, y, z) tuple. Returns a NearestWall, or None if nothing
    is within max_distance_mm.

    Measures HORIZONTAL (plan) distance only. A wall's location curve is a
    flat line at the wall's base elevation - Curve.Project's literal 3D
    distance to that line conflates a connector's actual height above the
    floor with its true proximity to the wall's vertical plane. Real bug
    caught live 2026-07-10: a shower valve connector 1100mm up reported
    "1101.1mm from the nearest wall" purely from that height, when its real
    horizontal distance (confirmed against a same-room fixture at the
    matching true ~100mm) was consistent with being mounted on the same wall
    as the adjacent shower drain. Fixed by flattening the query point onto
    the curve's own Z before projecting, so height never contributes.
    """
    if walls is None:
        walls = _collect_walls(doc)

    nearest_wall = None
    nearest_dist_ft = None
    for w in walls:
        try:
            curve = w.Location.Curve
        except Exception:
            continue
        try:
            curve_z = curve.GetEndPoint(0).Z
            flattened_point = XYZ(mm_to_ft(point_mm[0]), mm_to_ft(point_mm[1]), curve_z)
            result = curve.Project(flattened_point)
            dist_ft = result.Distance
        except Exception:
            continue
        if nearest_dist_ft is None or dist_ft < nearest_dist_ft:
            nearest_dist_ft = dist_ft
            nearest_wall = w

    if nearest_wall is None:
        return None
    dist_mm = ft_to_mm(nearest_dist_ft)
    if dist_mm > max_distance_mm:
        return None
    return NearestWall(wall_ref=nearest_wall.Id, wall_type_name=type_name(nearest_wall),
                        distance_mm=dist_mm)


def find_nearest_walls_for_fixtures(doc, fixtures, max_distance_mm=DEFAULT_MAX_DISTANCE_MM):
    """fixtures: list[FixtureInfo] (uses each fixture's first connector
    position as its location - close enough for "which wall is this fixture
    against", not precise host-face detection).

    :rtype: dict {element_id_token(fixture.ref): NearestWall or None}
    """
    walls = _collect_walls(doc)
    result = {}
    for fixture in fixtures:
        if not fixture.connectors:
            result[element_id_token(fixture.ref)] = None
            continue
        point_mm = fixture.connectors[0].position
        result[element_id_token(fixture.ref)] = find_nearest_wall(
            doc, point_mm, walls=walls, max_distance_mm=max_distance_mm)
    return result
