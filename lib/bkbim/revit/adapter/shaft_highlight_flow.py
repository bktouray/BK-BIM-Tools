# -*- coding: utf-8 -*-
"""Highlight Shaft Openings in plan views with filled regions and optional X-lines.

This is deliberately a Revit-adapter slice rather than pure domain logic:
Shaft Opening geometry, FilledRegion creation, detail line styles, and detail
groups are all Revit API concerns. The flow mirrors the rest of the extension:
collect choices -> show one WPF options window -> execute each target view in
its own Transaction -> show one result dialog.
"""

import clr

clr.AddReference("RevitAPI")

import System
from System.Collections.Generic import List

from Autodesk.Revit.DB import (
    BuiltInCategory, BuiltInParameter, Color, CurveLoop, DetailCurve,
    ElementId, FilledRegion, FilledRegionType, FillPatternElement,
    FilteredElementCollector, GraphicsStyleType, Line, Transaction, ViewPlan,
    XYZ,
)

from bkbim.revit.adapter.multi_view_batch import alert_batch_results, run_across_views
from bkbim.ui.views.result_dialog import show_result
from bkbim.ui.views.shaft_highlight_options import (
    FILL_MODE_CUSTOM, show_shaft_highlight_options,
)

_TRANSACTION_LABEL = u"Highlight Shafts"
_GENERATED_MARKER = u"BKBIM Highlight Shafts"
_CUSTOM_FILL_TYPE_NAME = u"BK Shaft Highlight"
_GROUP_NAME_PREFIX = u"BK Shaft Highlights"
_EPS = 1e-6


def _name(elem):
    try:
        return elem.Name
    except Exception:
        return u"<unnamed>"


def _id_value(element_id):
    try:
        return element_id.Value
    except Exception:
        try:
            return element_id.IntegerValue
        except Exception:
            return None


def _view_name(view):
    return _name(view)


def _line_style_name(style):
    try:
        return style.GraphicsStyleCategory.Name
    except Exception:
        return _name(style)


def _plan_views(doc):
    views = []
    for view in FilteredElementCollector(doc).OfClass(ViewPlan).ToElements():
        try:
            if view.IsTemplate:
                continue
        except Exception:
            continue
        views.append(view)
    return sorted(views, key=lambda v: _name(v).lower())


def _filled_region_types(doc):
    return sorted(
        FilteredElementCollector(doc).OfClass(FilledRegionType).ToElements(),
        key=lambda t: _name(t).lower())


def _line_styles(doc):
    styles = []
    try:
        lines_cat = doc.Settings.Categories.get_Item(BuiltInCategory.OST_Lines)
        for subcat in lines_cat.SubCategories:
            style = subcat.GetGraphicsStyle(GraphicsStyleType.Projection)
            if style is not None:
                styles.append(style)
    except Exception:
        pass
    return sorted(styles, key=lambda s: _line_style_name(s).lower())


def _solid_fill_pattern_id(doc):
    for fp in FilteredElementCollector(doc).OfClass(FillPatternElement).ToElements():
        try:
            if fp.GetFillPattern().IsSolidFill:
                return fp.Id
        except Exception:
            continue
    return ElementId.InvalidElementId


def _set_param_string(elem, bip, value):
    try:
        param = elem.get_Parameter(bip)
        if param is not None and not param.IsReadOnly:
            param.Set(value)
            return True
    except Exception:
        pass
    return False


def _mark_generated(elem):
    _set_param_string(elem, BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS, _GENERATED_MARKER)


def _is_generated(elem):
    try:
        param = elem.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
        return param is not None and (param.AsString() or u"") == _GENERATED_MARKER
    except Exception:
        return False


def _delete_previous_generated(doc, view):
    generated = [
        elem for elem in FilteredElementCollector(doc, view.Id).WhereElementIsNotElementType().ToElements()
        if _is_generated(elem)]
    group_ids = set()
    for elem in generated:
        try:
            if elem.GetType().Name == u"Group":
                group_id = _id_value(elem.Id)
                if group_id is not None:
                    group_ids.add(group_id)
        except Exception:
            pass
    ids = List[ElementId]()
    for elem in generated:
        try:
            group_id = elem.GroupId
            if group_id is not None and _id_value(group_id) in group_ids:
                continue
        except Exception:
            pass
        ids.Add(elem.Id)
    if ids.Count:
        doc.Delete(ids)
    return ids.Count


