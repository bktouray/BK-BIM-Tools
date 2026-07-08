# -*- coding: utf-8 -*-
__title__ = u"Wall\nLegend"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Auto-generate a wall-type legend.

Places a labeled Legend Component per wall type, with a title. Needs a
one-time seed legend first (Project Browser > Legends > New Legend, drag
in any one wall type).
"""

from pyrevit import forms, script
import bkd_walllegend as wl
from Autodesk.Revit.DB import (
    FilteredElementCollector, View, ViewType, TextNoteType,
)

doc = __revit__.ActiveUIDocument.Document
view = doc.ActiveView
output = script.get_output()

WALL_VIEW_TYPES = (
    ViewType.FloorPlan, ViewType.CeilingPlan, ViewType.EngineeringPlan,
    ViewType.AreaPlan, ViewType.Section, ViewType.Elevation,
    ViewType.Detail, ViewType.ThreeD,
)


def choose_source(cfg):
    """Fill cfg['source'] (+ source_view_id / type_ids). Returns False on cancel."""
    mode = forms.alert(
        u"Where should the wall types come from?",
        title=__title__,
        options=[u"From a specific view", u"Used in whole model",
                 u"Pick from list", u"All wall types"])
    if not mode:
        return False

    if mode == u"From a specific view":
        views = [v for v in FilteredElementCollector(doc).OfClass(View).ToElements()
                 if (not v.IsTemplate) and v.ViewType in WALL_VIEW_TYPES]
        vmap = {}
        for v in views:
            vmap[u"{0}  [{1}]".format(v.Name, v.ViewType)] = v
        pick = forms.SelectFromList.show(
            sorted(vmap.keys()),
            title=u"Pick the view to read wall types from",
            multiselect=False)
        if not pick:
            return False
        cfg["source"] = "view"
        cfg["source_view_id"] = wl.idv(vmap[pick].Id)

    elif mode == u"Used in whole model":
        cfg["source"] = "model"

    elif mode == u"All wall types":
        cfg["source"] = "all"

    else:  # Pick from list
        nmap = {}
        for wt in FilteredElementCollector(doc).OfClass(wl.WallType).ToElements():
            nmap[wl.name_of(wt)] = wt
        picked = forms.SelectFromList.show(
            sorted(nmap.keys()),
            title=u"Select wall types for the legend",
            multiselect=True)
        if not picked:
            return False
        cfg["source"] = "list"
        cfg["type_ids"] = [wl.idv(nmap[n].Id) for n in picked]

    return True


def choose_text_type(purpose):
    tmap = {}
    for t in FilteredElementCollector(doc).OfClass(TextNoteType).ToElements():
        tmap[wl.name_of(t)] = t
    if not tmap:
        forms.alert(u"No text types in this model.", title=__title__)
        return None
    pick = forms.SelectFromList.show(
        sorted(tmap.keys()),
        title=u"Pick the text type for the {0}".format(purpose),
        multiselect=False)
    if not pick:
        return None
    return wl.idv(tmap[pick].Id)


def main():
    if not isinstance(view, View) or view.ViewType != ViewType.Legend:
        legends = [v for v in FilteredElementCollector(doc).OfClass(View).ToElements()
                   if v.ViewType == ViewType.Legend and not v.IsTemplate]
        msg = u"Open a Legend view first, then run this button."
        if legends:
            msg += u"\n\nExisting legend views:\n" + \
                u"\n".join(u"  - " + v.Name for v in legends)
        else:
            msg += (u"\n\nNo legend views exist yet. One-time setup:\n"
                    u"1. Project Browser -> right-click 'Legends' -> New Legend.\n"
                    u"2. Drag any one wall type into it (the 'seed').")
        forms.alert(msg, title=__title__)
        return

    if not wl.find_components(doc, view):
        forms.alert(
            u"This legend has no legend component to use as a seed.\n\n"
            u"Drag ANY one wall type from the Project Browser into this\n"
            u"legend once, then run the button again.",
            title=__title__)
        return

    cfg = wl.load_config(doc) or {}

    if not choose_source(cfg):
        return

    title_type_id = choose_text_type(u"TITLE text")
    if not title_type_id:
        return
    label_type_id = choose_text_type(u"wall-type LABELS")
    if not label_type_id:
        return
    cfg["title_type_id"] = title_type_id
    cfg["label_type_id"] = label_type_id

    title_text = forms.ask_for_string(
        default=cfg.get("title_text", u"WALL TYPE LEGEND"),
        prompt=u"Legend title:", title=__title__)
    if title_text is None:
        return
    cfg["title_text"] = title_text

    cfg["legend_view_id"] = wl.idv(view.Id)

    auto = forms.alert(
        u"Auto-refresh this legend whenever you open it and the wall\n"
        u"types have changed? (Uses these same choices silently.)",
        title=__title__, yes=True, no=True)
    cfg["auto"] = bool(auto)

    wl.save_config(doc, cfg)

    count, msg = wl.generate(doc, view, cfg)
    if msg != u"ok":
        forms.alert(msg, title=__title__)
        return

    output.print_md(u"## Wall legend: **{0}** rows generated".format(count))
    output.print_md(u"Auto-refresh: **{0}**".format(u"ON" if cfg["auto"] else u"OFF"))


if __name__ == "__main__":
    main()
