# -*- coding: utf-8 -*-
"""Turns confirmed wall(s) (wall_confirmation_prompt.py) into corridor
points for build_routing_graph (MEP_Routing_Playbook.md Sec 6/14).

Known simplification, disclosed: uses the wall's own location CENTERLINE
directly, at the caller-supplied Z, rather than offsetting perpendicular
into the wall cavity by `Standard.mep_in_wall_offset_mm` - that offset still
doesn't have a product-owner-confirmed value (MEP_SAD.md Sec 5A), and
computing the correct perpendicular offset direction for an arbitrary wall
needs its own verification before being trusted. The trunk currently runs
along the wall's centerline; a real in-wall offset is a disclosed follow-up,
not silently assumed to be zero forever.
"""

import clr

clr.AddReference("RevitAPI")


def corridor_points_from_walls(walls, z_mm):
    """walls: list[Wall], in the order the trunk should traverse them (a
    single wall is the common case; more than one is only meaningful if
    they're already end-to-end - MEP_SAD.md Sec 6's "multi-wall corridor"
    limitation, not resolved here).
    z_mm: the elevation the corridor runs at (the routing style's own
    horizontal_z_mm - ceiling void, floor void, or the fixed valve-height
    convention for in-wall routing).

    :rtype: list[(x, y, z)] - ready for build_routing_graph.
    """
    from bkbim.domain.geometry.units import ft_to_mm

    points = []
    for wall in walls:
        curve = wall.Location.Curve
        p0 = curve.GetEndPoint(0)
        p1 = curve.GetEndPoint(1)
        points.append((ft_to_mm(p0.X), ft_to_mm(p0.Y), z_mm))
        points.append((ft_to_mm(p1.X), ft_to_mm(p1.Y), z_mm))
    return points
