# -*- coding: utf-8 -*-
"""Cuts one detail Section view per "typical" Column/Beam/Footing - grouped
by the element's own current Mark (product owner, 2026-07-14: requires
Auto Mark to already be run, so Mark IS the authoritative "same typical
section" signal - two elements sharing a Mark are, by definition, the same
size+reinforcement group Auto Mark already computed).

View geometry, confirmed live against the real model before writing this
(see chat history 2026-07-14 and 2026-07-18 - Revit's ViewSection creation
derives RightDirection=BasisX, ViewDirection=-BasisZ, UpDirection=BasisX x
BasisZ from the BoundingBoxXYZ.Transform - NOT the naive "BasisZ is the view
direction" assumption). Use `CreateDetail` whenever the project has a Detail
view family type; falling back to `CreateSection` is only for projects with no
Detail type loaded:

- Column: a horizontal detail at the column's own mid-height.
- Footing: a plan-style detail cut from above, looking down into the footing.
  Its cut plane is user-adjustable above the footing's own top face (default
  150mm, product owner 2026-07-18), with the crop depth running downward and
  the far clip extended past the footing's own bottom face by its own
  user-adjustable margin (default 150mm).
- Beam: BasisZ = -beam_dir, BasisX = world_Z x beam_dir -> ViewDirection
  ends up aligned with the beam's own length axis (so its cross-section
  shows as a rectangle) and UpDirection comes out as world Z (height reads
  vertical). Cut plane = the beam's own mid-span, with the crop centered on
  the beam's bbox mid-depth, not on LocationCurve.Z (real projects often
  place that curve at the top of beam).

Far/Near Clip Offset are always explicitly SET after creation (not left to
whatever CreateSection derives from the box - confirmed live it defaults to
150mm regardless of the box's own Z depth, not the user's requested value).

IronPython 2.7.
"""

import re

import System
from pyrevit import DB

_MM = 304.8
_NEAR_REVEAL_MM = 50.0  # small fixed reveal on the near (viewer) side of the cut plane
_PLAN_MARGIN_MM = 500.0  # crop margin beyond the element's own footprint, columns/footings


def _name(el):
    try:
        return el.Name
    except Exception:
        return DB.Element.Name.__get__(el)


def list_typical_view_family_types(doc):
    """Detail view types first, with Section as fallback only when needed."""
    vfts = DB.FilteredElementCollector(doc).OfClass(DB.ViewFamilyType).ToElements()
    detail_vfts = [v for v in vfts if v.ViewFamily == DB.ViewFamily.Detail]
    if detail_vfts:
        return sorted(detail_vfts, key=lambda v: _name(v).lower())

    section_vfts = [v for v in vfts if v.ViewFamily == DB.ViewFamily.Section]
    return sorted(section_vfts, key=lambda v: _name(v).lower())


def pick_section_view_family_type(doc):
    types = list_typical_view_family_types(doc)
    return types[0] if types else None


def _unique_view_name(doc, base_name):
    """Revit requires every View.Name to be unique project-wide. Appends
    ' (2)', ' (3)'... until free - lets per-instance mode create many views
    sharing one Mark's base name without colliding.
    """
    existing = set(v.Name for v in DB.FilteredElementCollector(doc).OfClass(DB.View).ToElements())
    if base_name not in existing:
        return base_name
    i = 2
    while u"{0} ({1})".format(base_name, i) in existing:
        i += 1
    return u"{0} ({1})".format(base_name, i)


def _sanitize_for_view_name(text):
    # Revit view names disallow \ : { } [ ] | ; < > ? ` ~
    return re.sub(r'[\\:{}\[\]|;<>?`~]', u"-", text or u"")


def view_name_for(category_label, mark, suffix=None):
    base = u"{0} - {1} Detail Section".format(_sanitize_for_view_name(mark), category_label)
    if suffix:
        base = u"{0} ({1})".format(base, suffix)
    return base


