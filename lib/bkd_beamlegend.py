# -*- coding: utf-8 -*-
"""Shared logic for BK BIM Tools beam mark legends.

Builds a legend from Structural Framing instance Marks and the matching
mark-based view filters already applied to a source drawing/template view.
"""
import re
import os
import json

import clr
clr.AddReference("RevitAPI")
from Autodesk.Revit.DB import (
    FilteredElementCollector, BuiltInCategory, BuiltInParameter,
    Element, ElementId, ElementTransformUtils, OverrideGraphicSettings,
    TextNote, Transaction, View, ViewType, XYZ, Line, GraphicsStyleType,
)

try:
    basestring
except NameError:
    basestring = (str,)

try:
    unicode
except NameError:
    unicode = str

try:
    from Autodesk.Revit.DB import HorizontalTextAlignment, TextNoteOptions, VerticalTextAlignment
except Exception:
    HorizontalTextAlignment = None
    TextNoteOptions = None
    VerticalTextAlignment = None


ROW_GAP_MM = 650.0
TEXT_GAP_MM = 300.0
MARK_COL_MM = 0.0
COMP_COL_MM = 1800.0
SIZE_COL_MM = 5200.0
COMPONENT_LENGTH_MM = 1200.0
TABLE_PADDING_MM = 220.0
TABLE_HEADER_HEIGHT_MM = 450.0
TABLE_LINE_MARKER = u"BKD_BEAM_LEGEND_TABLE"
DEFAULT_TITLE = u"BEAM TYPE LEGEND"


def mm_to_ft(mm):
    return mm / 304.8


def idv(eid):
    try:
        return eid.Value
    except Exception:
        return eid.IntegerValue


def name_of(e):
    try:
        return Element.Name.GetValue(e)
    except Exception:
        return getattr(e, "Name", u"?")


def get_view_by_id(doc, vid):
    if vid is None:
        return None
    for v in FilteredElementCollector(doc).OfClass(View).ToElements():
        if idv(v.Id) == vid:
            return v
    return None


def get_texttype_by_id(doc, tid):
    if tid is None:
        return None
    from Autodesk.Revit.DB import TextNoteType
    for t in FilteredElementCollector(doc).OfClass(TextNoteType).ToElements():
        if idv(t.Id) == tid:
            return t
    return None


def safe_text(value):
    try:
        return unicode(value)
    except Exception:
        try:
            return str(value)
        except Exception:
            return u""


def _config_path(doc):
    title = doc.Title or u"untitled"
    safe = u"".join(c if c.isalnum() else u"_" for c in title)
    base = os.path.join(os.getenv("APPDATA"), "pyRevit")
    try:
        if not os.path.isdir(base):
            os.makedirs(base)
    except Exception:
        pass
    return os.path.join(base, "bkd_beamlegend_" + safe + ".json")


def load_config(doc):
    p = _config_path(doc)
    if os.path.isfile(p):
        try:
            with open(p, "r") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def save_config(doc, cfg):
    try:
        with open(_config_path(doc), "w") as f:
            json.dump(cfg, f)
    except Exception:
        pass


def _param_text(e, bip_or_name):
    if isinstance(bip_or_name, basestring):
        p = e.LookupParameter(bip_or_name)
    else:
        p = e.get_Parameter(bip_or_name)
    if p is None:
        return u""
    try:
        value = p.AsString()
        if value is not None:
            return value
    except Exception:
        pass
    try:
        return p.AsValueString() or u""
    except Exception:
        return u""


def type_name(doc, e):
    et = doc.GetElement(e.GetTypeId())
    name = u""
    if et is not None:
        name = _param_text(et, BuiltInParameter.ALL_MODEL_TYPE_NAME)
        if not name:
            name = name_of(et)
    if not name:
        name = name_of(e)
    return re.sub(r"\s+", u"", name or u"")


def parse_size(size):
    m = re.match(r"^(\d+)\s*x\s*(\d+)$", size or u"", re.I)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def find_components(doc, view):
    return list(FilteredElementCollector(doc, view.Id)
                .OfCategory(BuiltInCategory.OST_LegendComponents)
                .WhereElementIsNotElementType().ToElements())


