# -*- coding: utf-8 -*-
__title__ = u"Beam\nLegend"
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Build a beam mark legend from the active/source view filters.

Run from a drawing view to use that view/template as the filter source, then
choose a Legend view containing one seed beam Legend Component.
"""

from pyrevit import script
import bkd_beamlegend as bl
from bkbim.ui.views.beam_legend_options import show_beam_legend_options
from bkbim.ui.views.result_dialog import show_result
from Autodesk.Revit.DB import FilteredElementCollector, View, ViewType, TextNoteType

doc = __revit__.ActiveUIDocument.Document
active_view = doc.ActiveView
output = script.get_output()


SOURCE_VIEW_TYPES = (
    ViewType.FloorPlan, ViewType.CeilingPlan, ViewType.EngineeringPlan,
    ViewType.AreaPlan, ViewType.Section, ViewType.Elevation,
    ViewType.Detail, ViewType.ThreeD,
)


def _legend_views():
    return sorted(
        (v for v in FilteredElementCollector(doc).OfClass(View).ToElements()
         if v.ViewType == ViewType.Legend and not v.IsTemplate),
        key=lambda v: v.Name)


def _source_views():
    return sorted(
        (v for v in FilteredElementCollector(doc).OfClass(View).ToElements()
         if (not v.IsTemplate) and v.ViewType in SOURCE_VIEW_TYPES),
        key=lambda v: v.Name)


def main():
    source_views = _source_views()
    legends = _legend_views()
    text_types = sorted(
        FilteredElementCollector(doc).OfClass(TextNoteType).ToElements(),
        key=bl.name_of)

    if not legends:
        show_result(
            __title__,
            u"No Legend views exist yet.\n\n"
            u"Create a Legend view, drag any beam type into it once as a seed,\n"
            u"then run Beam Legend from your beam plan again.")
        return
    if not text_types:
        show_result(__title__, u"No text types in this model.")
        return

    default_source = None if active_view.ViewType == ViewType.Legend else active_view
    default_legend = active_view if active_view.ViewType == ViewType.Legend else None
    cfg = bl.load_config(doc) or {}

    result = show_beam_legend_options(
        source_views, legends, text_types, bl.name_of, bl.idv, cfg,
        default_source_view=default_source,
        default_legend_view=default_legend)
    if not result:
        return

    source_view = result.source_view
    legend_view = result.legend_view

    if not bl.find_components(doc, legend_view):
        show_result(
            __title__,
            u"The selected legend has no seed Legend Component.\n\n"
            u"Open that Legend view and drag any beam type into it once, then run again.")
        return

    cfg["source_scope"] = result.source_scope
    cfg["source_view_id"] = bl.idv(source_view.Id)
    cfg["legend_view_id"] = bl.idv(legend_view.Id)
    cfg["title_type_id"] = bl.idv(result.title_type.Id)
    cfg["label_type_id"] = bl.idv(result.label_type.Id)
    cfg["title_text"] = result.title_text
    cfg["row_spacing_mm"] = result.row_spacing_mm
    cfg["mark_to_component_mm"] = result.mark_to_component_mm
    cfg["component_to_size_mm"] = result.component_to_size_mm
    bl.save_config(doc, cfg)

    count, msg = bl.generate(doc, source_view, legend_view, cfg)
    if msg != u"ok":
        show_result(__title__, msg)
        return

    output.print_md(u"## Beam legend: **{0}** rows generated".format(count))
    output.print_md(u"Beam source: **{0}**".format(
        u"selected view only" if result.source_scope == u"view" else u"whole project"))
    output.print_md(u"Source view: **{0}**".format(source_view.Name))
    output.print_md(u"Legend view: **{0}**".format(legend_view.Name))
    show_result(
        __title__,
        u"Beam legend generated: {0} row(s).\n\nBeam source: {1}\nSource view:\n{2}\n\nLegend view:\n{3}".format(
            count,
            u"selected view only" if result.source_scope == u"view" else u"whole project",
            source_view.Name,
            legend_view.Name))


if __name__ == "__main__":
    main()
