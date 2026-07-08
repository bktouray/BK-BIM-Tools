# -*- coding: utf-8 -*-
"""Category extractors for the BOQ export tools.

Every extractor returns an ``Extract`` made of one or more ``Sheet`` objects.
Two archetypes are used:

* Type-catalog (Walls, Floors, Materials) - preserves the original NEO
  deliverable (type + layer breakdown) and adds aggregated instance
  quantities (count / area / volume / length) per type.
* Instance takeoff (Columns, Beams, Doors, Windows, Foundations, Ceilings,
  Roofs, Rooms, Railings, Stairs) - one row per placed element with Mark,
  family/type and quantities; a second sheet lists type definitions that have
  zero placed instances ("unused").

The first column of every sheet is ``Key`` (the merge key) and the second is
``Status`` (filled in by the merge step in xlio).
"""

from pyrevit import DB
from bkbim.boq import rvt
from bkbim.boq.model import KEY, STATUS, Sheet, Extract


# ===========================================================================
# Instance-takeoff archetype
# ===========================================================================
def _instance_extract(doc, label, bics, fields, scope, kind_for=None):
    """Generic instance takeoff.

    bics      : list of BuiltInCategory to union (e.g. struct + arch columns)
    fields    : list of (header, func(doc, element) -> value)
    kind_for  : optional func(doc, element) -> str tag (e.g. Structural/Arch)
    """
    used_cols = [KEY, STATUS, "Mark", "Family", "Type", "Level"]
    if kind_for:
        used_cols.append("Kind")
    used_cols += [h for h, _ in fields] + ["Comments"]

    used_rows = []
    counts = {}
    all_types = {}

    for bic in bics:
        for el in rvt.instances(doc, bic):
            try:
                tid = rvt.eid(el.GetTypeId())
                counts[tid] = counts.get(tid, 0) + 1
            except Exception:
                pass
            fam, typ = rvt.family_and_type(doc, el)
            row = {
                KEY: rvt.uid(el),
                STATUS: "",
                "Mark": rvt.mark(el),
                "Family": fam,
                "Type": typ,
                "Level": rvt.level_name(doc, el),
                "Comments": rvt.comments(el),
            }
            if kind_for:
                row["Kind"] = kind_for(doc, el)
            for header, fn in fields:
                try:
                    row[header] = fn(doc, el)
                except Exception:
                    row[header] = None
            used_rows.append(row)
        for t in rvt.types(doc, bic):
            all_types[rvt.eid(t.Id)] = (t, bic)

    sheets = [Sheet("Used", used_cols, used_rows)]

    if scope == "all":
        unused_cols = [KEY, STATUS, "Family", "Type", "Note"]
        unused_rows = []
        for tid, (t, bic) in all_types.items():
            if counts.get(tid, 0) == 0:
                fam = ""
                try:
                    fam = rvt.nstr(t.FamilyName)
                except Exception:
                    fam = ""
                unused_rows.append({
                    KEY: rvt.uid(t),
                    STATUS: "",
                    "Family": fam,
                    "Type": rvt.ename(t),
                    "Note": "Type loaded but no instances placed",
                })
        sheets.append(Sheet("Unused", unused_cols, unused_rows))

    return Extract(label, sheets)


# ---- per-category field functions -----------------------------------------
def _len_m(doc, el):
    try:
        loc = el.Location
        if isinstance(loc, DB.LocationCurve):
            return rvt.to_m(loc.Curve.Length)
    except Exception:
        pass
    return rvt.to_m(rvt.p_double(el, "CURVE_ELEM_LENGTH", "INSTANCE_LENGTH_PARAM",
                                 "STRUCTURAL_FRAME_CUT_LENGTH"))


def _host_wall(doc, el):
    try:
        h = el.Host
        if h is not None:
            return rvt.ename(h) or ("Wall " + str(rvt.eid(h.Id)))
    except Exception:
        pass
    return ""


def _dim_mm(bip_names):
    """Read a length parameter from the instance only (e.g. sill height)."""
    def fn(doc, el):
        return rvt.to_mm(rvt.p_double(el, *bip_names))
    return fn


def _type_dim_mm(bip_names):
    """Read a length parameter from the element's type first (door/window
    Width and Height live on the type), falling back to the instance."""
    def fn(doc, el):
        sym = getattr(el, "Symbol", None)
        v = rvt.p_double(sym, *bip_names) if sym is not None else None
        if not v:
            v = rvt.p_double(el, *bip_names)
        return rvt.to_mm(v)
    return fn