def _text_type_id(doc):
    from Autodesk.Revit.DB import TextNoteType
    types = sorted(FilteredElementCollector(doc).OfClass(TextNoteType).ToElements(),
                   key=name_of)
    if not types:
        return None
    return types[0].Id


def _create_left_middle_text(doc, view, point, text, text_type_id):
    note = None
    try:
        if TextNoteOptions is not None:
            options = TextNoteOptions(text_type_id)
            if HorizontalTextAlignment is not None:
                options.HorizontalAlignment = HorizontalTextAlignment.Left
            if VerticalTextAlignment is not None:
                options.VerticalAlignment = VerticalTextAlignment.Middle
            note = TextNote.Create(doc, view.Id, point, text, options)
    except Exception:
        note = None
    if note is None:
        note = TextNote.Create(doc, view.Id, point, text, text_type_id)
    try:
        if HorizontalTextAlignment is not None:
            note.HorizontalAlignment = HorizontalTextAlignment.Left
    except Exception:
        pass
    try:
        if VerticalTextAlignment is not None:
            note.VerticalAlignment = VerticalTextAlignment.Middle
    except Exception:
        pass
    return note


def _create_center_middle_text(doc, view, point, text, text_type_id):
    note = None
    try:
        if TextNoteOptions is not None:
            options = TextNoteOptions(text_type_id)
            if HorizontalTextAlignment is not None:
                options.HorizontalAlignment = HorizontalTextAlignment.Center
            if VerticalTextAlignment is not None:
                options.VerticalAlignment = VerticalTextAlignment.Middle
            note = TextNote.Create(doc, view.Id, point, text, options)
    except Exception:
        note = None
    if note is None:
        note = TextNote.Create(doc, view.Id, point, text, text_type_id)
    try:
        if HorizontalTextAlignment is not None:
            note.HorizontalAlignment = HorizontalTextAlignment.Center
    except Exception:
        pass
    try:
        if VerticalTextAlignment is not None:
            note.VerticalAlignment = VerticalTextAlignment.Middle
    except Exception:
        pass
    return note


def _source_graphics_view(doc, source_view):
    try:
        if source_view.ViewTemplateId != ElementId.InvalidElementId:
            template = doc.GetElement(source_view.ViewTemplateId)
            if template is not None:
                return template
    except Exception:
        pass
    return source_view


def _get_ogs_color(ogs):
    for attr in ("ProjectionLineColor", "CutLineColor"):
        try:
            color = getattr(ogs, attr)
            if color is not None and color.IsValid:
                return color
        except Exception:
            pass
    for getter in ("GetProjectionLineColor", "GetCutLineColor"):
        try:
            color = getattr(ogs, getter)()
            if color is not None and color.IsValid:
                return color
        except Exception:
            pass
    return None


def _get_ogs_pattern_id(ogs):
    for attr in ("ProjectionLinePatternId", "CutLinePatternId"):
        try:
            value = getattr(ogs, attr)
            if value is not None and value != ElementId.InvalidElementId:
                return value
        except Exception:
            pass
    for getter in ("GetProjectionLinePatternId", "GetCutLinePatternId"):
        try:
            value = getattr(ogs, getter)()
            if value is not None and value != ElementId.InvalidElementId:
                return value
        except Exception:
            pass
    return ElementId.InvalidElementId


def _get_ogs_weight(ogs):
    for attr in ("ProjectionLineWeight", "CutLineWeight"):
        try:
            value = getattr(ogs, attr)
            if value and value > 0:
                return int(value)
        except Exception:
            pass
    for getter in ("GetProjectionLineWeight", "GetCutLineWeight"):
        try:
            value = getattr(ogs, getter)()
            if value and value > 0:
                return int(value)
        except Exception:
            pass
    return 4


