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
from bkbim.ui.views.wall_legend_options import show_wall_legend_options
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

    views = sorted(
        (v for v in FilteredElementCollector(doc).OfClass(View).ToElements()
         if (not v.IsTemplate) and v.ViewType in WALL_VIEW_TYPES),
        key=lambda v: v.Name)
    wall_types = sorted(
        FilteredElementCollector(doc).OfClass(wl.WallType).ToElements(),
        key=wl.name_of)
    text_types = sorted(
        FilteredElementCollector(doc).OfClass(TextNoteType).ToElements(),
        key=wl.name_of)

    if not text_types:
        forms.alert(u"No text types in this model.", title=__title__)
        return

    result = show_wall_legend_options(views, wall_types, text_types, wl.name_of, wl.idv, cfg)
    if not result:
        return

    cfg["source"] = result.source
    if result.source == u"view":
        cfg["source_view_id"] = wl.idv(result.source_view.Id)
    if result.source == u"list":
        cfg["type_ids"] = [wl.idv(wt.Id) for wt in result.wall_types]
    cfg["title_type_id"] = wl.idv(result.title_type.Id)
    cfg["label_type_id"] = wl.idv(result.label_type.Id)
    cfg["title_text"] = result.title_text
    cfg["legend_view_id"] = wl.idv(view.Id)
    cfg["auto"] = result.auto

    wl.save_config(doc, cfg)

    count, msg = wl.generate(doc, view, cfg)
    if msg != u"ok":
        forms.alert(msg, title=__title__)
        return

    output.print_md(u"## Wall legend: **{0}** rows generated".format(count))
    output.print_md(u"Auto-refresh: **{0}**".format(u"ON" if cfg["auto"] else u"OFF"))


if __name__ == "__main__":
    main()