def _set_clip_offsets(view, far_ft, near_ft):
    far_p = view.get_Parameter(DB.BuiltInParameter.VIEWER_BOUND_OFFSET_FAR)
    if far_p is not None and not far_p.IsReadOnly:
        far_p.Set(far_ft)
    near_p = view.get_Parameter(DB.BuiltInParameter.VIEWER_BOUND_OFFSET_NEAR)
    if near_p is not None and not near_p.IsReadOnly:
        near_p.Set(near_ft)


def _finalize_view(doc, view, far_ft, near_ft, view_name):
    doc.Regenerate()
    _set_clip_offsets(view, far_ft, near_ft)
    _set_detail_level_fine(view)
    view.Name = _unique_view_name(doc, view_name)
    _hide_marker_in_project_views(doc, view)


def _set_detail_level_fine(view):
    try:
        view.DetailLevel = DB.ViewDetailLevel.Fine
    except Exception:
        p = view.get_Parameter(DB.BuiltInParameter.VIEW_DETAIL_LEVEL)
        if p is not None and not p.IsReadOnly:
            p.Set(int(DB.ViewDetailLevel.Fine))


def _hide_marker_in_project_views(doc, marker_view):
    """Hide the created section/detail marker in every ordinary view.

    The detail view itself remains usable from Project Browser; this only
    removes the section/callout marker graphics that otherwise clutter plans,
    elevations, and sections.
    """
    ids = System.Collections.Generic.List[DB.ElementId]()
    ids.Add(marker_view.Id)
    for view in DB.FilteredElementCollector(doc).OfClass(DB.View).ToElements():
        if view.Id == marker_view.Id:
            continue
        try:
            if view.IsTemplate or not view.AreGraphicsOverridesAllowed():
                continue
            if marker_view.CanBeHidden(view):
                view.HideElements(ids)
        except Exception:
            continue


def _create_detail_or_section(doc, vft_id, box):
    vft = doc.GetElement(vft_id)
    if vft is not None and vft.ViewFamily == DB.ViewFamily.Detail:
        return DB.ViewSection.CreateDetail(doc, vft_id, box)
    return DB.ViewSection.CreateSection(doc, vft_id, box)


def _bbox_corners(bbox):
    return [
        DB.XYZ(x, y, z)
        for x in (bbox.Min.X, bbox.Max.X)
        for y in (bbox.Min.Y, bbox.Max.Y)
        for z in (bbox.Min.Z, bbox.Max.Z)
    ]


def _projected_half_extent(points, origin, axis):
    out = 0.0
    for p in points:
        out = max(out, abs((p - origin).DotProduct(axis)))
    return out


# ---------------------------------------------------------------------------
# Column / Footing: horizontal, looking-down section
# ---------------------------------------------------------------------------

def _looking_down_transform(origin):
    tr = DB.Transform.Identity
    tr.Origin = origin
    basis_x = DB.XYZ(-1, 0, 0)
    basis_z = DB.XYZ(0, 0, 1)
    tr.BasisX = basis_x
    tr.BasisZ = basis_z
    tr.BasisY = basis_x.CrossProduct(basis_z)
    return tr


def _footing_top_down_transform(origin):
    """Plan-style footing detail: east-right, north-up, depth goes down."""
    tr = DB.Transform.Identity
    tr.Origin = origin
    basis_x = DB.XYZ(1, 0, 0)
    basis_z = DB.XYZ(0, 0, -1)
    tr.BasisX = basis_x
    tr.BasisZ = basis_z
    tr.BasisY = basis_x.CrossProduct(basis_z)
    return tr