def _line_only_ogs_from_filter(ogs):
    new_ogs = OverrideGraphicSettings()
    color = _get_ogs_color(ogs)
    pattern_id = _get_ogs_pattern_id(ogs)
    weight = _get_ogs_weight(ogs)
    if color is not None:
        try:
            new_ogs.SetProjectionLineColor(color)
            new_ogs.SetCutLineColor(color)
        except Exception:
            pass
    try:
        new_ogs.SetProjectionLineWeight(weight)
        new_ogs.SetCutLineWeight(weight)
    except Exception:
        pass
    if pattern_id != ElementId.InvalidElementId:
        try:
            new_ogs.SetProjectionLinePatternId(pattern_id)
        except Exception:
            pass
        try:
            new_ogs.SetCutLinePatternId(pattern_id)
        except Exception:
            pass
    try:
        new_ogs.SetSurfaceTransparency(100)
    except Exception:
        pass
    invalid = ElementId.InvalidElementId
    for method in ("SetSurfaceForegroundPatternId", "SetSurfaceBackgroundPatternId",
                   "SetCutForegroundPatternId", "SetCutBackgroundPatternId"):
        try:
            getattr(new_ogs, method)(invalid)
        except Exception:
            pass
    return new_ogs


def _filter_overrides_by_mark(doc, source_view):
    graphics_view = _source_graphics_view(doc, source_view)
    overrides = {}
    try:
        filter_ids = list(graphics_view.GetFilters())
    except Exception:
        filter_ids = []
    for fid in filter_ids:
        f = doc.GetElement(fid)
        if f is None:
            continue
        try:
            name = f.Name
        except Exception:
            name = u""
        if not name:
            continue
        try:
            overrides[name] = _line_only_ogs_from_filter(graphics_view.GetFilterOverrides(fid))
        except Exception:
            pass
    return overrides


def _beam_candidates(doc, source_view=None, source_scope=u"model"):
    if source_scope == u"view" and source_view is not None:
        return FilteredElementCollector(doc, source_view.Id) \
            .OfCategory(BuiltInCategory.OST_StructuralFraming) \
            .WhereElementIsNotElementType().ToElements()
    return FilteredElementCollector(doc) \
        .OfCategory(BuiltInCategory.OST_StructuralFraming) \
        .WhereElementIsNotElementType().ToElements()


def _beam_rows(doc, source_view=None, source_scope=u"model"):
    by_mark = {}
    for beam in _beam_candidates(doc, source_view, source_scope):
        size = type_name(doc, beam)
        dims = parse_size(size)
        if dims is None:
            continue
        mark = _param_text(beam, BuiltInParameter.ALL_MODEL_MARK)
        if not mark:
            continue
        if mark not in by_mark:
            by_mark[mark] = {
                "mark": mark,
                "size": size,
                "area": dims[0] * dims[1],
                "type_id": beam.GetTypeId(),
            }
    rows = list(by_mark.values())
    rows.sort(key=lambda r: (-r["area"], r["mark"]))
    return rows


def _set_component_type(doc, comp, type_id):
    p = comp.get_Parameter(BuiltInParameter.LEGEND_COMPONENT)
    if p is not None and not p.IsReadOnly:
        p.Set(type_id)


def _set_component_length(comp, length_mm):
    param_names = (
        u"Length", u"Component Length", u"Legend Component Length",
        u"LEGEND_COMPONENT_LENGTH",
    )
    try:
        bip = getattr(BuiltInParameter, "LEGEND_COMPONENT_LENGTH")
        p = comp.get_Parameter(bip)
        if p is not None and not p.IsReadOnly:
            p.Set(mm_to_ft(length_mm))
            return True
    except Exception:
        pass
    for name in param_names:
        try:
            p = comp.LookupParameter(name)
            if p is not None and not p.IsReadOnly:
                p.Set(mm_to_ft(length_mm))
                return True
        except Exception:
            pass
    return False


def _move_component_center_to(doc, view, comp_id, center_x, center_y):
    comp = doc.GetElement(comp_id)
    bb = comp.get_BoundingBox(view)
    if bb is not None:
        current_x = (bb.Min.X + bb.Max.X) / 2.0
        current_y = (bb.Min.Y + bb.Max.Y) / 2.0
        ElementTransformUtils.MoveElement(
            doc, comp_id, XYZ(center_x - current_x, center_y - current_y, 0))
        doc.Regenerate()
        bb = comp.get_BoundingBox(view)
    return bb


