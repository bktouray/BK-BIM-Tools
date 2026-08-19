# -*- coding: utf-8 -*-
__title__ = u"Auto\nLintels"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Generate lintel beams above wall-hosted doors and windows.
Select a structural framing family type, enter the lintel height and bearing
offset, choose a structural material, and the tool sizes each lintel from the
host wall core width and opening width.
"""

from pyrevit import revit, DB, script
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType

# Dev reload: always pick up the latest shared helpers on each click.
import sys as _sys
for _m in [_n for _n in list(_sys.modules)
          if _n.startswith("bkbim.automation")
          or _n.startswith("bkbim.ui.views")]:
    del _sys.modules[_m]

from bkbim.automation.common import element_id_value, to_feet
from bkbim.automation.failures import swallow_warnings
from bkbim.automation.familyutils import pick_family_symbol
from bkbim.ui.views.auto_lintel_options import (
    SCOPE_ACTIVE_VIEW,
    SCOPE_MANUAL,
    SCOPE_WHOLE_MODEL,
    show_auto_lintel_options,
)
from bkbim.ui.views.result_dialog import show_result

logger = script.get_logger()
output = script.get_output()
doc = revit.doc
uidoc = revit.uidoc

_MM = 304.8
_SNAP_MM = 5.0
_COMMENT_PREFIX = u"BKBIM Auto Lintel opening:"
_TYPE_MARK = u"Lintel"

BEAM_DIM_NAMES = [
    (u"b", u"h"),
    (u"B", u"H"),
    (u"Width", u"Height"),
    (u"Beam Width", u"Beam Height"),
    (u"Width", u"Depth"),
    (u"b", u"d"),
    (u"B", u"D"),
]


def _name(el):
    try:
        return el.Name
    except Exception:
        return DB.Element.Name.__get__(el)


def _snap(value_mm, step_mm=_SNAP_MM):
    return int(round(value_mm / step_mm) * step_mm)


def _is_opening(elem):
    if not isinstance(elem, DB.FamilyInstance):
        return False
    if elem.Category is None:
        return False
    try:
        cid = element_id_value(elem.Category.Id)
        return cid in (
            int(DB.BuiltInCategory.OST_Doors),
            int(DB.BuiltInCategory.OST_Windows),
        )
    except Exception:
        return False


class _OpeningSelectionFilter(ISelectionFilter):
    def AllowElement(self, elem):
        return _is_opening(elem)

    def AllowReference(self, reference, point):
        return False


def _collect_openings_for_scope(scope):
    if scope == SCOPE_MANUAL:
        try:
            picked_refs = uidoc.Selection.PickObjects(
                ObjectType.Element, _OpeningSelectionFilter(),
                "Select doors/windows for Auto Lintels, then click Finish")
        except Exception:
            return []
        return [doc.GetElement(ref.ElementId) for ref in picked_refs]

    openings = []
    view_id = revit.active_view.Id if scope == SCOPE_ACTIVE_VIEW else None
    for bic in (DB.BuiltInCategory.OST_Doors, DB.BuiltInCategory.OST_Windows):
        collector = DB.FilteredElementCollector(doc, view_id) if view_id else DB.FilteredElementCollector(doc)
        elems = (collector.OfCategory(bic)
                 .WhereElementIsNotElementType().ToElements())
        openings.extend([e for e in elems if _is_opening(e)])
    return openings


def _param_double(elem, builtins, names):
    for bip_name in builtins:
        try:
            bip = getattr(DB.BuiltInParameter, bip_name)
            p = elem.get_Parameter(bip)
        except Exception:
            p = None
        if p is not None:
            try:
                v = p.AsDouble()
                if v > 1e-9:
                    return v
            except Exception:
                pass

    for source in (elem, getattr(elem, "Symbol", None)):
        if source is None:
            continue
        for pn in names:
            try:
                p = source.LookupParameter(pn)
            except Exception:
                p = None
            if p is not None:
                try:
                    v = p.AsDouble()
                    if v > 1e-9:
                        return v
                except Exception:
                    pass
    return None


def _bbox_center(elem):
    bbox = elem.get_BoundingBox(None)
    if bbox is None:
        return None
    return DB.XYZ(
        (bbox.Min.X + bbox.Max.X) / 2.0,
        (bbox.Min.Y + bbox.Max.Y) / 2.0,
        (bbox.Min.Z + bbox.Max.Z) / 2.0)


def _bbox_width_along(elem, direction):
    bbox = elem.get_BoundingBox(None)
    if bbox is None:
        return None
    vals = []
    for x in (bbox.Min.X, bbox.Max.X):
        for y in (bbox.Min.Y, bbox.Max.Y):
            for z in (bbox.Min.Z, bbox.Max.Z):
                vals.append(DB.XYZ(x, y, z).DotProduct(direction))
    if not vals:
        return None
    return max(vals) - min(vals)


def _opening_width(opening, wall_direction):
    width = _param_double(
        opening,
        ("DOOR_WIDTH", "WINDOW_WIDTH", "FAMILY_WIDTH_PARAM"),
        (u"Width", u"Rough Width", u"Overall Width", u"Nominal Width"))
    if width is not None:
        return width
    return _bbox_width_along(opening, wall_direction)


def _level_for_opening(opening, wall):
    for eid in (opening.LevelId, wall.LevelId):
        try:
            level = doc.GetElement(eid)
        except Exception:
            level = None
        if isinstance(level, DB.Level):
            return level
    levels = list(DB.FilteredElementCollector(doc).OfClass(DB.Level).ToElements())
    if not levels:
        return None
    center = _bbox_center(opening)
    z = center.Z if center is not None else 0.0
    levels.sort(key=lambda lv: abs(lv.Elevation - z))
    return levels[0]


def _opening_head_offset(opening, level):
    if level is None:
        return None

    head = _param_double(opening, ("INSTANCE_HEAD_HEIGHT_PARAM",), (u"Head Height",))
    if head is not None:
        return head

    height = _param_double(
        opening,
        ("FAMILY_HEIGHT_PARAM", "DOOR_HEIGHT", "WINDOW_HEIGHT"),
        (u"Height", u"Rough Height", u"Overall Height", u"Nominal Height"))
    sill = _param_double(opening, ("INSTANCE_SILL_HEIGHT_PARAM",), (u"Sill Height",)) or 0.0
    if height is not None:
        return sill + height

    bbox = opening.get_BoundingBox(None)
    if bbox is not None:
        return bbox.Max.Z - level.Elevation
    return None


def _compound_core_data(wall):
    try:
        wall_type = wall.WallType
        total_width = wall_type.Width
        cs = wall_type.GetCompoundStructure()
    except Exception:
        try:
            return wall.WallType.Width, 0.0
        except Exception:
            return 0.0, 0.0

    if cs is None:
        return total_width, 0.0

    try:
        first = cs.GetFirstCoreLayerIndex()
        last = cs.GetLastCoreLayerIndex()
        layers = list(cs.GetLayers())
    except Exception:
        return total_width, 0.0

    if first < 0 or last < first or last >= len(layers):
        return total_width, 0.0

    core_width = 0.0
    exterior_finish = 0.0
    for i, layer in enumerate(layers):
        try:
            w = layer.Width
        except Exception:
            w = 0.0
        if i < first:
            exterior_finish += w
        if first <= i <= last:
            core_width += w

    if core_width <= 1e-9:
        core_width = total_width
    core_offset_from_wall_center = (total_width / 2.0) - exterior_finish - (core_width / 2.0)
    return core_width, core_offset_from_wall_center


def _wall_location_line(wall):
    try:
        p = wall.get_Parameter(DB.BuiltInParameter.WALL_KEY_REF_PARAM)
        if p is not None:
            return p.AsInteger()
    except Exception:
        pass
    return 0


def _enum_int(value):
    try:
        return int(value)
    except Exception:
        try:
            return int(value.value__)
        except Exception:
            return None


def _core_offset_from_baseline(wall, core_width, core_offset_from_wall_center):
    try:
        total_width = wall.WallType.Width
    except Exception:
        total_width = core_width
    exterior_finish_to_core_center = (total_width / 2.0) - core_offset_from_wall_center
    interior_finish_to_core_center = (total_width / 2.0) + core_offset_from_wall_center

    loc = _wall_location_line(wall)
    enums = (
        (u"WallCenterline", core_offset_from_wall_center),
        (u"CoreCenterline", 0.0),
        (u"FinishFaceExterior", -exterior_finish_to_core_center),
        (u"FinishFaceInterior", interior_finish_to_core_center),
        (u"CoreFaceExterior", -core_width / 2.0),
        (u"CoreFaceInterior", core_width / 2.0),
    )
    for enum_name, offset in enums:
        try:
            enum_value = _enum_int(getattr(DB.WallLocationLine, enum_name))
        except Exception:
            enum_value = None
        if enum_value is not None and loc == enum_value:
            return offset
    return core_offset_from_wall_center


def _wall_line_data(wall):
    loc = wall.Location
    if not isinstance(loc, DB.LocationCurve):
        return None
    curve = loc.Curve
    if not isinstance(curve, DB.Line):
        return None
    start = curve.GetEndPoint(0)
    direction = (curve.GetEndPoint(1) - start).Normalize()
    normal = wall.Orientation.Normalize()
    return start, direction, normal


def _opening_center_point(opening):
    try:
        loc = opening.Location
        if isinstance(loc, DB.LocationPoint):
            return loc.Point
    except Exception:
        pass
    return _bbox_center(opening)


def _lintel_line(opening, wall, bearing_ft):
    data = _wall_line_data(wall)
    if data is None:
        return None, None, None, None, u"host wall is not a straight basic wall"
    wall_start, wall_direction, wall_normal = data

    level = _level_for_opening(opening, wall)
    if level is None:
        return None, None, None, None, u"no reference level found"
    head_offset = _opening_head_offset(opening, level)
    if head_offset is None:
        return None, None, None, None, u"could not determine opening head height"

    opening_center = _opening_center_point(opening)
    if opening_center is None:
        return None, None, None, None, u"could not determine opening center"

    opening_width = _opening_width(opening, wall_direction)
    if opening_width is None or opening_width <= 1e-6:
        return None, None, None, None, u"could not determine opening width"

    core_width, core_offset_center = _compound_core_data(wall)
    if core_width <= 1e-6:
        return None, None, None, None, u"could not determine host wall core width"
    core_offset_base = _core_offset_from_baseline(wall, core_width, core_offset_center)

    along = (opening_center - wall_start).DotProduct(wall_direction)
    plan_center = wall_start + (wall_direction * along) + (wall_normal * core_offset_base)
    center = DB.XYZ(plan_center.X, plan_center.Y, level.Elevation)
    half_length = (opening_width / 2.0) + bearing_ft

    p0 = center - (wall_direction * half_length)
    p1 = center + (wall_direction * half_length)
    return DB.Line.CreateBound(p0, p1), core_width, level, head_offset, None


def _get_parameter_by_builtin_or_name(elem, builtins, names):
    for bip_name in builtins:
        try:
            p = elem.get_Parameter(getattr(DB.BuiltInParameter, bip_name))
        except Exception:
            p = None
        if p is not None:
            return p
    for pn in names:
        try:
            p = elem.LookupParameter(pn)
        except Exception:
            p = None
        if p is not None:
            return p
    return None


def _set_element_id_param(elem, builtins, names, element_id):
    p = _get_parameter_by_builtin_or_name(elem, builtins, names)
    if p is not None and not p.IsReadOnly:
        try:
            p.Set(element_id)
            return True
        except Exception:
            pass
    return False


def _set_double_param(elem, builtins, names, value_ft):
    p = _get_parameter_by_builtin_or_name(elem, builtins, names)
    if p is not None and not p.IsReadOnly:
        try:
            p.Set(value_ft)
            return True
        except Exception:
            pass
    return False


def _set_int_or_value_string_param(elem, builtins, names, int_value, value_text):
    p = _get_parameter_by_builtin_or_name(elem, builtins, names)
    if p is None or p.IsReadOnly:
        return False
    try:
        ok = p.SetValueString(value_text)
        if ok:
            return True
    except Exception:
        pass
    try:
        p.Set(int_value)
        return True
    except Exception:
        pass
    return False


def _apply_bottom_head_reference(inst, level, head_offset_ft):
    _set_element_id_param(
        inst,
        ("INSTANCE_REFERENCE_LEVEL_PARAM",),
        (u"Reference Level",),
        level.Id)

    _set_int_or_value_string_param(
        inst,
        ("Z_JUSTIFICATION",),
        (u"z Justification", u"Z Justification"),
        3,
        u"Bottom")

    if _set_double_param(
            inst,
            ("Z_OFFSET_VALUE",),
            (u"z Offset Value", u"Z Offset Value", u"Z Offset"),
            head_offset_ft):
        return

    _set_double_param(
        inst,
        ("STRUCTURAL_BEAM_END0_ELEVATION",),
        (u"Start Level Offset", u"Start Offset"),
        head_offset_ft)
    _set_double_param(
        inst,
        ("STRUCTURAL_BEAM_END1_ELEVATION",),
        (u"End Level Offset", u"End Offset"),
        head_offset_ft)


def _set_type_mark(symbol):
    p = symbol.LookupParameter(u"Type Mark")
    if p is not None and not p.IsReadOnly:
        try:
            p.Set(_TYPE_MARK)
        except Exception:
            pass


def _set_beam_dimensions(symbol, width_ft, height_ft):
    for width_name, height_name in BEAM_DIM_NAMES:
        wp = symbol.LookupParameter(width_name)
        hp = symbol.LookupParameter(height_name)
        if (wp is not None and hp is not None
                and not wp.IsReadOnly and not hp.IsReadOnly):
            try:
                wp.Set(width_ft)
                hp.Set(height_ft)
                return True
            except Exception:
                continue
    return False


def _get_or_create_lintel_type(base_symbol, core_width_ft, height_ft, cache):
    key = (_snap(core_width_ft * _MM), _snap(height_ft * _MM))
    if key in cache:
        return cache[key]

    wanted = u"Lintel - {0} - {1}x{2}mm".format(_name(base_symbol.Family), key[0], key[1])
    for tid in base_symbol.Family.GetFamilySymbolIds():
        sym = doc.GetElement(tid)
        if _name(sym) == wanted:
            _set_type_mark(sym)
            cache[key] = (sym, True)
            return cache[key]

    try:
        new_el = base_symbol.Duplicate(wanted)
        if isinstance(new_el, DB.FamilySymbol):
            sym = new_el
        elif isinstance(new_el, DB.ElementId):
            sym = doc.GetElement(new_el)
        else:
            sym = doc.GetElement(new_el.Id)
    except Exception:
        cache[key] = (base_symbol, False)
        return cache[key]

    sized = _set_beam_dimensions(sym, core_width_ft, height_ft)
    _set_type_mark(sym)
    cache[key] = (sym, sized)
    return cache[key]


def _apply_structural_material(inst, symbol, material_id):
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
            try:
                p = symbol.LookupParameter(pn)
            except Exception:
                p = None
            if p is not None and not p.IsReadOnly:
                try:
                    p.Set(material_id)
                    return
                except Exception:
                    pass


def _join_lintel_to_wall(inst, wall):
    try:
        if not DB.JoinGeometryUtils.AreElementsJoined(doc, inst, wall):
            DB.JoinGeometryUtils.JoinGeometry(doc, inst, wall)
    except Exception as e:
        return False, unicode(str(e))

    try:
        if not DB.JoinGeometryUtils.IsCuttingElementInJoin(doc, inst, wall):
            DB.JoinGeometryUtils.SwitchJoinOrder(doc, inst, wall)
    except Exception as e:
        return False, unicode(str(e))

    return True, None


def _opening_key(opening):
    try:
        return unicode(opening.UniqueId)
    except Exception:
        return unicode(opening.Id)


def _existing_lintel_keys():
    keys = set()
    beams = (DB.FilteredElementCollector(doc)
             .OfCategory(DB.BuiltInCategory.OST_StructuralFraming)
             .WhereElementIsNotElementType().ToElements())
    for beam in beams:
        try:
            p = beam.get_Parameter(DB.BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
        except Exception:
            p = None
        if p is None:
            continue
        try:
            text = p.AsString()
        except Exception:
            text = None
        if text and text.startswith(_COMMENT_PREFIX):
            keys.add(text[len(_COMMENT_PREFIX):].strip())
    return keys


def _tag_lintel(inst, opening):
    key = _opening_key(opening)
    try:
        p = inst.get_Parameter(DB.BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
        if p is not None and not p.IsReadOnly:
            p.Set(u"{0} {1}".format(_COMMENT_PREFIX, key))
    except Exception:
        pass


class _LintelResult(object):
    def __init__(self):
        self.created = 0
        self.skipped_existing = 0
        self.skipped = 0
        self.unsized_types = 0
        self.join_failed = 0
        self.errors = []


def _place_lintels(openings, base_symbol, beam_height_ft, bearing_ft, material_id):
    res = _LintelResult()
    existing = _existing_lintel_keys()
    type_cache = {}
    unsized_type_ids = set()

    if not base_symbol.IsActive:
        base_symbol.Activate()
        doc.Regenerate()

    for opening in openings:
        key = _opening_key(opening)
        if key in existing:
            res.skipped_existing += 1
            continue

        wall = opening.Host
        if wall is None or not isinstance(wall, DB.Wall):
            res.skipped += 1
            res.errors.append(u"Opening {0}: not hosted by a wall.".format(opening.Id))
            continue

        line, core_width, level, head_offset, err = _lintel_line(opening, wall, bearing_ft)
        if err is not None:
            res.skipped += 1
            res.errors.append(u"Opening {0}: {1}.".format(opening.Id, err))
            continue

        symbol, sized = _get_or_create_lintel_type(base_symbol, core_width, beam_height_ft, type_cache)
        if not symbol.IsActive:
            symbol.Activate()
            doc.Regenerate()
        _apply_structural_material(None, symbol, material_id)
        if not sized:
            unsized_type_ids.add(symbol.Id)

        try:
            inst = doc.Create.NewFamilyInstance(line, symbol, level, DB.Structure.StructuralType.Beam)
            _apply_bottom_head_reference(inst, level, head_offset)
            _apply_structural_material(inst, symbol, material_id)
            doc.Regenerate()
            joined, join_err = _join_lintel_to_wall(inst, wall)
            if not joined:
                res.join_failed += 1
                if join_err:
                    res.errors.append(u"Opening {0}: lintel placed, join failed: {1}".format(opening.Id, join_err))
            _tag_lintel(inst, opening)
            existing.add(key)
            res.created += 1
        except Exception as e:
            res.skipped += 1
            res.errors.append(u"Opening {0}: {1}".format(opening.Id, unicode(str(e))))

    res.unsized_types = len(unsized_type_ids)
    return res


def main():
    if doc is None:
        show_result(__title__, "No active Revit document.")
        return

    materials = sorted(
        DB.FilteredElementCollector(doc).OfClass(DB.Material).ToElements(),
        key=_name)
    options = show_auto_lintel_options(
        u"Generate lintel beams over wall-hosted doors and windows.",
        materials,
        _name,
        lambda: pick_family_symbol(
            doc,
            [DB.BuiltInCategory.OST_StructuralFraming],
            "Base beam family/type for lintels"))
    if not options:
        return

    openings = _collect_openings_for_scope(options.scope)
    if not openings:
        show_result(__title__, "No doors or windows found for that scope.")
        return

    height_ft = to_feet(options.height_mm, "mm")
    bearing_ft = to_feet(options.bearing_mm, "mm")

    t = DB.Transaction(doc, "Generate Lintel Beams")
    t.Start()
    swallow_warnings(t)
    try:
        res = _place_lintels(
            openings,
            options.base_symbol,
            height_ft,
            bearing_ft,
            options.material_id)
        if res.created == 0:
            t.RollBack()
        else:
            t.Commit()
    except Exception as e:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        logger.error("Auto Lintels failed: {0}".format(str(e)))
        show_result(__title__, "Auto Lintels failed:\n{0}".format(str(e)))
        return

    if res.created == 0:
        msg = "No lintel beams were created."
        if res.skipped_existing:
            msg += "\n\n{0} opening(s) already had BKBIM lintels.".format(res.skipped_existing)
        if res.errors:
            msg += "\n\n" + "\n".join(res.errors[:5])
        show_result(__title__, msg)
        return

    msg = (
        "Auto Lintels Complete.\n\n"
        "Created {0} lintel beam(s).".format(res.created))
    if res.skipped_existing:
        msg += "\n{0} skipped because they already had BKBIM lintels.".format(res.skipped_existing)
    if res.skipped:
        msg += "\n{0} skipped because their host/geometry could not be read.".format(res.skipped)
    if res.join_failed:
        msg += "\n{0} lintel(s) were placed but could not be joined to the host wall.".format(res.join_failed)
    if res.unsized_types:
        msg += (
            "\n\nNote: {0} beam type(s) could not be auto-sized. "
            "If the selected family uses custom width/height parameter names, "
            "rename them to b/h, B/H, Width/Height, or Beam Width/Beam Height."
            .format(res.unsized_types))
    show_result(__title__, msg)

    if res.errors:
        output.print_md("**Auto Lintels notes:**")
        for err in res.errors[:20]:
            output.print_md("- " + err)


if __name__ == "__main__":
    main()
