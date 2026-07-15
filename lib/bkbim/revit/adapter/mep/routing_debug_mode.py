# -*- coding: utf-8 -*-
"""Routing Debug Mode (MEP_Routing_Playbook.md Sec 13): visualizes a
RoutingGraph's decisions in the active view BEFORE any real pipe geometry
exists. Not yet gated behind a Developer Mode setting - that concept doesn't
exist in `bkbim.core.settings` yet (Sec 19's known limitation); callable
directly for now.

Design choice, disclosed: draws temporary `ModelCurve` elements (real 3D
curves, findable/deletable, visible in any view whose range includes them),
not a true ephemeral/immediate-mode overlay - implementing genuine frame-by-
frame overlay graphics would need a full `IDirectContext3DServer`, a much
larger undertaking than this phase calls for.

`DetailCurve` was tried first and rejected live: it requires the curve to
lie exactly in the HOST VIEW's own cut-plane, so a vertical branch segment
(or even a horizontal one at a different elevation than the view's own Z)
throws "Curve must be in the plane." `ModelCurve` has no such restriction -
it needs a `SketchPlane` that merely CONTAINS the line (any line has
infinitely many), computed per-line via a direction cross-product, not tied
to whatever view happens to be active. This means Debug Mode output may not
be visible in the SAME 2D plan view that triggered it if a segment's
elevation falls outside that view's view range - a 3D view or a section
shows everything regardless.

Tagging via a Comments parameter was tried next and also rejected live:
`ModelLine` does not expose `BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS`
at all (`get_Parameter` returns None). Fixed by having `show_debug_graphics`
return the created ElementIds directly - the caller owns tracking/clearing
exactly those, which is simpler and more robust than searching the model for
a tag that may not exist on every element type anyway.

Colors match the product owner's own convention: corridor=blue, trunk=green,
branches=yellow, junctions=red, valve origin=purple.

Covers the core visual overlay only - per-element text labels (segment/
branch/junction IDs, estimated lengths, future pipe size/system type) are
NOT implemented yet, disclosed as a scope cut, not silently dropped.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import Color, Line, OverrideGraphicSettings, Plane, SketchPlane, XYZ

COLOR_CORRIDOR = Color(0, 80, 220)     # blue
COLOR_TRUNK = Color(0, 160, 0)         # green
COLOR_BRANCH = Color(220, 190, 0)      # yellow
COLOR_JUNCTION = Color(220, 0, 0)      # red
COLOR_ORIGIN = Color(140, 0, 200)      # purple

_MARKER_SIZE_MM = 100.0

# Revit's own ShortCurveTolerance rejects near-zero curves - same real issue
# and same fix as pipe_geometry_writer.py's _MIN_PIPE_LENGTH_MM, hit again
# here live 2026-07-10 drawing a near-zero branch segment (the same WC
# segment Phase 2 already skips for the same reason).
_MIN_LINE_LENGTH_MM = 10.0


def _mm_to_xyz(point_mm):
    from bkbim.domain.geometry.units import mm_to_ft
    return XYZ(mm_to_ft(point_mm[0]), mm_to_ft(point_mm[1]), mm_to_ft(point_mm[2]))


def _sketch_plane_containing_line(doc, start, end):
    direction = (end - start).Normalize()
    # Any vector not parallel to `direction` works as a cross-product seed -
    # try X first, fall back to Y if the line itself runs along X.
    seed = XYZ(1, 0, 0) if abs(direction.X) < 0.9 else XYZ(0, 1, 0)
    normal = direction.CrossProduct(seed).Normalize()
    plane = Plane.CreateByNormalAndOrigin(normal, start)
    return SketchPlane.Create(doc, plane)


def _draw_line(doc, view, start_mm, end_mm, color):
    length_mm = ((end_mm[0] - start_mm[0]) ** 2 + (end_mm[1] - start_mm[1]) ** 2 +
                 (end_mm[2] - start_mm[2]) ** 2) ** 0.5
    if length_mm < _MIN_LINE_LENGTH_MM:
        return None
    start, end = _mm_to_xyz(start_mm), _mm_to_xyz(end_mm)
    line = Line.CreateBound(start, end)
    sketch_plane = _sketch_plane_containing_line(doc, start, end)
    model_curve = doc.Create.NewModelCurve(line, sketch_plane)

    override = OverrideGraphicSettings()
    override.SetProjectionLineColor(color)
    override.SetProjectionLineWeight(6)
    view.SetElementOverrides(model_curve.Id, override)
    return model_curve


def _draw_marker(doc, view, point_mm, color, size_mm=_MARKER_SIZE_MM):
    """A small X-cross at a point - used for junctions/origin, which are
    points, not lines. Returns the created elements (0-2, since near-zero
    legs are skipped by _draw_line the same as anywhere else).
    """
    half = size_mm / 2.0
    a = (point_mm[0] - half, point_mm[1] - half, point_mm[2])
    b = (point_mm[0] + half, point_mm[1] + half, point_mm[2])
    c = (point_mm[0] - half, point_mm[1] + half, point_mm[2])
    d = (point_mm[0] + half, point_mm[1] - half, point_mm[2])
    created = [_draw_line(doc, view, a, b, color), _draw_line(doc, view, c, d, color)]
    return [e for e in created if e is not None]


def show_debug_graphics(doc, view, routing_graph):
    """Draws the corridor, trunk, every branch, every junction, and the
    origin - caller owns the Transaction (SAD Sec 4.4), same convention as
    every other writer in this codebase.

    :rtype: list[ElementId] - every element created, so the caller can clear
    exactly these later via clear_debug_graphics(doc, element_ids).
    """
    created = []

    corridor_points = routing_graph.corridor.points
    for i in range(len(corridor_points) - 1):
        e = _draw_line(doc, view, corridor_points[i], corridor_points[i + 1], COLOR_CORRIDOR)
        if e is not None:
            created.append(e)

    trunk_points = routing_graph.trunk_points
    for i in range(len(trunk_points) - 1):
        e = _draw_line(doc, view, trunk_points[i], trunk_points[i + 1], COLOR_TRUNK)
        if e is not None:
            created.append(e)

    for junction, branch in routing_graph.junctions:
        for segment in branch.segments:
            e = _draw_line(doc, view, segment.start_point, segment.end_point, COLOR_BRANCH)
            if e is not None:
                created.append(e)
        created.extend(_draw_marker(doc, view, junction.position, COLOR_JUNCTION))

    created.extend(_draw_marker(doc, view, routing_graph.origin.position, COLOR_ORIGIN,
                                 size_mm=_MARKER_SIZE_MM * 1.5))

    return [e.Id for e in created]


def clear_debug_graphics(doc, element_ids):
    """Deletes exactly the elements `show_debug_graphics` returned - no
    searching, no tag matching. Caller owns the Transaction.
    """
    removed = 0
    for element_id in element_ids:
        try:
            doc.Delete(element_id)
            removed += 1
        except Exception:
            continue
    return removed
