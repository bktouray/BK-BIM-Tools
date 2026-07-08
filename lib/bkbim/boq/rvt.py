# -*- coding: utf-8 -*-
"""Revit API helpers shared by all BOQ extractors.

Targets the pyRevit CPython engine on Revit 2026, but every helper is written
defensively so it also works on older API versions (ElementId.Value vs
IntegerValue, missing BuiltInParameters, etc.).

All quantities coming out of the Revit API are in internal units (feet,
square feet, cubic feet). Convert with the to_* helpers below.
"""

from pyrevit import revit, DB

# ---------------------------------------------------------------------------
# Unit conversion (Revit internal units are always imperial regardless of the
# project's display units, so fixed constants are version-proof).
# ---------------------------------------------------------------------------
FT_TO_MM = 304.8
FT_TO_M = 0.3048
FT2_TO_M2 = 0.09290304
FT3_TO_M3 = 0.028316846592


def to_mm(value_ft):
    return round(value_ft * FT_TO_MM, 1) if value_ft is not None else None


def to_m(value_ft):
    return round(value_ft * FT_TO_M, 3) if value_ft is not None else None


def to_m2(value_ft2):
    return round(value_ft2 * FT2_TO_M2, 3) if value_ft2 is not None else None


def to_m3(value_ft3):
    return round(value_ft3 * FT3_TO_M3, 4) if value_ft3 is not None else None


# ---------------------------------------------------------------------------
# Document / element basics
# ---------------------------------------------------------------------------
def get_doc():
    """Return the active document or None."""
    return revit.doc


def bic_int(bic):
    """Integer value of a BuiltInCategory, working on IronPython and CPython."""
    try:
        return int(bic)
    except (TypeError, ValueError):
        from System import Convert
        return Convert.ToInt32(bic)


def eid(element_id):
    """Integer value of an ElementId across API versions."""
    if element_id is None:
        return None
    try:
        return int(element_id.Value)          # Revit 2024+
    except AttributeError:
        return int(element_id.IntegerValue)   # Revit 2023 and earlier


def ename(element):
    """Element name, working around IronPython/CPython property quirks."""
    if element is None:
        return ""
    try:
        n = element.Name
        if n:
            return nstr(n)
    except Exception:
        pass
    try:
        return nstr(DB.Element.Name.__get__(element))
    except Exception:
        return ""


def nstr(value):
    """Normalise any Revit string to a clean unicode str."""
    if value is None:
        return ""
    try:
        s = value if isinstance(value, str) else str(value)
    except Exception:
        return ""
    # strip control chars that break xlsx
    return "".join(ch for ch in s if ch == "\n" or ch == "\t" or ord(ch) >= 32).strip()


def uid(element):
    """Stable Revit UniqueId (GUID-based) used as the merge key."""
    try:
        return element.UniqueId
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Parameter readers (all None-safe)
# ---------------------------------------------------------------------------
def _bip(name):
    return getattr(DB.BuiltInParameter, name, None)


def p_by_bip(element, *bip_names):
    """First non-None parameter found for the given BuiltInParameter names."""
    for name in bip_names:
        bip = _bip(name)
        if bip is None:
            continue
        try:
            p = element.get_Parameter(bip)
            if p is not None:
                return p
        except Exception:
            continue
    return None


def p_str(element, *bip_names):
    p = p_by_bip(element, *bip_names)
    if p is None:
        return ""
    try:
        v = p.AsString()
        if v:
            return nstr(v)
        v = p.AsValueString()
        return nstr(v) if v else ""
    except Exception:
        return ""


def p_double(element, *bip_names):
    p = p_by_bip(element, *bip_names)
    if p is None:
        return None
    try:
        return p.AsDouble()
    except Exception:
        return None


def lookup_str(element, param_name):
    """Read a parameter by display name (handles shared/project params)."""
    try:
        p = element.LookupParameter(param_name)
        if p is None:
            return ""
        v = p.AsString()
        if v:
            return nstr(v)
        v = p.AsValueString()
        return nstr(v) if v else ""
    except Exception:
        return ""


def mark(element):
    return p_str(element, "ALL_MODEL_MARK")


def comments(element):
    return p_str(element, "ALL_MODEL_INSTANCE_COMMENTS")


def volume_m3(element):
    return to_m3(p_double(element, "HOST_VOLUME_COMPUTED", "INSTANCE_VOLUME_COMPUTED"))


def area_m2(element):
    return to_m2(p_double(element, "HOST_AREA_COMPUTED", "INSTANCE_AREA_COMPUTED"))


