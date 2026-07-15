# -*- coding: utf-8 -*-
"""Runs the AutoWall flow: pick CAD import/layer/drawing-mode (unchanged,
lightweight, sequential - each choice changes what the scan even looks
for) -> scan -> ONE themed options window (levels, structural, per-mode
content) -> a single Transaction that places the walls.

Redesigned 2026-07-15 (CAD to Revit panel redesign) from AutoWall.pushbutton's
old chain of forms popups. automation/walls.py stays exactly as the
execution engine - only the UI layer changed. `structural` is newly exposed
as a checkbox (was hardcoded structural=False).
"""

from pyrevit import DB, forms, script

from bkbim.automation import cadreader
from bkbim.automation.common import to_feet
from bkbim.automation.failures import swallow_warnings
from bkbim.automation.walls import (
    basic_wall_types, extract_centerlines, extract_wall_runs, get_or_create_wall_type,
    group_by_thickness, place_walls,
)
from bkbim.core.tool_memory import recall, remember
from bkbim.revit.adapter.cad_prescan_prompt import list_levels, list_materials, pick_cad_import, pick_cad_layer
from bkbim.revit.adapter.element_naming import type_name
from bkbim.ui.views.wall_options import MODE_CENTRELINE, MODE_PARALLEL, show_wall_options

_SNAP = 5.0


def _make_base_wall_type_picker(type_names, types_by_name, title):
    def _pick():
        choice = forms.SelectFromList.show(
            type_names, title=u"{0}: base type to duplicate for auto-generated walls".format(title))
        if not choice:
            return None, None
        return types_by_name[choice], choice
    return _pick


def run_auto_wall_flow(doc, title):
    if doc is None:
        forms.alert(u"No active Revit document.", title=title)
        return

    logger = script.get_logger()
    output = script.get_output()

    inst = pick_cad_import(doc, title)
    if inst is None:
        return
    layer = pick_cad_layer(doc, inst, title, u"wall")
    if layer is None:
        return

    types_by_name = basic_wall_types(doc)
    if not types_by_name:
        forms.alert(u"No basic wall types in the model.", title=title)
        return
    type_names = sorted(types_by_name.keys())
    curves = cadreader.curves_on_layer(doc, inst, layer)

    mode_choice = forms.CommandSwitchWindow.show(
        [u"Two parallel lines (double-line)", u"Centreline"],
        message=u"How are the walls drawn in the CAD?")
    if not mode_choice:
        return
    mode = MODE_PARALLEL if mode_choice.startswith(u"Two parallel") else MODE_CENTRELINE

    groups = []
    if mode == MODE_PARALLEL:
        raw = forms.ask_for_string(
            default=u"450", prompt=u"Maximum wall thickness to detect (mm):", title=title)
        if raw is None:
            return
        try:
            max_thk_ft = to_feet(float(raw), u"mm")
        except (TypeError, ValueError):
            max_thk_ft = to_feet(450.0, u"mm")

        runs = extract_wall_runs(curves, max_thickness_ft=max_thk_ft)
        if not runs:
            forms.alert(u"No double-line walls found on layer '{0}'.\n\n"
                       u"Walls must be drawn as two parallel lines.".format(layer), title=title)
            return
        groups = group_by_thickness(runs, snap=_SNAP)
    else:
        runs = extract_centerlines(curves)
        if not runs:
            forms.alert(u"No lines found on layer '{0}'.".format(layer), title=title)
            return

    levels = list_levels(doc)
    if not levels:
        forms.alert(u"No levels in the model.", title=title)
        return
    materials = list_materials(doc)

    default_start_level_name = recall(u"cad_to_revit.wall.start_level_name", doc=doc)
    default_stop_level_name = recall(u"cad_to_revit.wall.stop_level_name", doc=doc)
    default_structural = recall(u"cad_to_revit.wall.structural", default=False, doc=doc)
    default_location_line = recall(u"cad_to_revit.wall.location_line", default=u"finish", doc=doc)
    default_material_name = recall(u"cad_to_revit.wall.material", doc=doc)
    default_wall_type_name = recall(u"cad_to_revit.wall.base_wall_type_name", doc=doc)

    options = show_wall_options(
        mode, groups, type_names, [types_by_name[n] for n in type_names], levels, materials, type_name,
        _make_base_wall_type_picker(type_names, types_by_name, title),
        default_start_level_name=default_start_level_name, default_stop_level_name=default_stop_level_name,
        default_structural=default_structural, default_location_line=default_location_line,
        default_material_name=default_material_name, default_wall_type_name=default_wall_type_name)
    if options is None:
        return  # user cancelled

    remember(u"cad_to_revit.wall.start_level_name", type_name(options.base_level), doc=doc)
    remember(u"cad_to_revit.wall.stop_level_name", type_name(options.top_level), doc=doc)
    remember(u"cad_to_revit.wall.structural", options.structural, doc=doc)
    if options.mode == MODE_PARALLEL:
        remember(u"cad_to_revit.wall.location_line", options.location_line, doc=doc)
        if options.material_id is not None:
            remember(u"cad_to_revit.wall.material", type_name(doc.GetElement(options.material_id)), doc=doc)
        if options.base_wall_type is not None:
            remember(u"cad_to_revit.wall.base_wall_type_name", type_name(options.base_wall_type), doc=doc)
    else:
        if options.wall_type is not None:
            remember(u"cad_to_revit.wall.base_wall_type_name", type_name(options.wall_type), doc=doc)

    t = DB.Transaction(doc, u"Generate Walls")
    t.Start()
    swallow_warnings(t)
    try:
        runs_by_type = []
        if options.mode == MODE_PARALLEL:
            location_line = (DB.WallLocationLine.WallCenterline if options.location_line == u"finish"
                            else DB.WallLocationLine.CoreCenterline)
            cache = {}
            for group_key, runs_in_group in groups:
                kind, value, _extra = options.group_selections[group_key]
                if kind == u"auto":
                    wt = get_or_create_wall_type(
                        doc, options.base_wall_type, runs_in_group[0].thickness_ft,
                        options.material_id, _SNAP, cache)
                else:
                    wt = value
                runs_by_type.append((wt, runs_in_group))
        else:
            location_line = DB.WallLocationLine.WallCenterline
            runs_by_type = [(options.wall_type, runs)]

        res = place_walls(doc, runs_by_type, options.base_level, options.top_level,
                          structural=options.structural, location_line=location_line)
        if res.placed == 0:
            t.RollBack()
        else:
            t.Commit()
    except Exception as e:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        logger.error(u"Wall generation failed: {0}".format(str(e)))
        forms.alert(u"Wall generation failed:\n{0}".format(str(e)), title=title)
        return

    if res.placed == 0:
        if res.skipped and not res.errors:
            forms.alert(u"All {0} wall(s) already exist - nothing new to "
                       u"add.".format(res.skipped), title=title)
            return
        msg = u"No walls were created."
        if res.errors:
            msg += u"\n\n" + u"\n".join(res.errors[:5])
        forms.alert(msg, title=title)
        return

    extra = u"\n{0} already existed (skipped).".format(res.skipped) if res.skipped else u""
    forms.alert(
        u"Wall Generation Complete.\n\n"
        u"Successfully created {0} Walls.{1}".format(res.placed, extra),
        title=title)
    if res.errors:
        output.print_md(u"**Notes:** " + u"; ".join(res.errors[:5]))
