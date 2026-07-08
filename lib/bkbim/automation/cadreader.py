# -*- coding: utf-8 -*-
"""Read geometry out of imported / linked CAD (DWG) instances.

This is the foundation of every automation tool: each button picks a
CAD *layer* and turns the geometry on that layer into native Revit elements.
The functions here hand back plain geometry (curves, points, closed loops) in
Revit model coordinates (internal feet) so the tool scripts stay simple.

IronPython 2.7 — no f-strings, no Python 3 stdlib.
"""

from pyrevit import DB
from bkbim.automation.common import normalize_string

# A geometry object whose layer can't be resolved gets bucketed under this.
_NO_LAYER = u"<no layer>"


def get_import_instances(doc):
    """Return all ImportInstance elements (DWG imports and links) in the doc."""
    return list(
        DB.FilteredElementCollector(doc)
        .OfClass(DB.ImportInstance)
        .WhereElementIsNotElementType()
        .ToElements()
    )


def _geometry_options():
    opt = DB.Options()
    opt.ComputeReferences = False
    opt.IncludeNonVisibleObjects = False
    opt.DetailLevel = DB.ViewDetailLevel.Fine
    return opt


def _layer_name(doc, geom_obj):
    """Resolve the CAD layer name of a geometry object via its GraphicsStyle."""
    try:
        gsid = geom_obj.GraphicsStyleId
    except Exception:
        return _NO_LAYER
    if gsid is None or gsid == DB.ElementId.InvalidElementId:
        return _NO_LAYER
    gs = doc.GetElement(gsid)
    if gs is None:
        return _NO_LAYER
    try:
        cat = gs.GraphicsStyleCategory
    except Exception:
        cat = None
    if cat is None:
        return _NO_LAYER
    return normalize_string(cat.Name)


def _iter_geometry(geom_element):
    """Yield leaf geometry objects, expanding GeometryInstances to world coords."""
    if geom_element is None:
        return
    for g in geom_element:
        if isinstance(g, DB.GeometryInstance):
            # GetInstanceGeometry() returns the geometry already transformed
            # into model coordinates (internal feet) — exactly what we want.
            inst = g.GetInstanceGeometry()
            for ig in _iter_geometry(inst):
                yield ig
        else:
            yield g


def collect_by_layer(doc, import_instance):
    """Group every curve on an import instance by CAD layer name.

    Returns a dict: { layer_name -> [DB.Curve, ...] }. PolyLines are exploded
    into their straight segments so downstream tools only deal with Curves.
    """
    result = {}
    geo = import_instance.get_Geometry(_geometry_options())
    for g in _iter_geometry(geo):
        layer = _layer_name(doc, g)
        curves = _as_curves(g)
        if not curves:
            continue
        result.setdefault(layer, []).extend(curves)
    return result


def _as_curves(geom_obj):
    """Normalize a geometry object into a list of DB.Curve."""
    if isinstance(geom_obj, DB.Curve):
        return [geom_obj]
    if isinstance(geom_obj, DB.PolyLine):
        pts = list(geom_obj.GetCoordinates())
        segs = []
        i = 0
        while i < len(pts) - 1:
            p0 = pts[i]
            p1 = pts[i + 1]
            if p0.DistanceTo(p1) > 1e-7:
                segs.append(DB.Line.CreateBound(p0, p1))
            i += 1
        return segs
    return []


def list_layers(doc, import_instance):
    """Return a sorted list of (layer_name, curve_count) for a CAD import."""
    grouped = collect_by_layer(doc, import_instance)
    rows = [(name, len(curves)) for name, curves in grouped.items()]
    rows.sort(key=lambda r: r[0].lower())
    return rows


def curves_on_layer(doc, import_instance, layer_name):
    """All curves on a single named layer of a single import instance."""
    grouped = collect_by_layer(doc, import_instance)
    return grouped.get(layer_name, [])


def all_curves_on_layer(doc, layer_name):
    """All curves on a named layer across every import instance in the doc."""
    out = []
    for inst in get_import_instances(doc):
        out.extend(curves_on_layer(doc, inst, layer_name))
    return out


# ---------------------------------------------------------------------------
# Geometry classification helpers used by several tools.
# ---------------------------------------------------------------------------


def flatten_z(pt, z=0.0):
    return DB.XYZ(pt.X, pt.Y, z)


def line_orientation(line, tol=1e-6):
    """Classify a straight line as 'V' (vertical), 'H' (horizontal) or 'D'."""
    d = line.GetEndPoint(1) - line.GetEndPoint(0)
    if abs(d.X) <= tol and abs(d.Y) > tol:
        return "V"
    if abs(d.Y) <= tol and abs(d.X) > tol:
        return "H"
    # near-axis tolerance: snap lines that are mostly axis-aligned
    if abs(d.X) < abs(d.Y) * 1e-3:
        return "V"
    if abs(d.Y) < abs(d.X) * 1e-3:
        return "H"
    return "D"