# ---------------------------------------------------------------------------
# Collectors / type-instance relationships
# ---------------------------------------------------------------------------
def instances(doc, bic):
    return list(
        DB.FilteredElementCollector(doc)
        .OfCategory(bic)
        .WhereElementIsNotElementType()
        .ToElements()
    )


def types(doc, bic):
    return list(
        DB.FilteredElementCollector(doc)
        .OfCategory(bic)
        .WhereElementIsElementType()
        .ToElements()
    )


def instance_count_by_type(doc, bic):
    """Map {type ElementId int: number of placed instances}."""
    counts = {}
    for inst in instances(doc, bic):
        try:
            tid = eid(inst.GetTypeId())
        except Exception:
            tid = None
        if tid is None:
            continue
        counts[tid] = counts.get(tid, 0) + 1
    return counts


def level_name(doc, element):
    """Best-effort level name for an element."""
    try:
        lid = element.LevelId
        if lid and eid(lid) and eid(lid) > 0:
            lvl = doc.GetElement(lid)
            if lvl:
                return ename(lvl)
    except Exception:
        pass
    # fall back to common level parameters
    for nm in ["FAMILY_LEVEL_PARAM", "SCHEDULE_LEVEL_PARAM",
               "INSTANCE_REFERENCE_LEVEL_PARAM", "INSTANCE_SCHEDULE_ONLY_LEVEL_PARAM",
               "FAMILY_BASE_LEVEL_PARAM"]:
        p = p_by_bip(element, nm)
        if p is not None:
            try:
                lvl = doc.GetElement(p.AsElementId())
                if lvl:
                    return ename(lvl)
            except Exception:
                continue
    return ""


def family_and_type(doc, element):
    """Return (family_name, type_name) for instance or system-family element."""
    fam, typ = "", ""
    # FamilyInstance (doors, windows, columns, framing, footings...)
    try:
        sym = getattr(element, "Symbol", None)
        if sym is not None:
            typ = ename(sym)
            try:
                fam = nstr(sym.Family.Name)
            except Exception:
                fam = ""
            return fam, typ
    except Exception:
        pass
    # System family (walls, floors, ceilings, roofs)
    try:
        t = doc.GetElement(element.GetTypeId())
        if t is not None:
            typ = ename(t)
            try:
                fp = t.get_Parameter(_bip("ALL_MODEL_FAMILY_NAME")) if _bip("ALL_MODEL_FAMILY_NAME") else None
                fam = nstr(fp.AsString()) if fp and fp.AsString() else nstr(t.FamilyName)
            except Exception:
                fam = ""
    except Exception:
        pass
    return fam, typ


def material_name(doc, mat_id):
    try:
        if mat_id is None or eid(mat_id) is None or eid(mat_id) < 0:
            return ""
        mat = doc.GetElement(mat_id)
        if not mat:
            return ""
        n = ename(mat)
        if n:
            return n
        p = mat.get_Parameter(_bip("MATERIAL_NAME")) if _bip("MATERIAL_NAME") else None
        return nstr(p.AsString()) if p and p.AsString() else ""
    except Exception:
        return ""


def _primary_material_id(element):
    """ElementId of the largest-area material on an element, or None."""
    try:
        ids = list(element.GetMaterialIds(False))
        best_id, best_area = None, -1.0
        for mid in ids:
            try:
                a = element.GetMaterialArea(mid, False)
            except Exception:
                a = 0.0
            if a > best_area:
                best_area = a
                best_id = mid
        if best_id is None and ids:
            best_id = ids[0]
        return best_id
    except Exception:
        return None


def primary_material(doc, element):
    """Name of the largest-area material on an element (best effort)."""
    return material_name(doc, _primary_material_id(element))


def mass_kg(doc, element):
    """Best-effort mass in kilograms = material density x element volume.

    Revit's internal mass-density unit times internal volume (cubic feet)
    yields kilograms directly, so no unit conversion is needed. Returns None
    when the material has no structural (physical) asset / density.
    """
    try:
        mid = _primary_material_id(element)
        if mid is None:
            return None
        mat = doc.GetElement(mid)
        if mat is None:
            return None
        said = mat.StructuralAssetId
        if said is None or eid(said) is None or eid(said) < 0:
            return None
        pse = doc.GetElement(said)
        if pse is None:
            return None
        density = pse.GetStructuralAsset().Density   # internal units
        vol_ft3 = p_double(element, "HOST_VOLUME_COMPUTED", "INSTANCE_VOLUME_COMPUTED")
        if not density or not vol_ft3:
            return None
        return round(density * vol_ft3, 1)
    except Exception:
        return None
