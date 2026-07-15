# -*- coding: utf-8 -*-
"""Convert Floor elements into isolated structural foundations.

Some imported models (e.g. from Tekla Structural Designer) represent pad
footings as Floors instead of native Revit Structural Foundations. This
groups floors by their bounding-box footprint size (length x width x
thickness), auto-generates a correctly sized isolated footing type per
distinct size from a chosen base family, places one footing per floor at
the floor's own level/position/elevation, applies a chosen structural
material, and optionally deletes the source floor.

Footprint is always the floor's plan bounding box - for a non-rectangular
floor this is an approximation (same disclosed convention this suite
already uses for Slab Dimensions' bounding-box mode), not a true
outline-tracing conversion.

IronPython 2.7.
"""

from pyrevit import DB

_MM = 304.8  # mm per foot

# Common dimension-parameter name triples across rectangular isolated
# footing families (Length, Width, Foundation Thickness) - tried in order,
# first fully-writable match wins. Falls back to leaving the duplicated
# type unsized if none match (still usable, just not auto-sized).
DIM_NAMES = [
    (u"Length", u"Width", u"Foundation Thickness"),
    (u"Length", u"Width", u"Thickness"),
    (u"Width", u"Length", u"Foundation Thickness"),
    (u"B", u"L", u"T"),
]


def _name(el):
    try:
        return el.Name
    except Exception:
        return DB.Element.Name.__get__(el)


def _snap(v, step):
    return int(round(v / step) * step)


# ---------------------------------------------------------------------------
# Floor footprint / sizing
# ---------------------------------------------------------------------------

def _floor_thickness_ft(floor):
    p = floor.LookupParameter(u"Thickness")
    if p is not None:
        try:
            return p.AsDouble()
        except Exception:
            pass
    bbox = floor.get_BoundingBox(None)
    if bbox is not None:
        return max(bbox.Max.Z - bbox.Min.Z, 0.0)
    return 0.0


def _floor_height_offset_ft(floor):
    try:
        p = floor.get_Parameter(DB.BuiltInParameter.FLOOR_HEIGHTABOVELEVEL_PARAM)
        if p is not None:
            return p.AsDouble()
    except Exception:
        pass
    p2 = floor.LookupParameter(u"Height Offset From Level")
    if p2 is not None:
        try:
            return p2.AsDouble()
        except Exception:
            pass
    return 0.0


def floor_bbox_footprint(floor):
    """Plan bounding-box footprint: {length_ft, width_ft, center_x, center_y,
    thickness_ft, height_offset_ft}, or None if degenerate.
    """
    bbox = floor.get_BoundingBox(None)
    if bbox is None:
        return None
    length_ft = bbox.Max.X - bbox.Min.X
    width_ft = bbox.Max.Y - bbox.Min.Y
    if length_ft <= 1e-6 or width_ft <= 1e-6:
        return None
    return {
        u"length_ft": length_ft,
        u"width_ft": width_ft,
        u"center_x": (bbox.Max.X + bbox.Min.X) / 2.0,
        u"center_y": (bbox.Max.Y + bbox.Min.Y) / 2.0,
        u"thickness_ft": _floor_thickness_ft(floor),
        u"height_offset_ft": _floor_height_offset_ft(floor),
    }


def group_floors_by_size(floors, snap=5.0):
    """Return [((length_mm, width_mm, thickness_mm), [Floor,...]), ...],
    sorted by size. Floors with a degenerate footprint are silently
    excluded (caller sees them missing from every group's floor list).
    """
    buckets = {}
    for f in floors:
        fp = floor_bbox_footprint(f)
        if fp is None:
            continue
        key = (
            _snap(fp[u"length_ft"] * _MM, snap),
            _snap(fp[u"width_ft"] * _MM, snap),
            _snap(fp[u"thickness_ft"] * _MM, snap),
        )
        buckets.setdefault(key, []).append(f)
    rows = list(buckets.items())
    rows.sort(key=lambda kv: (kv[0][0], kv[0][1], kv[0][2]))
    return rows


# ---------------------------------------------------------------------------
# Footing types
# ---------------------------------------------------------------------------

def set_dimensions(symbol, length_ft, width_ft, thickness_ft):
    for lname, wname, tname in DIM_NAMES:
        pl = symbol.LookupParameter(lname)
        pw = symbol.LookupParameter(wname)
        pt = symbol.LookupParameter(tname)
        if (pl is not None and pw is not None and pt is not None
                and not pl.IsReadOnly and not pw.IsReadOnly and not pt.IsReadOnly):
            try:
                pl.Set(length_ft)
                pw.Set(width_ft)
                pt.Set(thickness_ft)
                return True
            except Exception:
                return False
    return False


