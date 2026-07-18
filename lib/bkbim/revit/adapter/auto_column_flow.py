# -*- coding: utf-8 -*-
"""Runs the AutoColumn flow: pick CAD import/layer/category (unchanged,
lightweight, sequential forms pickers - each choice changes what the scan
even looks for) -> scan the CAD layer for rectangular columns -> ONE themed
options window (levels, base family, material, per-size-group type mapping)
-> a single Transaction that places the columns.

Redesigned 2026-07-15 (CAD to Revit panel redesign) from AutoColumn.pushbutton's
old chain of forms.SelectFromList/forms.alert popups. automation/columns.py
stays exactly as the execution engine (ADR-0001's pure-command-layer split
is intentionally NOT being done for the CAD-to-Revit tools) - only the UI
layer changed.
"""

from pyrevit import DB, script

from bkbim.automation import cadreader
from bkbim.automation.columns import extract_rectangles, get_or_create_sized_type, group_by_size, place_columns
from bkbim.automation.failures import swallow_warnings
from bkbim.automation.familyutils import collect_symbols, pick_family_symbol
from bkbim.core.tool_memory import recall, remember
from bkbim.revit.adapter.cad_prescan_prompt import list_levels, list_materials, pick_cad_import, pick_cad_layer
from bkbim.revit.adapter.element_naming import type_name
from bkbim.ui.views.category_picker import show_category_picker
from bkbim.ui.views.column_options import show_column_options
from bkbim.ui.views.result_dialog import show_result

_SNAP = 5.0  # mm rounding for section grouping


def _make_base_family_picker(doc, bic, title):
    def _pick():
        symbol = pick_family_symbol(doc, [bic], u"{0}: base column family (used for auto-sizing)".format(title))
        if symbol is None:
            return None, None
        return symbol, u"{0} : {1}".format(type_name(symbol.Family), type_name(symbol))
    return _pick


def run_auto_column_flow(doc, title):
    if doc is None:
        show_result(title, u"No active Revit document.")
        return

    logger = script.get_logger()
    output = script.get_output()

    inst = pick_cad_import(doc, title)
    if inst is None:
        return
    layer = pick_cad_layer(doc, inst, title, u"column")
    if layer is None:
        return

    category = show_category_picker(
        title, u"Column category:", [u"Structural", u"Architectural"])
    if not category:
        return
    structural = (category == u"Structural")
    bic = DB.BuiltInCategory.OST_StructuralColumns if structural else DB.BuiltInCategory.OST_Columns

    curves = cadreader.curves_on_layer(doc, inst, layer)
    rects = extract_rectangles(curves)
    if not rects:
        show_result(
            title,
            u"No closed rectangular columns found on layer '{0}'.\n\n"
            u"Columns must be drawn as closed rectangles.".format(layer))
        return
    groups = group_by_size(rects, snap=_SNAP)

    levels = list_levels(doc)
    if not levels:
        show_result(title, u"No levels in the model.")
        return
    materials = list_materials(doc)
    existing_types_by_label = collect_symbols(doc, [bic])

    default_start_level_name = recall(u"cad_to_revit.column.start_level_name", doc=doc)
    default_stop_level_name = recall(u"cad_to_revit.column.stop_level_name", doc=doc)
    default_material_name = recall(u"cad_to_revit.column.material", doc=doc)

    options = show_column_options(
        groups, levels, materials, existing_types_by_label, type_name,
        _make_base_family_picker(doc, bic, title),
        default_start_level_name=default_start_level_name,
        default_stop_level_name=default_stop_level_name,
        default_material_name=default_material_name)
    if options is None:
        return  # user cancelled

    remember(u"cad_to_revit.column.start_level_name", type_name(options.base_level), doc=doc)
    remember(u"cad_to_revit.column.stop_level_name", type_name(options.top_level), doc=doc)
    if options.material_id is not None:
        material = doc.GetElement(options.material_id)
        remember(u"cad_to_revit.column.material", type_name(material), doc=doc)

    t = DB.Transaction(doc, u"Generate Columns")
    t.Start()
    swallow_warnings(t)
    try:
        rects_by_type = []
        cache = {}
        for group_key, rects_in_group in groups:
            kind, value, _extra = options.group_selections[group_key]
            if kind == u"auto":
                sym = get_or_create_sized_type(
                    doc, options.base_symbol, rects_in_group[0].short_ft, rects_in_group[0].long_ft, _SNAP, cache)
            else:
                sym = value
            rects_by_type.append((sym, rects_in_group))

        res = place_columns(doc, rects_by_type, options.base_level, options.top_level,
                            structural=structural, material_id=options.material_id)
        if res.placed == 0:
            t.RollBack()
        else:
            t.Commit()
    except Exception as e:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        logger.error(u"Column generation failed: {0}".format(str(e)))
        show_result(title, u"Column generation failed:\n{0}".format(str(e)))
        return

    if res.placed == 0:
        if res.skipped and not res.errors:
            show_result(
                title,
                u"All {0} column(s) already exist - nothing new to add.".format(
                    res.skipped))
            return
        msg = u"No columns were placed."
        if res.errors:
            msg += u"\n\n" + u"\n".join(res.errors[:5])
        show_result(title, msg)
        return

    extra = u"\n{0} already existed (skipped).".format(res.skipped) if res.skipped else u""
    show_result(
        title,
        u"Column Generation Complete.\n\n"
        u"Successfully placed {0} Columns.{1}".format(res.placed, extra))
    if res.errors:
        output.print_md(u"**Notes:** " + u"; ".join(res.errors[:5]))
