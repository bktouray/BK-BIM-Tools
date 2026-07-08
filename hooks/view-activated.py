# -*- coding: utf-8 -*-
"""Auto-refresh the BKDesigns Wall Legend when it is opened.

Fires on every view activation, but does work ONLY when:
  - auto-refresh is enabled in this project's config, AND
  - the activated view is the managed legend, AND
  - the set of wall types has actually changed since the last build.
Kept defensive: any failure is swallowed so it never disrupts the user.
"""
try:
    from pyrevit import EXEC_PARAMS
    import bkd_walllegend as wl

    args = getattr(EXEC_PARAMS, "event_args", None) or globals().get("__eventargs__")

    doc = None
    actview = None
    if args is not None:
        doc = getattr(args, "Document", None)
        actview = getattr(args, "CurrentActiveView", None)
    if doc is None:
        doc = __revit__.ActiveUIDocument.Document
    if actview is None:
        actview = doc.ActiveView

    if doc is not None and actview is not None:
        cfg = wl.load_config(doc)
        if cfg and cfg.get("auto") \
                and actview.ViewType == wl.ViewType.Legend \
                and wl.idv(actview.Id) == cfg.get("legend_view_id"):
            if wl.find_components(doc, actview) and wl.needs_update(doc, cfg):
                wl.generate(doc, actview, cfg)
except Exception:
    pass
