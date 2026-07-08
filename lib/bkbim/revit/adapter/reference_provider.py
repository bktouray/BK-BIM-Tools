# -*- coding: utf-8 -*-
"""Implements IReferenceProvider against live Revit geometry (SAD Sec 4.3).

Orthogonal (axis-aligned) faces only for this iteration, matching the planner's
axis-aligned assumption (PHASE_1_PLAN Stage 3) - curved/angled walls are an explicit,
known, deferred scope, not silently mishandled.

Two element shapes need different handling:
- Solid-backed elements (walls): faces come directly from get_Geometry() with
  working References.
- FamilyInstance-backed elements (columns): get_Geometry() gives correct WORLD
  coordinates via a GeometryInstance + Transform, but its face References do not
  work for NewDimension. The fix is to read faces from GetSymbolGeometry() instead
  (stable, type-level References) and rewrite the stable representation's leading
  element-id token from the type id to the instance id. This is a real, independently
  verifiable Revit API fact - re-verified live against this project's model, not
  assumed correct because a similar technique appears in third-party code.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import GeometryInstance, Line, Options, PlanarFace, Reference, Solid
from Autodesk.Revit.DB import FamilyInstance

from bkbim.domain.dimensioning.ports import IWallRunReader
from bkbim.domain.models.axis_faces import AxisFaces
from bkbim.domain.models.outline_edge import OutlineEdge
from bkbim.domain.references.ports import IReferenceProvider
from bkbim.revit.adapter.stable_representation import (
    element_id_token,
    rewrite_stable_representation_element_id,
)


class RevitReferenceProvider(IReferenceProvider, IWallRunReader):
    def __init__(self, doc, view):
        self._doc = doc
        self._view = view

    def faces_for(self, element_ref, axis):
        element = element_ref
        opt = Options()
        opt.ComputeReferences = True
        opt.IncludeNonVisibleObjects = False
        opt.View = self._view

        geo = element.get_Geometry(opt)
        if geo is None:
            return None

        is_family = isinstance(element, FamilyInstance)
        faces = []

        for item in geo:
            if isinstance(item, GeometryInstance) and is_family:
                faces.extend(self._family_faces(item, element, axis))
            elif isinstance(item, Solid) and item.Faces.Size > 0:
                faces.extend(self._solid_faces(item, axis))

        if len(faces) < 2:
            return None

        faces.sort(key=lambda pair: pair[1])
        lo_ref, lo_coord = faces[0]
        hi_ref, hi_coord = faces[-1]
        return AxisFaces(ref_lo=lo_ref, ref_hi=hi_ref, coord_lo=lo_coord, coord_hi=hi_coord)

    def _solid_faces(self, solid, axis):
        result = []
        for face in solid.Faces:
            if not isinstance(face, PlanarFace):
                continue
            ref = face.Reference
            if ref is None:
                continue
            n = face.FaceNormal
            if axis == "x" and abs(n.X) > 0.9:
                result.append((ref, face.Origin.X))
            elif axis == "y" and abs(n.Y) > 0.9:
                result.append((ref, face.Origin.Y))
        return result

    def _family_faces(self, geom_instance, instance_element, axis):
        result = []
        xform = geom_instance.Transform
        sym_geo = geom_instance.GetSymbolGeometry()
        if sym_geo is None:
            return result

        for sym_item in sym_geo:
            if not isinstance(sym_item, Solid) or sym_item.Faces.Size == 0:
                continue
            for face in sym_item.Faces:
                if not isinstance(face, PlanarFace):
                    continue
                sym_ref = face.Reference
                if sym_ref is None:
                    continue
                world_normal = xform.OfVector(face.FaceNormal)
                world_origin = xform.OfPoint(face.Origin)
                inst_ref = self._symbol_ref_to_instance_ref(sym_ref, instance_element)
                if inst_ref is None:
                    continue
                if axis == "x" and abs(world_normal.X) > 0.9:
                    result.append((inst_ref, world_origin.X))
                elif axis == "y" and abs(world_normal.Y) > 0.9:
                    result.append((inst_ref, world_origin.Y))
        return result

    def _symbol_ref_to_instance_ref(self, sym_ref, instance_element):
        try:
            stable = sym_ref.ConvertToStableRepresentation(self._doc)
            new_stable = rewrite_stable_representation_element_id(
                stable, element_id_token(instance_element.Id))
            return Reference.ParseFromStableRepresentation(self._doc, new_stable)
        except Exception:
            return None

    def wall_run_faces(self, wall_ref, length_axis, opening_locations):
        wall = wall_ref
        opt = Options()
        opt.ComputeReferences = True
        opt.IncludeNonVisibleObjects = False
        opt.View = self._view

        geo = wall.get_Geometry(opt)
        if geo is None:
            return None, [None] * len(opening_locations)

        # (coord, normal_sign, Reference) for every planar face whose normal runs
        # along the wall's own length axis - this includes the wall's two outer end
        # faces AND, for every opening cut into the wall, the reveal faces bounding
        # that opening's void. Compound walls (multiple layers) can produce more
        # than one near-duplicate reveal face per opening side (core vs finish
        # layer) - handled below by picking the closest bracketing pair to each
        # opening's known location, not by trying to deduplicate geometrically.
        faces = []
        for item in geo:
            if not (isinstance(item, Solid) and item.Faces.Size > 0):
                continue
            for face in item.Faces:
                if not isinstance(face, PlanarFace):
                    continue
                ref = face.Reference
                if ref is None:
                    continue
                n = face.FaceNormal
                if length_axis == "x" and abs(n.X) > 0.9:
                    faces.append((face.Origin.X, 1 if n.X > 0 else -1, ref))
                elif length_axis == "y" and abs(n.Y) > 0.9:
                    faces.append((face.Origin.Y, 1 if n.Y > 0 else -1, ref))

        if len(faces) < 2:
            return None, [None] * len(opening_locations)

        faces.sort(key=lambda f: f[0])
        wall_axis_faces = AxisFaces(
            ref_lo=faces[0][2], ref_hi=faces[-1][2],
            coord_lo=faces[0][0], coord_hi=faces[-1][0],
        )

        # A void's near jamb (lower coord) faces outward (+X/+Y, away from the
        # solid material beside it); its far jamb (higher coord) faces the
        # opposite way (-X/-Y) - the wall's own outer end faces have the reverse
        # pattern, so they're naturally excluded from being picked as a "near" or
        # "far" jamb candidate here.
        near_candidates = [(c, r) for c, sign, r in faces if sign > 0]
        far_candidates = [(c, r) for c, sign, r in faces if sign < 0]

        opening_axis_faces_list = []
        for location in opening_locations:
            near_side = [(c, r) for c, r in near_candidates if c < location]
            far_side = [(c, r) for c, r in far_candidates if c > location]
            if not near_side or not far_side:
                opening_axis_faces_list.append(None)
                continue
            near_coord, near_ref = max(near_side, key=lambda p: p[0])
            far_coord, far_ref = min(far_side, key=lambda p: p[0])
            opening_axis_faces_list.append(AxisFaces(
                ref_lo=near_ref, ref_hi=far_ref, coord_lo=near_coord, coord_hi=far_coord,
            ))

        return wall_axis_faces, opening_axis_faces_list

    def outline_edges_for(self, element_ref):
        element = element_ref
        opt = Options()
        opt.ComputeReferences = True
        opt.IncludeNonVisibleObjects = False
        opt.View = self._view

        geo = element.get_Geometry(opt)
        if geo is None:
            return []

        edges = []
        for item in geo:
            if isinstance(item, Solid) and item.Faces.Size > 0:
                edges.extend(self._outline_edges_from_solid(item))
        return edges

    def _outline_edges_from_solid(self, solid):
        result = []
        for face in solid.Faces:
            if not isinstance(face, PlanarFace):
                continue
            n = face.FaceNormal
            if abs(n.Z) > 0.5:
                continue  # skip top/bottom horizontal faces

            if abs(n.X) > 0.9:
                axis, sign = u"x", (1 if n.X > 0 else -1)
            elif abs(n.Y) > 0.9:
                axis, sign = u"y", (1 if n.Y > 0 else -1)
            else:
                continue  # diagonal/angled side face - unsupported, skip

            ref = face.Reference
            if ref is None:
                continue

            try:
                bbox = face.GetBoundingBox()
                p_min = face.Evaluate(bbox.Min)
                p_max = face.Evaluate(bbox.Max)
            except Exception:
                continue

            if axis == u"x":
                coord = face.Origin.X
                span_lo, span_hi = sorted([p_min.Y, p_max.Y])
            else:
                coord = face.Origin.Y
                span_lo, span_hi = sorted([p_min.X, p_max.X])

            result.append(OutlineEdge(ref=ref, axis=axis, coord=coord,
                                       span_lo=span_lo, span_hi=span_hi, sign=sign))
        return result

    def grid_reference(self, grid_ref):
        grid = grid_ref
        try:
            opt = Options()
            opt.ComputeReferences = True
            opt.IncludeNonVisibleObjects = True
            opt.View = self._view
            geo = grid.get_Geometry(opt)
            if geo:
                for item in geo:
                    if isinstance(item, Line) and item.Reference:
                        return item.Reference
            crv = grid.Curve
            if crv is not None and crv.Reference:
                return crv.Reference
        except Exception:
            pass
        return None