def cut_column_section(doc, vft_id, column, far_clip_ft, view_name):
    """Horizontal section at the column's own mid-height."""
    bbox = column.get_BoundingBox(None)
    if bbox is None:
        return None
    cx = (bbox.Max.X + bbox.Min.X) / 2.0
    cy = (bbox.Max.Y + bbox.Min.Y) / 2.0
    mid_z = (bbox.Max.Z + bbox.Min.Z) / 2.0
    half_x = (bbox.Max.X - bbox.Min.X) / 2.0 + (_PLAN_MARGIN_MM / _MM)
    half_y = (bbox.Max.Y - bbox.Min.Y) / 2.0 + (_PLAN_MARGIN_MM / _MM)
    near_ft = _NEAR_REVEAL_MM / _MM

    box = DB.BoundingBoxXYZ()
    box.Transform = _looking_down_transform(DB.XYZ(cx, cy, mid_z))
    box.Min = DB.XYZ(-half_x, -half_y, -far_clip_ft)
    box.Max = DB.XYZ(half_x, half_y, near_ft)

    view = _create_detail_or_section(doc, vft_id, box)
    _finalize_view(doc, view, far_clip_ft, near_ft, view_name)
    return view


def cut_footing_section(doc, vft_id, footing, above_top_ft, below_bottom_margin_ft, view_name):
    """Horizontal section above the footing's own top face, far clip extended
    past the footing's own bottom face by below_bottom_margin_ft - guarantees
    the whole footing is always inside the crop regardless of its thickness.
    """
    bbox = footing.get_BoundingBox(None)
    if bbox is None:
        return None
    cx = (bbox.Max.X + bbox.Min.X) / 2.0
    cy = (bbox.Max.Y + bbox.Min.Y) / 2.0
    top_z = bbox.Max.Z
    bottom_z = bbox.Min.Z
    cut_z = top_z + above_top_ft
    far_clip_ft = (cut_z - bottom_z) + below_bottom_margin_ft
    half_x = (bbox.Max.X - bbox.Min.X) / 2.0 + (_PLAN_MARGIN_MM / _MM)
    half_y = (bbox.Max.Y - bbox.Min.Y) / 2.0 + (_PLAN_MARGIN_MM / _MM)
    near_ft = 0.0

    box = DB.BoundingBoxXYZ()
    box.Transform = _footing_top_down_transform(DB.XYZ(cx, cy, cut_z))
    box.Min = DB.XYZ(-half_x, -half_y, near_ft)
    box.Max = DB.XYZ(half_x, half_y, far_clip_ft)

    view = _create_detail_or_section(doc, vft_id, box)
    _finalize_view(doc, view, far_clip_ft, near_ft, view_name)
    return view


# ---------------------------------------------------------------------------
# Beam: section perpendicular to its own length axis
# ---------------------------------------------------------------------------

def cut_beam_section(doc, vft_id, beam, far_clip_ft, view_name):
    """Section at the beam's own mid-span, cut perpendicular to its length
    (view direction runs along the beam's axis, so its cross-section shows
    as a rectangle; height reads vertical).
    """
    loc = beam.Location
    if not isinstance(loc, DB.LocationCurve):
        return None
    curve = loc.Curve
    p0 = curve.GetEndPoint(0)
    p1 = curve.GetEndPoint(1)
    beam_dir = (p1 - p0)
    if beam_dir.GetLength() <= 1e-9:
        return None
    beam_dir = beam_dir.Normalize()

    bbox = beam.get_BoundingBox(None)
    curve_mid = (p0 + p1) / 2.0
    if bbox is not None:
        origin = DB.XYZ(curve_mid.X, curve_mid.Y, (bbox.Max.Z + bbox.Min.Z) / 2.0)
    else:
        origin = curve_mid

    tr = DB.Transform.Identity
    tr.Origin = origin
    basis_x = DB.XYZ(0, 0, 1).CrossProduct(beam_dir)
    if basis_x.GetLength() <= 1e-9:
        # beam is vertical (shouldn't normally happen for OST_StructuralFraming) - fall back to world X
        basis_x = DB.XYZ(1, 0, 0)
    else:
        basis_x = basis_x.Normalize()
    basis_z = beam_dir.Negate()
    tr.BasisX = basis_x
    tr.BasisZ = basis_z
    tr.BasisY = basis_x.CrossProduct(basis_z)

    if bbox is not None:
        corners = _bbox_corners(bbox)
        half_w = _projected_half_extent(corners, origin, basis_x) + (_PLAN_MARGIN_MM / _MM)
        half_h = _projected_half_extent(corners, origin, tr.BasisY) + (_PLAN_MARGIN_MM / _MM)
    else:
        half_w = _PLAN_MARGIN_MM / _MM
        half_h = _PLAN_MARGIN_MM / _MM
    near_ft = _NEAR_REVEAL_MM / _MM

    box = DB.BoundingBoxXYZ()
    box.Transform = tr
    box.Min = DB.XYZ(-half_w, -half_h, -far_clip_ft)
    box.Max = DB.XYZ(half_w, half_h, near_ft)

    view = _create_detail_or_section(doc, vft_id, box)
    _finalize_view(doc, view, far_clip_ft, near_ft, view_name)
    return view


