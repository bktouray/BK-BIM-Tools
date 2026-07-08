# -*- coding: utf-8 -*-
"""Detects exterior walls without manual picking (product owner, 2026-07-08:
"is it possible to just autodetect the building boundary, or do I have to
differentiate exterior and interior walls?"). Two methods, picked
automatically per view:

- Room-based (primary): if the view has Room elements placed, sample a point
  just off each side of every wall and ask Revit directly
  (doc.GetRoomAtPoint) whether a Room encloses that side. A wall with a Room
  on only one side (or neither) is exterior.
- Geometry fallback: if the view has no Rooms, delegate to
  exterior_wall_classifier.classify_by_boundary_trace, which treats the wall
  network itself as an implicit polygon boundary.

Returns the same contract as the manual picker in wall_selection_prompt.py -
a set of element_id_token strings - so build_walls_with_context needs no
changes to accept either source.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector, LocationCurve, XYZ

from bkbim.domain.dimensioning.exterior_wall_classifier import (
    classify_by_boundary_trace,
    classify_by_room_adjacency,
    perpendicular_sample_points,
)
from bkbim.revit.adapter.stable_representation import element_id_token

# Clears the wall's own thickness band before sampling a side - a Room's
# boundary sits at the wall face, not the centerline, so a small clearance
# past the half-width is enough to land inside/outside the Room reliably.
_ROOM_SAMPLE_CLEARANCE_FT = 0.5

# The geometry fallback has no Room boundary to lean on, so it needs a wider
# clearance to reliably clear a NEIGHBORING wall's own thickness band too,
# not just the sampled wall's own.
_BOUNDARY_TRACE_CLEARANCE_FT = 1.5


def detect_exterior_walls(doc, view, dimensionable_walls):
    """Returns a set of element_id_token strings for auto-detected exterior
    walls. Empty is a normal outcome (classification found nothing), never
    an error - matches pick_exterior_walls' convention.
    """
    rooms_in_view = FilteredElementCollector(doc, view.Id).OfCategory(
        BuiltInCategory.OST_Rooms).WhereElementIsNotElementType().ToElements()
    if list(rooms_in_view):
        return _detect_via_rooms(doc, dimensionable_walls)
    return _detect_via_geometry(dimensionable_walls)


def _wall_endpoints(wall):
    location = wall.Location
    if not isinstance(location, LocationCurve):
        return None
    curve = location.Curve
    return curve.GetEndPoint(0), curve.GetEndPoint(1)


def _detect_via_rooms(doc, dimensionable_walls):
    room_sides = {}
    for wall in dimensionable_walls:
        endpoints = _wall_endpoints(wall)
        if endpoints is None:
            continue
        p1, p2 = endpoints
        half_width_ft = wall.Width / 2.0
        point_a, point_b = perpendicular_sample_points(
            p1.X, p1.Y, p2.X, p2.Y, half_width_ft + _ROOM_SAMPLE_CLEARANCE_FT)
        z = (p1.Z + p2.Z) / 2.0
        room_a = doc.GetRoomAtPoint(XYZ(point_a[0], point_a[1], z))
        room_b = doc.GetRoomAtPoint(XYZ(point_b[0], point_b[1], z))
        room_sides[element_id_token(wall.Id)] = (room_a is not None, room_b is not None)

    return classify_by_room_adjacency(room_sides)


def _detect_via_geometry(dimensionable_walls):
    wall_segments = []
    for wall in dimensionable_walls:
        endpoints = _wall_endpoints(wall)
        if endpoints is None:
            continue
        p1, p2 = endpoints
        half_width_ft = wall.Width / 2.0
        wall_segments.append((
            element_id_token(wall.Id), p1.X, p1.Y, p2.X, p2.Y, half_width_ft))

    return classify_by_boundary_trace(wall_segments, offset_ft=_BOUNDARY_TRACE_CLEARANCE_FT)
