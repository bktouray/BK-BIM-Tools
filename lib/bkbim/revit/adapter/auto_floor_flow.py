# -*- coding: utf-8 -*-
"""Runs the AutoFloor flow: pick CAD import/layer (unchanged, lightweight)
-> ONE themed options window (floor type, level, boundary mode, mm-only
offset) -> a single Transaction that creates the floors.

Redesigned 2026-07-15 (CAD to Revit panel redesign) from AutoFloor.pushbutton's
old chain of forms.SelectFromList/forms.CommandSwitchWindow/forms.ask_for_string
popups (including a confusing "pick the unit, THEN type the value" pair for
the height offset - now mm-only, matching every other numeric field in the
suite). automation/floors.py stays exactly as the execution engine - only
the UI layer changed.
"""

from pyrevit import DB, forms, script

from bkbim.automation import cadreader
from bkbim.automation.common import to_feet
from bkbim.automation.failures import swallow_warnings
from bkbim.automation.floors import create_floors
from bkbim.core.tool_memory import recall, remember
from bkbim.revit.adapter.cad_prescan_prompt import list_levels, pick_cad_import, pick_cad_layer
from bkbim.revit.adapter.element_naming import type_name
from bkbim.ui.views.floor_options import show_floor_options


def _list_floor_types(doc):
    cat_id = DB.ElementId(DB.BuiltInCategory.OST_Floors)
    types = [ft for ft in DB.FilteredElementCollector(doc).OfClass(DB.FloorType).ToElements()
            if ft.Category and ft.Category.Id == cat_id]
    return sorted(types, key=lambda ft: type_name(ft).lower())


def run_auto_floor_flow(doc, title):
    if doc is None:
        forms.alert(u"No active Revit document.", title=title)
        return

    logger = script.get_logger()
    output = script.get_output()

    inst = pick_cad_import(doc, title)
    if inst is None:
        return
    layer = pick_cad_layer(doc, inst, title, u"slab")
    if layer is None:
        return

    curves = cadreader.curves_on_layer(doc, inst, layer)
    if not curves:
        forms.alert(u"No curves on layer '{0}'.".format(layer), title=title)
        return

    floor_types = _list_floor_types(doc)
    if not floor_types:
        forms.alert(u"No floor types found in the model.", title=title)
        return
    levels = list_levels(doc)
    if not levels:
        forms.alert(u"No levels in the model.", title=title)
        return

    default_floor_type_name = recall(u"cad_to_revit.floor.floor_type_name", doc=doc)
    default_level_name = recall(u"cad_to_revit.floor.level_name", doc=doc)
    default_subtract_walls = recall(u"cad_to_revit.floor.boundary_mode", default=False, doc=doc)
    default_offset_mm = recall(u"cad_to_revit.floor.offset_mm", default=0.0, doc=doc)

    options = show_floor_options(
        floor_types, levels, type_name,
        default_floor_type_name=default_floor_type_name, default_level_name=default_level_name,
        default_subtract_walls=default_subtract_walls, default_offset_mm=default_offset_mm)
    if options is None:
        return  # user cancelled

    remember(u"cad_to_revit.floor.floor_type_name", type_name(options.floor_type), doc=doc)
    remember(u"cad_to_revit.floor.level_name", type_name(options.level), doc=doc)
    remember(u"cad_to_revit.floor.boundary_mode", options.subtract_walls, doc=doc)
    remember(u"cad_to_revit.floor.offset_mm", options.offset_mm, doc=doc)

    offset_ft = to_feet(options.offset_mm, "mm")

    res = None
    t = DB.Transaction(doc, u"Generate Floors")
    t.Start()
    swallow_warnings(t)
    try:
        res = create_floors(doc, curves, options.floor_type.Id, options.level.Id, offset_ft,
                            subtract_walls=options.subtract_walls)
        if res.placed == 0:
            t.RollBack()
        else:
            t.Commit()
    except Exception as e:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        logger.error(u"Floor generation failed: {0}".format(str(e)))
        forms.alert(u"Floor generation failed:\n{0}".format(str(e)), title=title)
        return

    if res.placed == 0:
        if res.skipped and not res.errors:
            forms.alert(u"All {0} floor(s) already exist - nothing new to "
                       u"add.".format(res.skipped), title=title)
            return
        msg = u"No floors were created."
        if res.errors:
            msg += u"\n\n" + u"\n".join(res.errors[:5])
        forms.alert(msg, title=title)
        return

    extra = u""
    if options.subtract_walls:
        extra = u"\nCut {0} opening(s) around walls.".format(res.openings)
    if res.skipped:
        extra += u"\n{0} already existed (skipped).".format(res.skipped)
    forms.alert(
        u"Floor Generation Complete.\n\n"
        u"Successfully created {0} Floor(s).{1}".format(res.placed, extra),
        title=title)
    if res.errors:
        output.print_md(u"**Notes:** " + u"; ".join(res.errors[:5]))