# ---------------------------------------------------------------------------
# Grouping + orchestration
# ---------------------------------------------------------------------------

MODE_PER_GROUP = u"per_group"
MODE_PER_INSTANCE = u"per_instance"


class TypicalViewsResult(object):
    def __init__(self):
        self.created = 0
        self.skipped = 0
        self.errors = []


def group_by_mark(elements):
    """Return [(mark, [elements...]), ...] ordered by first appearance.
    Elements with a blank/missing Mark are returned separately by
    unmarked_elements() - callers should check that first (Auto Mark is
    required to have been run, per product owner, 2026-07-14).
    """
    groups = {}
    order = []
    for e in elements:
        mp = e.LookupParameter(u"Mark")
        mark = mp.AsString() if mp else None
        mark = (mark or u"").strip()
        if not mark:
            continue
        if mark not in groups:
            groups[mark] = []
            order.append(mark)
        groups[mark].append(e)
    return [(m, groups[m]) for m in order]


def unmarked_elements(elements):
    """Elements with a blank/missing Mark - non-empty means Auto Mark
    needs to be (re-)run for this category before Typical views can name
    anything meaningfully.
    """
    out = []
    for e in elements:
        mp = e.LookupParameter(u"Mark")
        mark = (mp.AsString() if mp else None) or u""
        if not mark.strip():
            out.append(e)
    return out


def cut_typical_views(doc, elements, category_label, cutter, mode=MODE_PER_GROUP, **cutter_kwargs):
    """Cuts detail sections for `elements` (already Mark-validated by the
    caller), grouped by Mark. `cutter` is one of cut_column_section/
    cut_beam_section/cut_footing_section; `cutter_kwargs` are its extra
    positional args after (doc, vft_id, element, ..., view_name) - passed
    through as keyword args matching each cutter's own signature via a thin
    per-category wrapper the pushbutton provides (see script.py).

    mode: MODE_PER_GROUP (default - one view for the group's first/
    representative instance, product owner: efficient default) or
    MODE_PER_INSTANCE (one view per individual element, product owner:
    "sometimes I want a detail cut section for each column").
    """
    res = TypicalViewsResult()
    for mark, members in group_by_mark(elements):
        targets = members if mode == MODE_PER_INSTANCE else [members[0]]
        for i, elem in enumerate(targets):
            suffix = None
            if mode == MODE_PER_INSTANCE and len(targets) > 1:
                suffix = i + 1
            view_name = view_name_for(category_label, mark, suffix=suffix)
            try:
                view = cutter(doc, elem, view_name, **cutter_kwargs)
                if view is None:
                    res.errors.append(u"Mark {0}: could not cut a view (no geometry).".format(mark))
                    res.skipped += 1
                    continue
                res.created += 1
            except Exception as e:
                res.errors.append(u"Mark {0}: {1}".format(mark, unicode(str(e))))
                res.skipped += 1
    return res