def _get_or_create_custom_fill_type(doc, red, green, blue, boundary_style):
    existing = None
    types = _filled_region_types(doc)
    for fr_type in types:
        if _name(fr_type) == _CUSTOM_FILL_TYPE_NAME:
            existing = fr_type
            break
    if existing is None:
        if not types:
            return None
        existing = types[0].Duplicate(_CUSTOM_FILL_TYPE_NAME)

    color = Color(int(red), int(green), int(blue))
    solid_id = _solid_fill_pattern_id(doc)
    for attr_name in (
        u"ForegroundPatternId", u"BackgroundPatternId", u"FillPatternId"):
        try:
            setattr(existing, attr_name, solid_id)
        except Exception:
            pass
    for attr_name in (
        u"ForegroundPatternColor", u"BackgroundPatternColor", u"Color"):
        try:
            setattr(existing, attr_name, color)
        except Exception:
            pass
    if boundary_style is not None:
        try:
            existing.LineStyleId = boundary_style.Id
        except Exception:
            pass
    return existing


def _shaft_openings_in_view(doc, view):
    try:
        return list(
            FilteredElementCollector(doc, view.Id)
            .OfCategory(BuiltInCategory.OST_ShaftOpening)
            .WhereElementIsNotElementType()
            .ToElements())
    except Exception:
        return []


def _rect_from_bbox(elem, view):
    try:
        bbox = elem.get_BoundingBox(view)
        if bbox is None:
            bbox = elem.get_BoundingBox(None)
    except Exception:
        bbox = None
    if bbox is None:
        return None

    minx = min(bbox.Min.X, bbox.Max.X)
    maxx = max(bbox.Min.X, bbox.Max.X)
    miny = min(bbox.Min.Y, bbox.Max.Y)
    maxy = max(bbox.Min.Y, bbox.Max.Y)
    if (maxx - minx) <= _EPS or (maxy - miny) <= _EPS:
        return None

    try:
        z = view.Origin.Z
    except Exception:
        z = bbox.Min.Z

    return (
        XYZ(minx, miny, z),
        XYZ(maxx, miny, z),
        XYZ(maxx, maxy, z),
        XYZ(minx, maxy, z),
    )


def _curve_loop_from_points(points):
    loop = CurveLoop()
    for i in range(len(points)):
        loop.Append(Line.CreateBound(points[i], points[(i + 1) % len(points)]))
    return loop


