# -*- coding: utf-8 -*-
"""Generate PCC (plain cement concrete) blinding pads beneath existing
isolated structural foundations.

Each footing gets its own rectangular blinding pad: footprint = the
footing's plan bounding box expanded outward by a fixed offset on all
sides, placed directly beneath the footing (the pad's own top coincides
with the footing's own bottom, both read from real bounding-box world Z -
independent of how the source footing names its own offset/thickness
parameters), at one shared user-chosen depth, using a chosen structural
material.

A blinding pad is geometrically just another rectangular isolated
foundation instance - reuses footings.py's `get_or_create_sized_footing_type`
(family duplication/caching) and `apply_footing_material`/`set_height_offset`
(shared once a 2nd consumer needed them, per this suite's own "extract on
2nd use" convention) rather than duplicating that logic.

Scope: isolated footings only (FamilyInstance, OST_StructuralFoundation,
StructuralType.Footing) - wall/strip footings (WallFoundation class) and
foundation slabs (Floor class) are out of scope, same category-scoping
precedent as structural_type_reader.py's CATEGORY_FOOTING.

IronPython 2.7.
"""

from pyrevit import DB

from bkbim.automation.footings import apply_footing_material, set_dimensions, set_height_offset

_MM = 304.8  # mm per foot

# Product owner, 2026-07-14: every blinding type's Type Mark must literally
# read "PCC Blinding" and its Type Name must contain "PCC" - kept as its
# own naming scheme (not footings.py's `get_or_create_sized_footing_type`)
# so a blinding type can never collide with, or be confused with, a
# same-size Floors-to-Footings type.
_TYPE_MARK = u"PCC Blinding"


def _name(el):
    try:
        return el.Name
    except Exception:
        return DB.Element.Name.__get__(el)


def _snap(v, step):
    return int(round(v / step) * step)


def _set_type_mark(symbol):
    p = symbol.LookupParameter(u"Type Mark")
    if p is not None and not p.IsReadOnly:
        try:
            p.Set(_TYPE_MARK)
        except Exception:
            pass


def _footing_mark(footing):
    p = footing.LookupParameter(u"Mark")
    if p is None:
        return None
    try:
        return p.AsString()
    except Exception:
        return None


def _wanted_mark(footing):
    """'PCC-<footing's own Mark>' (e.g. footing 'F1' -> 'PCC-F1'), or plain
    'PCC' if the footing has no Mark of its own.
    """
    footing_mark = _footing_mark(footing)
    return u"PCC-{0}".format(footing_mark) if footing_mark else u"PCC"


def _apply_blinding_mark(footing, inst):
    ip = inst.LookupParameter(u"Mark")
    if ip is not None and not ip.IsReadOnly:
        try:
            ip.Set(_wanted_mark(footing))
        except Exception:
            pass


def is_blinding_pad(elem):
    """True if `elem` is one of THIS tool's own blinding pads (Structural
    Foundation FamilyInstance whose type carries our "PCC Blinding" Type
    Mark) - used to make sure a pad changing its own Mark is never mistaken
    for a footing whose blinding needs (re-)syncing.
    """
    if not isinstance(elem, DB.FamilyInstance):
        return False
    try:
        cat = elem.Category
        if cat is None or cat.Id != DB.ElementId(DB.BuiltInCategory.OST_StructuralFoundation):
            return False
        tm = elem.Symbol.LookupParameter(u"Type Mark")
        return tm is not None and tm.AsString() == _TYPE_MARK
    except Exception:
        return False


_ASSOCIATION_TOLERANCE_FT = 0.01  # ~3mm


def find_associated_blinding_pad(doc, footing, tol_ft=_ASSOCIATION_TOLERANCE_FT):
    """Find the blinding pad geometrically associated with `footing`: same
    plan center, and the pad's own top touching the footing's own bottom.
    The link is derived from geometry, not a stored id - both were placed
    from the exact same footprint math when the tool ran, so this is exact
    unless one of the two was independently moved afterward (at which
    point the pairing is genuinely ambiguous anyway). Returns None if no
    match is found.
    """
    f_bbox = footing.get_BoundingBox(None)
    if f_bbox is None:
        return None
    fx = (f_bbox.Max.X + f_bbox.Min.X) / 2.0
    fy = (f_bbox.Max.Y + f_bbox.Min.Y) / 2.0
    f_bottom_z = f_bbox.Min.Z

    candidates = (DB.FilteredElementCollector(doc)
                  .OfCategory(DB.BuiltInCategory.OST_StructuralFoundation)
                  .WhereElementIsNotElementType().ToElements())
    for c in candidates:
        if c.Id == footing.Id or not is_blinding_pad(c):
            continue
        c_bbox = c.get_BoundingBox(None)
        if c_bbox is None:
            continue
        cx = (c_bbox.Max.X + c_bbox.Min.X) / 2.0
        cy = (c_bbox.Max.Y + c_bbox.Min.Y) / 2.0
        if (abs(cx - fx) <= tol_ft and abs(cy - fy) <= tol_ft
                and abs(c_bbox.Max.Z - f_bottom_z) <= tol_ft):
            return c
    return None