def _line_style_by_name(doc, names):
    try:
        lines_cat = doc.Settings.Categories.get_Item(BuiltInCategory.OST_Lines)
        for subcat in lines_cat.SubCategories:
            sub_name = safe_text(subcat.Name).lower()
            for name in names:
                if name.lower() == sub_name:
                    return subcat.GetGraphicsStyle(GraphicsStyleType.Projection)
        for subcat in lines_cat.SubCategories:
            sub_name = safe_text(subcat.Name).lower()
            if u"thin" in sub_name:
                return subcat.GetGraphicsStyle(GraphicsStyleType.Projection)
    except Exception:
        pass
    return None


def _delete_table_lines(doc, view):
    lines = FilteredElementCollector(doc, view.Id) \
        .OfCategory(BuiltInCategory.OST_Lines) \
        .WhereElementIsNotElementType().ToElements()
    for line in lines:
        if _param_text(line, BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS) == TABLE_LINE_MARKER:
            try:
                doc.Delete(line.Id)
            except Exception:
                pass


def _draw_detail_line(doc, view, p0, p1, line_style):
    detail = doc.Create.NewDetailCurve(view, Line.CreateBound(p0, p1))
    if line_style is not None:
        try:
            detail.LineStyle = line_style
        except Exception:
            pass
    try:
        p = detail.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
        if p is not None and not p.IsReadOnly:
            p.Set(TABLE_LINE_MARKER)
    except Exception:
        pass
    return detail


def _draw_table(doc, view, x_lines, top_y, header_height, row_height, row_count):
    if row_count < 1:
        return
    line_style = _line_style_by_name(doc, (u"Thin Lines", u"<Thin Lines>"))
    header_bottom_y = top_y - header_height
    for i in range(row_count + 2):
        if i == 0:
            y = top_y
        elif i == 1:
            y = header_bottom_y
        else:
            y = top_y - header_height - (row_height * (i - 1))
        _draw_detail_line(doc, view, XYZ(x_lines[0], y, 0), XYZ(x_lines[-1], y, 0), line_style)


def _float_cfg(cfg, key, default):
    try:
        return float(cfg.get(key, default))
    except Exception:
        return default