def _outline_bbox(points):
    xs = [p.X for p in points]
    ys = [p.Y for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _boxes_intersect(a, b, tolerance=0.02):
    return not (
        a[2] < b[0] - tolerance or b[2] < a[0] - tolerance or
        a[3] < b[1] - tolerance or b[3] < a[1] - tolerance)


def _existing_manual_region_boxes(doc, view):
    boxes = []
    for region in FilteredElementCollector(doc, view.Id).OfClass(FilledRegion).ToElements():
        if _is_generated(region):
            continue
        try:
            bbox = region.get_BoundingBox(view)
        except Exception:
            bbox = None
        if bbox is None:
            continue
        boxes.append((
            min(bbox.Min.X, bbox.Max.X),
            min(bbox.Min.Y, bbox.Max.Y),
            max(bbox.Min.X, bbox.Max.X),
            max(bbox.Min.Y, bbox.Max.Y),
        ))
    return boxes


def _create_filled_region(doc, view, filled_region_type, points, boundary_style):
    loops = List[CurveLoop]()
    loops.Add(_curve_loop_from_points(points))
    region = FilledRegion.Create(doc, filled_region_type.Id, view.Id, loops)
    _mark_generated(region)
    if boundary_style is not None:
        try:
            region.SetLineStyleId(boundary_style.Id)
        except Exception:
            try:
                region.LineStyleId = boundary_style.Id
            except Exception:
                pass
    return region


def _create_x_lines(doc, view, points, line_style):
    created = []
    pairs = ((points[0], points[2]), (points[1], points[3]))
    for a, b in pairs:
        curve = doc.Create.NewDetailCurve(view, Line.CreateBound(a, b))
        _mark_generated(curve)
        if line_style is not None:
            try:
                curve.LineStyle = line_style
            except Exception:
                pass
        created.append(curve)
    return created


def _group_created(doc, view, created):
    if not created:
        return None
    ids = List[ElementId]()
    for elem in created:
        ids.Add(elem.Id)
    try:
        group = doc.Create.NewGroup(ids)
        _mark_generated(group)
        group.GroupType.Name = u"{0} - {1}".format(_GROUP_NAME_PREFIX, _name(view))
        return group
    except Exception:
        return None


def _apply_to_view(doc, view, options, filled_region_type):
    tx = Transaction(doc, _TRANSACTION_LABEL)
    tx.Start()
    try:
        deleted = _delete_previous_generated(doc, view)
        shafts = _shaft_openings_in_view(doc, view)
        manual_boxes = _existing_manual_region_boxes(doc, view)
        created = []
        skipped_existing = 0
        skipped_geometry = 0

        for shaft in shafts:
            points = _rect_from_bbox(shaft, view)
            if points is None:
                skipped_geometry += 1
                continue
            shaft_box = _outline_bbox(points)
            if any(_boxes_intersect(shaft_box, box) for box in manual_boxes):
                skipped_existing += 1
                continue
            region = _create_filled_region(
                doc, view, filled_region_type, points, options.boundary_style)
            created.append(region)
            if options.draw_x:
                created.extend(_create_x_lines(doc, view, points, options.x_style))

        grouped = False
        if options.group_results and created:
            grouped = _group_created(doc, view, created) is not None

        tx.Commit()
        msg = u"{0} shaft(s) highlighted".format(len(created) // (3 if options.draw_x else 1))
        details = []
        if deleted:
            details.append(u"{0} previous generated element(s) rebuilt".format(deleted))
        if skipped_existing:
            details.append(u"{0} skipped because a filled region already exists".format(skipped_existing))
        if skipped_geometry:
            details.append(u"{0} skipped because no plan outline was readable".format(skipped_geometry))
        if grouped:
            details.append(u"grouped")
        if details:
            msg += u" ({0})".format(u"; ".join(details))
        return (_name(view), msg)
    except Exception as exc:
        if tx.HasStarted():
            tx.RollBack()
        return (_name(view), u"Failed: {0}".format(unicode(str(exc))))


def _release_note_missing_data(views, filled_region_types, line_styles):
    if not views:
        return u"No plan views are available."
    if not filled_region_types:
        return u"No filled region types are available in this model."
    if not line_styles:
        return u"No detail line styles are available in this model."
    return None


def run_highlight_shafts_flow(doc, uidoc, active_view, title):
    views = _plan_views(doc)
    filled_region_types = _filled_region_types(doc)
    line_styles = _line_styles(doc)
    blocker = _release_note_missing_data(views, filled_region_types, line_styles)
    if blocker:
        show_result(title, blocker)
        return

    options = show_shaft_highlight_options(
        title, views, active_view, _view_name, filled_region_types, _name,
        line_styles, _line_style_name)
    if not options:
        return

    if options.fill_mode == FILL_MODE_CUSTOM:
        tx = Transaction(doc, u"Prepare Shaft Highlight Fill")
        tx.Start()
        try:
            filled_region_type = _get_or_create_custom_fill_type(
                doc, options.red, options.green, options.blue, options.boundary_style)
            tx.Commit()
        except Exception as exc:
            if tx.HasStarted():
                tx.RollBack()
            show_result(title, u"Could not create the shaft highlight filled region type:\n\n{0}".format(
                unicode(str(exc))))
            return
    else:
        filled_region_type = options.filled_region_type

    if filled_region_type is None:
        show_result(title, u"No filled region type is available for shaft highlighting.")
        return

    results = run_across_views(
        doc, options.selected_views, _TRANSACTION_LABEL,
        lambda view: _apply_to_view(doc, view, options, filled_region_type))
    alert_batch_results(results, title)