def sync_mark_from_footing(doc, footing):
    """If `footing` has an associated blinding pad, make sure the pad's
    Mark matches `_wanted_mark(footing)`. Returns True if the pad's Mark
    was actually changed, False if no pad was found, it's read-only, or
    it was already in sync (cheap to call unconditionally/often).
    """
    pad = find_associated_blinding_pad(doc, footing)
    if pad is None:
        return False
    ip = pad.LookupParameter(u"Mark")
    if ip is None or ip.IsReadOnly:
        return False
    wanted = _wanted_mark(footing)
    if ip.AsString() == wanted:
        return False
    try:
        ip.Set(wanted)
        return True
    except Exception:
        return False


class BlindingResult(object):
    def __init__(self):
        self.placed = 0
        self.skipped = 0
        self.errors = []


def footing_blinding_footprint(footing, offset_ft):
    """Blinding footprint for one footing: plan bbox expanded by
    `offset_ft` on all sides (XY center unchanged), top Z = the footing's
    own bottom Z (world coordinates). Returns None if degenerate.
    """
    bbox = footing.get_BoundingBox(None)
    if bbox is None:
        return None
    length_ft = (bbox.Max.X - bbox.Min.X) + 2 * offset_ft
    width_ft = (bbox.Max.Y - bbox.Min.Y) + 2 * offset_ft
    if length_ft <= 1e-6 or width_ft <= 1e-6:
        return None
    return {
        u"length_ft": length_ft,
        u"width_ft": width_ft,
        u"center_x": (bbox.Max.X + bbox.Min.X) / 2.0,
        u"center_y": (bbox.Max.Y + bbox.Min.Y) / 2.0,
        u"top_z": bbox.Min.Z,
    }


def group_footings_by_blinding_size(footings, offset_ft, snap=5.0):
    """Return [((length_mm, width_mm), [footing,...]), ...], grouped by the
    RESULTING blinding footprint size. Depth is one shared global value
    applied at placement time, not part of this grouping key. Footings with
    a degenerate bounding box are silently excluded.
    """
    buckets = {}
    for f in footings:
        fp = footing_blinding_footprint(f, offset_ft)
        if fp is None:
            continue
        key = (_snap(fp[u"length_ft"] * _MM, snap), _snap(fp[u"width_ft"] * _MM, snap))
        buckets.setdefault(key, []).append(f)
    rows = list(buckets.items())
    rows.sort(key=lambda kv: (kv[0][0], kv[0][1]))
    return rows


def get_or_create_sized_blinding_type(doc, base_symbol, length_ft, width_ft, depth_ft, snap, cache):
    """Return a PCC-blinding-specific footing type sized to (length, width,
    depth), named "PCC Blinding - <base family> - <L>x<W>x<T>mm" with its
    Type Mark set to "PCC Blinding" - creating it once per distinct size.
    Falls back to `base_symbol` unsized (Type Mark left untouched) if
    duplication or dimension-writing fails.
    """
    key = (
        _snap(length_ft * _MM, snap),
        _snap(width_ft * _MM, snap),
        _snap(depth_ft * _MM, snap),
    )
    if key in cache:
        return cache[key]

    wanted = u"PCC Blinding - {0} - {1}x{2}x{3}mm".format(_name(base_symbol.Family), key[0], key[1], key[2])

    fam = base_symbol.Family
    for tid in fam.GetFamilySymbolIds():
        s = doc.GetElement(tid)
        if _name(s) == wanted:
            _set_type_mark(s)
            cache[key] = s
            return s

    try:
        new_id_el = base_symbol.Duplicate(wanted)
    except Exception:
        cache[key] = base_symbol
        return base_symbol
    new_sym = new_id_el if isinstance(new_id_el, DB.FamilySymbol) else doc.GetElement(new_id_el.Id)
    set_dimensions(new_sym, length_ft, width_ft, depth_ft)
    _set_type_mark(new_sym)
    cache[key] = new_sym
    return new_sym


def place_blinding(doc, footings_by_type, offset_ft, material_id=None):
    """Place one blinding pad per footing. footings_by_type: list of
    (family_symbol, [footing,...]) - symbol already sized to this group's
    length/width, with the shared depth baked in as its own Foundation
    Thickness.
    """
    res = BlindingResult()
    for symbol, footings in footings_by_type:
        if symbol is None:
            continue
        if not symbol.IsActive:
            symbol.Activate()
            doc.Regenerate()
        apply_footing_material(None, symbol, material_id)
        for footing in footings:
            try:
                level = doc.GetElement(footing.LevelId)
                if level is None:
                    res.errors.append(u"Footing {0}: no level found, skipped.".format(footing.Id))
                    res.skipped += 1
                    continue
                fp = footing_blinding_footprint(footing, offset_ft)
                if fp is None:
                    res.errors.append(u"Footing {0}: degenerate footprint, skipped.".format(footing.Id))
                    res.skipped += 1
                    continue

                pt = DB.XYZ(fp[u"center_x"], fp[u"center_y"], level.Elevation)
                inst = doc.Create.NewFamilyInstance(pt, symbol, level, DB.Structure.StructuralType.Footing)
                doc.Regenerate()
                height_offset_ft = fp[u"top_z"] - level.Elevation
                set_height_offset(inst, height_offset_ft)
                apply_footing_material(inst, symbol, material_id)
                _apply_blinding_mark(footing, inst)
                res.placed += 1
            except Exception as e:
                res.errors.append(unicode(str(e)))
    return res
