# -*- coding: utf-8 -*-
"""Shared logic for the BKDesigns Wall Legend tool.

Used by both the pushbutton (interactive) and the view-activated hook
(silent auto-refresh). Keeps NO UI code so it is safe to import anywhere.
"""
import os
import json

import clr
clr.AddReference("RevitAPI")
from Autodesk.Revit.DB import (
    FilteredElementCollector, BuiltInCategory, BuiltInParameter,
    Wall, WallType, View, ViewType, Element,
    Transaction, ElementTransformUtils, TextNote, XYZ,
)

ROW_GAP_MM = 500.0
TEXT_GAP_MM = 300.0


# ---------- small helpers ----------
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


# ---------- config (per project) ----------
def _config_path(doc):
    title = doc.Title or u"untitled"
    safe = u"".join(c if c.isalnum() else u"_" for c in title)
    base = os.path.join(os.getenv("APPDATA"), "pyRevit")
    try:
        if not os.path.isdir(base):
            os.makedirs(base)
    except Exception:
        pass
    return os.path.join(base, "bkd_walllegend_" + safe + ".json")


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


# ---------- wall type resolution ----------
def _all_types(doc):
    return list(FilteredElementCollector(doc).OfClass(WallType).ToElements())


def current_type_ids(doc, cfg):
    """The CURRENT set of wall type ids implied by the config's source."""
    src = cfg.get("source", "model")
    if src == "all":
        return set(idv(wt.Id) for wt in _all_types(doc))
    if src == "list":
        return set(cfg.get("type_ids", []))
    if src == "view":
        v = get_view_by_id(doc, cfg.get("source_view_id"))
        if v is None:
            return set()
        ids = set()
        for w in FilteredElementCollector(doc, v.Id).OfClass(Wall) \
                .WhereElementIsNotElementType().ToElements():
            try:
                ids.add(idv(w.GetTypeId()))
            except Exception:
                pass
        return ids
    # model
    ids = set()
    for w in FilteredElementCollector(doc).OfClass(Wall) \
            .WhereElementIsNotElementType().ToElements():
        try:
            ids.add(idv(w.GetTypeId()))
        except Exception:
            pass
    return ids


def wall_width(wt):
    """Total wall thickness in feet; 0 for kinds without a width (curtain)."""
    try:
        return wt.Width
    except Exception:
        return 0.0


def core_thickness(wt):
    """Thickness of the structural core layers only (feet).
    Falls back to total width when there's no compound structure."""
    try:
        cs = wt.GetCompoundStructure()
        if cs is None:
            return wall_width(wt)
        first = cs.GetFirstCoreLayerIndex()
        last = cs.GetLastCoreLayerIndex()
        total = 0.0
        for i in range(first, last + 1):
            total += cs.GetLayerWidth(i)
        return total
    except Exception:
        return wall_width(wt)


def _group_rank(wt):
    """ARC walls first (0), then STR walls (1), then anything else (2)."""
    n = name_of(wt).upper()
    if "_ARC" in n:
        return 0
    if "_STR" in n:
        return 1
    return 2


def resolve_types(doc, cfg):
    by_id = {}
    for wt in _all_types(doc):
        by_id[idv(wt.Id)] = wt
    chosen = [by_id[i] for i in current_type_ids(doc, cfg) if i in by_id]
    # ARC before STR; then core thickness; then total thickness; name breaks ties
    chosen.sort(key=lambda wt: (_group_rank(wt), core_thickness(wt),
                                wall_width(wt), name_of(wt)))
    return chosen


def needs_update(doc, cfg):
    """True if the live set of wall types differs from what was last drawn."""
    last = set(cfg.get("last_type_ids", []))
    return current_type_ids(doc, cfg) != last


# ---------- legend building ----------
def find_components(doc, view):
    return list(FilteredElementCollector(doc, view.Id)
                .OfCategory(BuiltInCategory.OST_LegendComponents)
                .WhereElementIsNotElementType().ToElements())


def _place_row(doc, view, comp_id, wall_type, target_x, top_y, label_type_id):
    comp = doc.GetElement(comp_id)
    p = comp.get_Parameter(BuiltInParameter.LEGEND_COMPONENT)
    if p is not None and not p.IsReadOnly:
        p.Set(wall_type.Id)
    doc.Regenerate()

    bb = comp.get_BoundingBox(view)
    if bb is not None:
        ElementTransformUtils.MoveElement(
            doc, comp_id, XYZ(target_x - bb.Min.X, top_y - bb.Max.Y, 0))
        doc.Regenerate()
        bb = comp.get_BoundingBox(view)

    if bb is None:
        return top_y - mm_to_ft(ROW_GAP_MM)

    TextNote.Create(doc, view.Id,
                    XYZ(bb.Max.X + mm_to_ft(TEXT_GAP_MM), bb.Max.Y, 0),
                    name_of(wall_type), label_type_id)
    return bb.Min.Y - mm_to_ft(ROW_GAP_MM)


def generate(doc, legend_view, cfg):
    """Rebuild the legend from cfg. Opens its own transaction.
    Returns (rows_created, message)."""
    seeds = find_components(doc, legend_view)
    if not seeds:
        return (0, u"No seed legend component in this legend.")
    seed = seeds[0]

    wall_types = resolve_types(doc, cfg)
    if not wall_types:
        return (0, u"No wall types resolved from the chosen source.")

    title_tt = get_texttype_by_id(doc, cfg.get("title_type_id"))
    label_tt = get_texttype_by_id(doc, cfg.get("label_type_id"))
    if label_tt is None:
        label_tt = title_tt
    if title_tt is None:
        title_tt = label_tt
    if label_tt is None:
        return (0, u"Stored text type no longer exists.")

    title_text = cfg.get("title_text", u"WALL TYPE LEGEND")

    seed_bb = seed.get_BoundingBox(legend_view)
    start_x = seed_bb.Min.X if seed_bb else 0.0
    start_y = seed_bb.Max.Y if seed_bb else 0.0
    try:
        title_gap = mm_to_ft(8.0 * legend_view.Scale)
    except Exception:
        title_gap = mm_to_ft(800.0)

    t = Transaction(doc, u"BKD Wall Legend")
    t.Start()
    try:
        # clear previous rows: components (except seed) + all text notes
        for c in find_components(doc, legend_view):
            if idv(c.Id) != idv(seed.Id):
                try:
                    doc.Delete(c.Id)
                except Exception:
                    pass
        for tn in FilteredElementCollector(doc, legend_view.Id) \
                .OfClass(TextNote).ToElements():
            try:
                doc.Delete(tn.Id)
            except Exception:
                pass

        # title
        try:
            TextNote.Create(doc, legend_view.Id,
                            XYZ(start_x, start_y + title_gap, 0),
                            title_text, title_tt.Id)
        except Exception:
            pass

        cursor_y = start_y
        count = 0
        for i, wt in enumerate(wall_types):
            if i == 0:
                comp_id = seed.Id
            else:
                new_ids = ElementTransformUtils.CopyElement(
                    doc, seed.Id, XYZ(mm_to_ft(1.0), 0, 0))
                comp_id = list(new_ids)[0]
            try:
                cursor_y = _place_row(doc, legend_view, comp_id, wt,
                                      start_x, cursor_y, label_tt.Id)
                count += 1
            except Exception:
                pass

        t.Commit()
    except Exception as ex:
        if t.HasStarted():
            t.RollBack()
        return (0, u"Error: " + unicode(ex))

    cfg["last_type_ids"] = sorted(current_type_ids(doc, cfg))
    save_config(doc, cfg)
    return (count, u"ok")
