# -*- coding: utf-8 -*-
"""Builds per-wall dimensioning context (bounding info + hosted-opening
locations + crossing-wall candidates) for wall-run dimensioning - extracted
2026-07-06 once Smart Dimension became a second consumer of logic that used to
live only in AutoWallOpeningDimension.pushbutton's script.py (ADR-0002: shared
helper once a 2nd consumer exists).

`exterior_wall_ids` added 2026-07-07 for the 3-string exterior-wall
perimeter dimensioning (product owner: "3 different strings going around
the footprint of the building to dimension the exterior walls"). This
project's walls don't reliably carry Revit's own Exterior/Interior
WallType.Function (confirmed live - every wall in a real mixed view reported
"Interior"), and wall type names don't distinguish it either, so "which
walls are exterior" is the caller's current UI selection, not something
this builder guesses at.
"""

from bkbim.domain.models.element_info import ElementInfo
from bkbim.revit.adapter.opening_reader import group_openings_by_host
from bkbim.revit.adapter.stable_representation import element_id_token

MIN_WALL_LENGTH_MM = 300.0


def _element_info_from_wall(wall, view):
    bb = wall.get_BoundingBox(view)
    if bb is None:
        return None
    return ElementInfo(
        ref=wall, category=u"Wall",
        min_x=bb.Min.X, max_x=bb.Max.X, min_y=bb.Min.Y, max_y=bb.Max.Y,
    )


def _wall_context(wall_info, view, openings_by_host, all_wall_infos, min_wall_length_mm, exterior_wall_ids):
    width_x = wall_info.width_x
    width_y = wall_info.width_y
    length_axis = u"x" if width_x >= width_y else u"y"
    length_ft = width_x if length_axis == u"x" else width_y
    if length_ft * 304.8 < min_wall_length_mm:
        return None

    if length_axis == u"x":
        perp_lo, perp_hi = wall_info.min_y, wall_info.max_y
    else:
        perp_lo, perp_hi = wall_info.min_x, wall_info.max_x

    this_key = element_id_token(wall_info.ref.Id)
    hosted = openings_by_host.get(this_key, [])
    opening_locations = []
    for opening in hosted:
        point = getattr(opening.Location, "Point", None)
        if point is None:
            continue
        opening_locations.append(point.X if length_axis == u"x" else point.Y)

    candidate_walls = [w for w in all_wall_infos if element_id_token(w.ref.Id) != this_key]

    return {
        u"wall_ref": wall_info.ref, u"length_axis": length_axis,
        u"perp_lo": perp_lo, u"perp_hi": perp_hi,
        u"opening_locations": opening_locations,
        u"candidate_walls": candidate_walls,
        u"is_exterior": this_key in exterior_wall_ids,
        # This wall's own overall centerpoint (both axes, not just the
        # length-axis-relative perp_lo/hi above) - 2026-07-07, lets the app
        # command work out which of its 2 sides actually faces the building's
        # exterior (see auto_wall_opening_dimension_command._outward_side).
        u"center_x": wall_info.center_x, u"center_y": wall_info.center_y,
    }


def build_walls_with_context(doc, view, dimensionable_walls, min_wall_length_mm=MIN_WALL_LENGTH_MM,
                              exterior_wall_ids=None):
    """Returns the list[dict] auto_wall_opening_dimension_command.run() expects,
    one entry per wall in `dimensionable_walls` long enough to bother with.

    exterior_wall_ids: set of element-id-token strings (see stable_representation)
        for walls that should get the 3-string exterior perimeter treatment -
        typically the user's current selection. None/empty means no wall gets
        the extra treatment (every wall falls back to the normal single-string
        behavior), not an error.
    """
    exterior_wall_ids = exterior_wall_ids or set()

    all_wall_infos = []
    for wall in dimensionable_walls:
        info = _element_info_from_wall(wall, view)
        if info is not None:
            all_wall_infos.append(info)

    openings_by_host = group_openings_by_host(doc, view)

    walls_with_context = []
    for wall_info in all_wall_infos:
        ctx = _wall_context(wall_info, view, openings_by_host, all_wall_infos, min_wall_length_mm, exterior_wall_ids)
        if ctx is not None:
            walls_with_context.append(ctx)

    return walls_with_context