def _struct_usage(doc, el):
    try:
        return rvt.nstr(str(el.StructuralUsage))
    except Exception:
        return rvt.p_str(el, "INSTANCE_STRUCT_USAGE_PARAM")


def extract_columns(doc, scope):
    fields = [
        ("Volume (m3)", lambda d, e: rvt.volume_m3(e)),
        ("Mass (kg)", lambda d, e: rvt.mass_kg(d, e)),
        ("Length (m)", _len_m),
        ("Material", lambda d, e: rvt.primary_material(d, e)),
    ]
    def kind(d, e):
        try:
            cat = e.Category
            if cat and rvt.eid(cat.Id) == rvt.bic_int(DB.BuiltInCategory.OST_StructuralColumns):
                return "Structural"
        except Exception:
            pass
        return "Architectural"
    return _instance_extract(
        doc, "Columns",
        [DB.BuiltInCategory.OST_StructuralColumns, DB.BuiltInCategory.OST_Columns],
        fields, scope, kind_for=kind)


def extract_framing(doc, scope):
    fields = [
        ("Structural Usage", _struct_usage),
        ("Length (m)", _len_m),
        ("Volume (m3)", lambda d, e: rvt.volume_m3(e)),
        ("Mass (kg)", lambda d, e: rvt.mass_kg(d, e)),
        ("Material", lambda d, e: rvt.primary_material(d, e)),
    ]
    return _instance_extract(
        doc, "Beams & Framing",
        [DB.BuiltInCategory.OST_StructuralFraming], fields, scope)


def extract_doors(doc, scope):
    fields = [
        ("Width (mm)", _type_dim_mm(["DOOR_WIDTH", "FAMILY_WIDTH_PARAM", "GENERIC_WIDTH"])),
        ("Height (mm)", _type_dim_mm(["DOOR_HEIGHT", "FAMILY_HEIGHT_PARAM", "GENERIC_HEIGHT"])),
        ("Host Wall", _host_wall),
    ]
    return _instance_extract(
        doc, "Doors", [DB.BuiltInCategory.OST_Doors], fields, scope)


def extract_windows(doc, scope):
    fields = [
        ("Width (mm)", _type_dim_mm(["WINDOW_WIDTH", "FAMILY_WIDTH_PARAM", "GENERIC_WIDTH"])),
        ("Height (mm)", _type_dim_mm(["WINDOW_HEIGHT", "FAMILY_HEIGHT_PARAM", "GENERIC_HEIGHT"])),
        ("Sill Height (mm)", _dim_mm(["INSTANCE_SILL_HEIGHT_PARAM"])),
        ("Host Wall", _host_wall),
    ]
    return _instance_extract(
        doc, "Windows", [DB.BuiltInCategory.OST_Windows], fields, scope)


def extract_foundations(doc, scope):
    fields = [
        ("Volume (m3)", lambda d, e: rvt.volume_m3(e)),
        ("Mass (kg)", lambda d, e: rvt.mass_kg(d, e)),
        ("Length (m)", _len_m),
        ("Material", lambda d, e: rvt.primary_material(d, e)),
    ]
    return _instance_extract(
        doc, "Foundations",
        [DB.BuiltInCategory.OST_StructuralFoundation], fields, scope)


def extract_ceilings(doc, scope):
    fields = [
        ("Area (m2)", lambda d, e: rvt.area_m2(e)),
        ("Volume (m3)", lambda d, e: rvt.volume_m3(e)),
        ("Material", lambda d, e: rvt.primary_material(d, e)),
    ]
    return _instance_extract(
        doc, "Ceilings", [DB.BuiltInCategory.OST_Ceilings], fields, scope)


def extract_roofs(doc, scope):
    fields = [
        ("Area (m2)", lambda d, e: rvt.area_m2(e)),
        ("Volume (m3)", lambda d, e: rvt.volume_m3(e)),
        ("Material", lambda d, e: rvt.primary_material(d, e)),
    ]
    return _instance_extract(
        doc, "Roofs", [DB.BuiltInCategory.OST_Roofs], fields, scope)


