# -*- coding: utf-8 -*-
"""Runs the AutoGrid flow: pick CAD import/layer (unchanged, lightweight)
-> ONE themed options window (auto-extend + distance) -> a single
Transaction that generates the grids.

Redesigned 2026-07-15 (CAD to Revit panel redesign) from AutoGrid.pushbutton's
old "extend? -> unit -> value" popup chain. automation/grids.py stays
exactly as the execution engine - only the UI layer changed.
"""

from pyrevit import DB, forms, script

from bkbim.automation import cadreader
from bkbim.automation.common import to_feet
from bkbim.automation.grids import generate_grids
from bkbim.core.tool_memory import recall, remember
from bkbim.revit.adapter.cad_prescan_prompt import pick_cad_import, pick_cad_layer
from bkbim.ui.views.grid_options import show_grid_options


def run_auto_grid_flow(doc, title):
    if doc is None:
        forms.alert(u"No active Revit document.", title=title)
        return

    logger = script.get_logger()
    output = script.get_output()

    inst = pick_cad_import(doc, title)
    if inst is None:
        return
    layer = pick_cad_layer(doc, inst, title, u"grid")
    if layer is None:
        return

    curves = cadreader.curves_on_layer(doc, inst, layer)
    if not curves:
        forms.alert(u"No curves on layer '{0}'.".format(layer), title=title)
        return

    default_auto_extend = recall(u"cad_to_revit.grid.auto_extend", default=True, doc=doc)
    default_extend_mm = recall(u"cad_to_revit.grid.extend_mm", default=1500.0, doc=doc)

    options = show_grid_options(default_auto_extend=default_auto_extend, default_extend_mm=default_extend_mm)
    if options is None:
        return  # user cancelled

    remember(u"cad_to_revit.grid.auto_extend", options.auto_extend, doc=doc)
    remember(u"cad_to_revit.grid.extend_mm", options.extend_mm, doc=doc)

    extend_ft = to_feet(options.extend_mm, "mm") if options.auto_extend else 0.0

    res = None
    t = DB.Transaction(doc, u"Generate Grids")
    t.Start()
    try:
        res = generate_grids(doc, curves, extend_ft=extend_ft, auto_number=True)
        if res.created == 0:
            t.RollBack()
        else:
            t.Commit()
    except Exception as e:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        logger.error(u"Grid generation failed: {0}".format(str(e)))
        forms.alert(u"Grid generation failed:\n{0}".format(str(e)), title=title)
        return

    if res.created == 0:
        if res.exists and not res.errors:
            forms.alert(u"All {0} grid line(s) already exist - nothing new "
                       u"to add.".format(res.exists), title=title)
            return
        msg = u"No grids were created."
        if res.errors:
            msg += u"\n\n" + u"\n".join(res.errors[:5])
        forms.alert(msg, title=title)
        return

    extra = u"\n{0} already existed (skipped).".format(res.exists) if res.exists else u""
    forms.alert(
        u"Grid Generation Complete.\n\n"
        u"Successfully placed {0} Grid Lines.{1}".format(res.created, extra),
        title=title)
    output.print_md(u"**AutoGrid** - created {0} grids: {1}".format(
        res.created, u", ".join(res.names)))