def get_or_create_sized_footing_type(doc, base_symbol, length_ft, width_ft, thickness_ft, snap, cache):
    """Return a footing family symbol sized to (length, width, thickness),
    creating (and naming) it once per distinct size. Falls back to
    `base_symbol` unsized if duplication or dimension-writing fails.
    """
    key = (
        _snap(length_ft * _MM, snap),
        _snap(width_ft * _MM, snap),
        _snap(thickness_ft * _MM, snap),
    )
    if key in cache:
        return cache[key]

    wanted = u"{0} - {1}x{2}x{3}mm".format(_name(base_symbol.Family), key[0], key[1], key[2])

    fam = base_symbol.Family
    for tid in fam.GetFamilySymbolIds():
        s = doc.GetElement(tid)
        if _name(s) == wanted:
            cache[key] = s
            return s

    try:
        new_id_el = base_symbol.Duplicate(wanted)
    except Exception:
        cache[key] = base_symbol
        return base_symbol
    new_sym = new_id_el if isinstance(new_id_el, DB.FamilySymbol) else doc.GetElement(new_id_el.Id)
    set_dimensions(new_sym, length_ft, width_ft, thickness_ft)
    cache[key] = new_sym
    return new_sym


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------

class FootingResult(object):
    def __init__(self):
        self.placed = 0
        self.skipped = 0
        self.errors = []


def set_height_offset(inst, value_ft):
    p = inst.LookupParameter(u"Height Offset From Level")
    if p is not None and not p.IsReadOnly:
        try:
            p.Set(value_ft)
        except Exception:
            pass


def apply_footing_material(inst, symbol, material_id):
    """Set the structural material on the instance, falling back to the type."""
    if material_id is None:
        return
    if inst is not None:
        try:
            p = inst.get_Parameter(DB.BuiltInParameter.STRUCTURAL_MATERIAL_PARAM)
            if p is not None and not p.IsReadOnly:
                p.Set(material_id)
                return
        except Exception:
            pass
    if symbol is not None:
        for pn in (u"Structural Material", u"Material"):
            sp = symbol.LookupParameter(pn)
            if sp is not None and not sp.IsReadOnly:
                try:
                    sp.Set(material_id)
                    return
                except Exception:
                    pass


def _copy_mark(floor, inst):
    fp = floor.LookupParameter(u"Mark")
    if fp is None:
        return
    try:
        value = fp.AsString()
    except Exception:
        return
    if not value:
        return
    ip = inst.LookupParameter(u"Mark")
    if ip is not None and not ip.IsReadOnly:
        try:
            ip.Set(value)
        except Exception:
            pass


def place_footings(doc, floors_by_type, material_id=None, delete_source_floors=True):
    """Place isolated footings. floors_by_type: list of (family_symbol, [Floor,...]).

    Each footing is hosted on ITS OWN floor's level (not a single shared
    level), positioned at the floor's plan-bbox center, at the floor's own
    Height Offset From Level. material_id (DB.ElementId or None) is applied
    to every footing's Structural Material instance parameter.
    """
    res = FootingResult()
    for symbol, floors in floors_by_type:
        if symbol is None:
            continue
        if not symbol.IsActive:
            symbol.Activate()
            doc.Regenerate()
        apply_footing_material(None, symbol, material_id)
        for floor in floors:
            try:
                level = doc.GetElement(floor.LevelId)
                if level is None:
                    res.errors.append(u"Floor {0}: no level found, skipped.".format(floor.Id))
                    res.skipped += 1
                    continue
                fp = floor_bbox_footprint(floor)
                if fp is None:
                    res.errors.append(u"Floor {0}: degenerate footprint, skipped.".format(floor.Id))
                    res.skipped += 1
                    continue

                pt = DB.XYZ(fp[u"center_x"], fp[u"center_y"], level.Elevation)
                inst = doc.Create.NewFamilyInstance(pt, symbol, level, DB.Structure.StructuralType.Footing)
                doc.Regenerate()
                set_height_offset(inst, fp[u"height_offset_ft"])
                apply_footing_material(inst, symbol, material_id)
                _copy_mark(floor, inst)

                if delete_source_floors:
                    doc.Delete(floor.Id)
                res.placed += 1
            except Exception as e:
                res.errors.append(unicode(str(e)))
    return res