def generate(doc, source_view, legend_view, cfg=None):
    """Rebuilds a beam mark legend.

    The legend must contain one seed Legend Component. The source view supplies
    mark filter overrides; if it uses a view template, the template is read.
    Returns (rows_created, message).
    """
    if source_view is None:
        return (0, u"No source view selected.")
    if legend_view is None or legend_view.ViewType != ViewType.Legend:
        return (0, u"Select a Legend view to build into.")

    seeds = find_components(doc, legend_view)
    if not seeds:
        return (0, u"No seed legend component in the target legend. Drag any beam type into the legend once, then run again.")
    seed = seeds[0]

    cfg = cfg or {}
    source_scope = cfg.get("source_scope", u"model")
    rows = _beam_rows(doc, source_view, source_scope)
    if not rows:
        if source_scope == u"view":
            return (0, u"No beam Marks found on Structural Framing in the selected source view.")
        return (0, u"No beam Marks found on Structural Framing.")
    title_tt = get_texttype_by_id(doc, cfg.get("title_type_id"))
    label_tt = get_texttype_by_id(doc, cfg.get("label_type_id"))
    fallback_text_type_id = _text_type_id(doc)
    if title_tt is None and fallback_text_type_id is not None:
        title_type_id = fallback_text_type_id
    elif title_tt is not None:
        title_type_id = title_tt.Id
    else:
        title_type_id = None
    if label_tt is None and fallback_text_type_id is not None:
        label_type_id = fallback_text_type_id
    elif label_tt is not None:
        label_type_id = label_tt.Id
    else:
        label_type_id = None
    if title_type_id is None or label_type_id is None:
        return (0, u"No text types in this model.")

    mark_overrides = _filter_overrides_by_mark(doc, source_view)

    title_text = cfg.get("title_text", DEFAULT_TITLE) or DEFAULT_TITLE
    row_gap_mm = _float_cfg(cfg, "row_spacing_mm", ROW_GAP_MM)
    mark_to_component_mm = _float_cfg(cfg, "mark_to_component_mm", COMP_COL_MM)
    component_to_size_mm = _float_cfg(cfg, "component_to_size_mm", SIZE_COL_MM - COMP_COL_MM)

    seed_bb = seed.get_BoundingBox(legend_view)
    start_x = seed_bb.Min.X if seed_bb else 0.0
    start_y = seed_bb.Max.Y if seed_bb else 0.0
    row_height = mm_to_ft(max(row_gap_mm, 450.0))
    header_height = mm_to_ft(TABLE_HEADER_HEIGHT_MM)
    table_top_y = start_y + mm_to_ft(900.0)
    title_y = table_top_y + mm_to_ft(550.0)

    pad = mm_to_ft(TABLE_PADDING_MM)
    comp_half = mm_to_ft(COMPONENT_LENGTH_MM / 2.0)
    comp_center_x = start_x + mm_to_ft(mark_to_component_mm)
    mark_left_x = start_x - pad
    comp_left_col_x = comp_center_x - comp_half - pad
    comp_right_col_x = comp_center_x + comp_half + pad
    size_right_x = comp_right_col_x + mm_to_ft(max(component_to_size_mm, 1600.0))
    mark_text_x = mark_left_x + pad
    size_text_x = comp_right_col_x + pad
    mark_header_x = (mark_left_x + comp_left_col_x) / 2.0
    type_header_x = (comp_left_col_x + size_right_x) / 2.0
    header_y = table_top_y - (header_height / 2.0)

    t = Transaction(doc, u"BKD Beam Legend")
    t.Start()
    try:
        for c in find_components(doc, legend_view):
            if idv(c.Id) != idv(seed.Id):
                try:
                    doc.Delete(c.Id)
                except Exception:
                    pass
        for tn in FilteredElementCollector(doc, legend_view.Id).OfClass(TextNote).ToElements():
            try:
                doc.Delete(tn.Id)
            except Exception:
                pass
        _delete_table_lines(doc, legend_view)

        _create_left_middle_text(doc, legend_view, XYZ(start_x, title_y, 0),
                                 title_text, title_type_id)
        _create_center_middle_text(doc, legend_view, XYZ(mark_header_x, header_y, 0),
                                   u"Beam Mark", label_type_id)
        _create_center_middle_text(doc, legend_view, XYZ(type_header_x, header_y, 0),
                                   u"Type", label_type_id)

        count = 0
        for i, row in enumerate(rows):
            if i == 0:
                comp_id = seed.Id
            else:
                new_ids = ElementTransformUtils.CopyElement(doc, seed.Id, XYZ(mm_to_ft(1.0), 0, 0))
                comp_id = list(new_ids)[0]
            comp = doc.GetElement(comp_id)
            _set_component_type(doc, comp, row["type_id"])
            _set_component_length(comp, COMPONENT_LENGTH_MM)
            doc.Regenerate()
            row_mid_y = table_top_y - header_height - (row_height * (i + 0.5))
            _move_component_center_to(doc, legend_view, comp_id, comp_center_x, row_mid_y)
            if row["mark"] in mark_overrides:
                try:
                    legend_view.SetElementOverrides(comp_id, mark_overrides[row["mark"]])
                except Exception:
                    pass
            _create_left_middle_text(doc, legend_view,
                                     XYZ(mark_text_x, row_mid_y, 0),
                                     row["mark"], label_type_id)
            _create_left_middle_text(doc, legend_view, XYZ(size_text_x, row_mid_y, 0),
                                     row["size"], label_type_id)
            count += 1

        _draw_table(
            doc, legend_view,
            [mark_left_x, comp_left_col_x, comp_right_col_x, size_right_x],
            table_top_y, header_height, row_height, count)

        t.Commit()
    except Exception as ex:
        if t.HasStarted():
            t.RollBack()
        return (0, u"Error: " + safe_text(ex))

    return (count, u"ok")