def extract_railings_stairs(doc, scope):
    # Railings and stairs share one sheet; "Kind" distinguishes them.
    fields = [
        ("Length / Run (m)", _len_m),
        ("Material", lambda d, e: rvt.primary_material(d, e)),
    ]
    def kind(d, e):
        try:
            if rvt.eid(e.Category.Id) == rvt.bic_int(DB.BuiltInCategory.OST_Stairs):
                return "Stair"
        except Exception:
            pass
        return "Railing"
    return _instance_extract(
        doc, "Railings & Stairs",
        [DB.BuiltInCategory.OST_Stairs, DB.BuiltInCategory.OST_Railings],
        fields, scope, kind_for=kind)


def extract_rooms(doc, scope):
    cols = [KEY, STATUS, "Number", "Name", "Level", "Area (m2)",
            "Perimeter (m)", "Volume (m3)", "Comments"]
    rows = []
    for r in rvt.instances(doc, DB.BuiltInCategory.OST_Rooms):
        try:
            placed = r.Area > 0
        except Exception:
            placed = False
        if not placed:
            continue
        rows.append({
            KEY: rvt.uid(r),
            STATUS: "",
            "Number": rvt.p_str(r, "ROOM_NUMBER") or rvt.lookup_str(r, "Number"),
            "Name": rvt.p_str(r, "ROOM_NAME") or rvt.lookup_str(r, "Name"),
            "Level": rvt.level_name(doc, r),
            "Area (m2)": rvt.to_m2(rvt.p_double(r, "ROOM_AREA")),
            "Perimeter (m)": rvt.to_m(rvt.p_double(r, "ROOM_PERIMETER")),
            "Volume (m3)": rvt.to_m3(rvt.p_double(r, "ROOM_VOLUME")),
            "Comments": rvt.comments(r),
        })
    return Extract("Rooms", [Sheet("Rooms", cols, rows)])


# ===========================================================================
# Type-catalog archetype (Walls / Floors) - preserves the original NEO format
# ===========================================================================
def _compound_layers(doc, type_el):
    """Return (layer_rows, total_thickness_mm).

    layer_rows: list of dict(idx, function, material, thickness_mm).
    """
    rows = []
    total = 0.0
    try:
        cs = type_el.GetCompoundStructure()
        if cs:
            for i, layer in enumerate(cs.GetLayers()):
                w = 0.0
                try:
                    w = layer.Width
                except Exception:
                    w = 0.0
                total += w
                try:
                    func = rvt.nstr(str(layer.Function))
                except Exception:
                    func = ""
                rows.append({
                    "idx": i + 1,
                    "function": func,
                    "material": rvt.material_name(doc, layer.MaterialId),
                    "thickness_mm": rvt.to_mm(w),
                })
    except Exception:
        pass
    return rows, rvt.to_mm(total)


def _type_catalog(doc, label, bic, with_length):
    """Build a Walls/Floors style catalog Extract (Used + Unused sheets)."""
    # aggregate instance quantities per type id
    agg = {}
    for inst in rvt.instances(doc, bic):
        try:
            tid = rvt.eid(inst.GetTypeId())
        except Exception:
            continue
        a = agg.setdefault(tid, {"count": 0, "area": 0.0, "vol": 0.0, "len": 0.0})
        a["count"] += 1
        av = rvt.p_double(inst, "HOST_AREA_COMPUTED")
        if av:
            a["area"] += av
        vv = rvt.p_double(inst, "HOST_VOLUME_COMPUTED")
        if vv:
            a["vol"] += vv
        if with_length:
            try:
                loc = inst.Location
                if isinstance(loc, DB.LocationCurve):
                    a["len"] += loc.Curve.Length
            except Exception:
                pass

    cols = [KEY, STATUS, "Type Name", "Family", "Count",
            "Total Area (m2)", "Total Volume (m3)"]
    if with_length:
        cols.append("Total Length (m)")
    cols += ["Total Thickness (mm)", "Layer #", "Layer Function",
             "Layer Material", "Layer Thickness (mm)"]

    used_rows, unused_rows = [], []
    for t in rvt.types(doc, bic):
        tid = rvt.eid(t.Id)
        a = agg.get(tid)
        is_used = a is not None and a["count"] > 0
        layers, total_thk = _compound_layers(doc, t)
        try:
            fam = rvt.nstr(t.FamilyName)
        except Exception:
            fam = ""
        type_uid = rvt.uid(t)

        if not layers:
            layers = [{"idx": "", "function": "", "material": "", "thickness_mm": ""}]

        for li, layer in enumerate(layers):
            row = {
                KEY: "{}::L{}".format(type_uid, layer["idx"] or (li + 1)),
                STATUS: "",
                "Type Name": rvt.ename(t),
                "Family": fam,
                "Total Thickness (mm)": total_thk if li == 0 else "",
                "Layer #": layer["idx"],
                "Layer Function": layer["function"],
                "Layer Material": layer["material"],
                "Layer Thickness (mm)": layer["thickness_mm"],
            }
            # aggregates only on the first row of the type block
            if li == 0:
                row["Count"] = a["count"] if a else 0
                row["Total Area (m2)"] = rvt.to_m2(a["area"]) if a else 0
                row["Total Volume (m3)"] = rvt.to_m3(a["vol"]) if a else 0
                if with_length:
                    row["Total Length (m)"] = rvt.to_m(a["len"]) if a else 0
            else:
                row["Count"] = ""
                row["Total Area (m2)"] = ""
                row["Total Volume (m3)"] = ""
                if with_length:
                    row["Total Length (m)"] = ""
            (used_rows if is_used else unused_rows).append(row)

    sheets = [Sheet("Used", cols, used_rows)]
    sheets.append(Sheet("Unused", cols, unused_rows))
    return Extract(label, sheets)


