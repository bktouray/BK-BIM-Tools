# -*- coding: utf-8 -*-
"""Cuts one detail Section view per "typical" Column/Beam/Footing - grouped
by the element's own current Mark (product owner, 2026-07-14: requires
Auto Mark to already be run, so Mark IS the authoritative "same typical
section" signal - two elements sharing a Mark are, by definition, the same
size+reinforcement group Auto Mark already computed).

View geometry, confirmed live against the real model before writing this
(see chat history 2026-07-14 - Revit's ViewSection.CreateSection derives
RightDirection=BasisX, ViewDirection=-BasisZ, UpDirection=BasisX x BasisZ
from the BoundingBoxXYZ.Transform - NOT the naive "BasisZ is the view
direction" assumption):

- Column/Footing: a horizontal, looking-STRAIGHT-DOWN section (BasisX=
  (-1,0,0), BasisZ=(0,0,1) -> ViewDirection=(0,0,-1), UpDirection=(0,1,0)
  north-up; RightDirection ends up (-1,0,0), a cosmetic east/west mirror
  that's unavoidable for a true look-down cut with north kept up - a
  worthwhile trade since structural drawings conventionally care about
  north-up far more than left/right). Column cut plane = the column's own
  mid-height. Footing cut plane = 200mm above the footing's own top face
  (product owner: "cut the detail view at 200mm above the footing"), far
  clip extended past the footing's own BOTTOM face by the same offset
  margin used for columns/beams (product owner: "far clip offset going
  below the footing" - interpreted as the same configurable offset, applied
  below the footing's real bottom rather than as a fixed thin slice, since
  a thin slice below a 200mm-above-top cut plane could miss the footing
  entirely depending on its thickness).
- Beam: BasisZ = -beam_dir, BasisX = world_Z x beam_dir -> ViewDirection
  ends up aligned with the beam's own length axis (so its cross-section
  shows as a rectangle) and UpDirection comes out as world Z (height reads
  vertical) - confirmed live, no north/south trade-off needed here since a
  beam's cross-section has no compass convention to preserve. Cut plane =
  the beam's own mid-span.

Far/Near Clip Offset are always explicitly SET after creation (not left to
whatever CreateSection derives from the box - confirmed live it defaults to
150mm regardless of the box's own Z depth, not the user's requested value).

IronPython 2.7.
"""

import re

from pyrevit import DB

_MM = 304.8
_NEAR_REVEAL_MM = 50.0  # small fixed reveal on the near (viewer) side of the cut plane
_PLAN_MARGIN_MM = 500.0  # crop margin beyond the element's own footprint, columns/footings


def _name(el):
    try:
        return el.Name
    except Exception:
        return DB.Element.Name.__get__(el)


def pick_section_view_family_type(doc):
    """Prefers a ViewFamilyType literally named "Detail Section" (matches
    the product owner's own words, "detail cut section"); falls back to
    whatever Section-family type exists first (confirmed live: this
    project only has "Building Section"/"Wall Section"/"Working Section" -
    no dedicated "Detail Section" type, which is a normal, valid Revit
    project state, not an error).
    """
    vfts = DB.FilteredElementCollector(doc).OfClass(DB.ViewFamilyType).ToElements()
    section_vfts = [v for v in vfts if v.ViewFamily == DB.ViewFamily.Section]
    if not section_vfts:
        return None
    detail = next((v for v in section_vfts if u"detail" in _name(v).lower()), None)
    return detail or section_vfts[0]


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
    view.Name = _unique_view_name(doc, view_name)


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

    view = DB.ViewSection.CreateSection(doc, vft_id, box)
    _finalize_view(doc, view, far_clip_ft, near_ft, view_name)
    return view


def cut_footing_section(doc, vft_id, footing, above_top_ft, below_bottom_margin_ft, view_name):
    """Horizontal section 200mm (above_top_ft) above the footing's own top
    face, far clip extended past the footing's own bottom face by
    below_bottom_margin_ft - guarantees the whole footing is always inside
    the crop regardless of its own thickness.
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
    near_ft = _NEAR_REVEAL_MM / _MM

    box = DB.BoundingBoxXYZ()
    box.Transform = _looking_down_transform(DB.XYZ(cx, cy, cut_z))
    box.Min = DB.XYZ(-half_x, -half_y, -far_clip_ft)
    box.Max = DB.XYZ(half_x, half_y, near_ft)

    view = DB.ViewSection.CreateSection(doc, vft_id, box)
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
    mid = (p0 + p1) / 2.0
    beam_dir = (p1 - p0)
    if beam_dir.GetLength() <= 1e-9:
        return None
    beam_dir = beam_dir.Normalize()

    tr = DB.Transform.Identity
    tr.Origin = mid
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

    bbox = beam.get_BoundingBox(None)
    depth_ft = (bbox.Max.Z - bbox.Min.Z) if bbox is not None else (300.0 / _MM)
    half_w = (bbox.Max.X - bbox.Min.X + bbox.Max.Y - bbox.Min.Y) / 2.0 + (_PLAN_MARGIN_MM / _MM) \
        if bbox is not None else (_PLAN_MARGIN_MM / _MM)
    half_h = depth_ft / 2.0 + (_PLAN_MARGIN_MM / _MM)
    near_ft = _NEAR_REVEAL_MM / _MM

    box = DB.BoundingBoxXYZ()
    box.Transform = tr
    box.Min = DB.XYZ(-half_w, -half_h, -far_clip_ft)
    box.Max = DB.XYZ(half_w, half_h, near_ft)

    view = DB.ViewSection.CreateSection(doc, vft_id, box)
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