def extract_walls(doc, scope):
    ex = _type_catalog(doc, "Walls", DB.BuiltInCategory.OST_Walls, with_length=True)
    if scope == "used":
        ex.sheets = [s for s in ex.sheets if s.name == "Used"]
    return ex


def extract_floors(doc, scope):
    ex = _type_catalog(doc, "Floors", DB.BuiltInCategory.OST_Floors, with_length=False)
    if scope == "used":
        ex.sheets = [s for s in ex.sheets if s.name == "Used"]
    return ex


# ===========================================================================
# Materials catalog
# ===========================================================================
def extract_materials(doc, scope):
    cols = [KEY, STATUS, "Material Name", "Appearance / Class",
            "Category", "Description", "Used"]
    # determine which materials are referenced by any element
    used_ids = set()
    try:
        for el in DB.FilteredElementCollector(doc).WhereElementIsNotElementType().ToElements():
            try:
                for mid in el.GetMaterialIds(False):
                    used_ids.add(rvt.eid(mid))
            except Exception:
                continue
    except Exception:
        pass

    used_rows, unused_rows = [], []
    for m in DB.FilteredElementCollector(doc).OfClass(DB.Material).ToElements():
        mid = rvt.eid(m.Id)
        is_used = mid in used_ids
        appearance = ""
        try:
            appearance = rvt.nstr(m.MaterialClass)
        except Exception:
            appearance = ""
        cat = ""
        try:
            cat = rvt.nstr(m.MaterialCategory)
        except Exception:
            cat = ""
        desc = rvt.p_str(m, "ALL_MODEL_DESCRIPTION") or rvt.lookup_str(m, "Description")
        row = {
            KEY: rvt.uid(m),
            STATUS: "",
            "Material Name": rvt.ename(m),
            "Appearance / Class": appearance,
            "Category": cat,
            "Description": desc,
            "Used": "Yes" if is_used else "No",
        }
        (used_rows if is_used else unused_rows).append(row)

    sheets = [Sheet("Used", cols, used_rows)]
    if scope == "all":
        sheets.append(Sheet("Unused", cols, unused_rows))
    return Extract("Materials", sheets)


# ===========================================================================
# Registry - single source of truth for buttons and the master dialog
# ===========================================================================
REGISTRY = [
    ("Walls", extract_walls),
    ("Floors", extract_floors),
    ("Materials", extract_materials),
    ("Columns", extract_columns),
    ("Beams & Framing", extract_framing),
    ("Doors", extract_doors),
    ("Windows", extract_windows),
    ("Foundations", extract_foundations),
    ("Ceilings", extract_ceilings),
    ("Roofs", extract_roofs),
    ("Rooms", extract_rooms),
    ("Railings & Stairs", extract_railings_stairs),
]

REGISTRY_MAP = dict(REGISTRY)


def run(doc, label, scope):
    return REGISTRY_MAP[label](doc, scope)
