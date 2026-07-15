# -*- coding: utf-8 -*-
"""Runs the AutoDoor / AutoWindow flow: pick CAD import/detection-mode/layer
(unchanged, lightweight, sequential) -> scan -> ONE themed options window
(host level, lintel height, per-width family mapping) -> a single
Transaction that places the openings.

Redesigned 2026-07-15 (CAD to Revit panel redesign), replacing the old
automation/opening_tool.py (deleted - its forms-popup-chain UI is fully
superseded by this + opening_options.py). Both tools are identical apart
from the Revit category and a couple of labels, so the whole interaction
lives here and each pushbutton just calls run_opening_flow() with its
BuiltInCategory, same as opening_tool.run() worked before.
automation/openings.py stays exactly as the execution engine - only the UI
layer changed.
"""

from pyrevit import DB, forms, script

from bkbim.automation import cadreader
from bkbim.automation.common import to_feet
from bkbim.automation.failures import swallow_warnings
from bkbim.automation.familyutils import collect_symbols, pick_family_symbol
from bkbim.automation.openings import (
    extract_openings, extract_openings_from_markers, get_or_create_sized_symbol, group_by_width, place_openings,
)
from bkbim.core.tool_memory import recall, remember
from bkbim.revit.adapter.cad_prescan_prompt import list_levels, pick_cad_import, pick_cad_layer
from bkbim.revit.adapter.element_naming import type_name
from bkbim.ui.views.opening_options import show_opening_options

_SNAP = 5.0


def _make_base_family_picker(doc, bic, title):
    def _pick(width_mm):
        symbol = pick_family_symbol(
            doc, [bic], u"{0}: base family for {1}mm openings (size from)".format(title, width_mm))
        if symbol is None:
            return None, None
        return symbol, u"{0} : {1}".format(type_name(symbol.Family), type_name(symbol))
    return _pick


def run_opening_flow(doc, bic, kind, default_width_mm, default_lintel_mm, default_height_mm):
    """kind: 'Door' or 'Window'. bic: DB.BuiltInCategory."""
    title = u"Auto{0}".format(kind)
    if doc is None:
        forms.alert(u"No active Revit document.", title=title)
        return

    logger = script.get_logger()

    inst = pick_cad_import(doc, title)
    if inst is None:
        return

    mode = forms.CommandSwitchWindow.show(
        [u"Centre-line marker (one line per opening)", u"Parallel jamb lines (distance = width)"],
        message=u"How are the openings drawn in the CAD?")
    if not mode:
        return
    marker_mode = mode.startswith(u"Centre-line")

    layer = pick_cad_layer(doc, inst, title, kind.lower())
    if layer is None:
        return
    curves = cadreader.curves_on_layer(doc, inst, layer)

    if marker_mode:
        ops = extract_openings_from_markers(curves)
    else:
        raw = forms.ask_for_string(
            default=str(int(default_width_mm * 1.6)),
            prompt=u"Maximum opening width to detect (mm):", title=title)
        if raw is None:
            return
        try:
            max_w_ft = to_feet(float(raw), u"mm")
        except (TypeError, ValueError):
            max_w_ft = to_feet(default_width_mm * 1.6, u"mm")
        ops = extract_openings(curves, max_width_ft=max_w_ft)

    if not ops:
        forms.alert(u"No openings found on layer '{0}'.\n\n"
                   u"Openings must be drawn as two parallel lines.".format(layer), title=title)
        return
    groups = group_by_width(ops, snap=_SNAP)

    levels = list_levels(doc)
    if not levels:
        forms.alert(u"No levels in the model.", title=title)
        return
    existing_types_by_label = collect_symbols(doc, [bic])
    existing_labels = sorted(existing_types_by_label.keys())
    existing_types = [existing_types_by_label[lbl] for lbl in existing_labels]

    kind_key = kind.lower()
    default_level_name = recall(u"cad_to_revit.{0}.level_name".format(kind_key), doc=doc)
    default_lintel = recall(u"cad_to_revit.{0}.lintel_mm".format(kind_key), default=default_lintel_mm, doc=doc)

    options = show_opening_options(
        kind, groups, levels, existing_labels, existing_types, type_name,
        _make_base_family_picker(doc, bic, title),
        default_level_name=default_level_name, default_lintel_mm=default_lintel,
        default_height_mm=default_height_mm)
    if options is None:
        return  # user cancelled

    remember(u"cad_to_revit.{0}.level_name".format(kind_key), type_name(options.level), doc=doc)
    remember(u"cad_to_revit.{0}.lintel_mm".format(kind_key), options.lintel_mm, doc=doc)

    lintel_ft = to_feet(options.lintel_mm, u"mm")

    t = DB.Transaction(doc, u"Generate {0}s".format(kind))
    t.Start()
    swallow_warnings(t)
    try:
        ops_by_symbol = []
        cache = {}
        for width_mm, ops_in_group in groups:
            sel_kind, value, extra = options.group_selections[width_mm]
            if sel_kind == u"auto":
                height_mm = extra.get(u"height_mm") or default_height_mm
                sym = get_or_create_sized_symbol(
                    doc, value, ops_in_group[0].width_ft, to_feet(height_mm, u"mm"), _SNAP, cache)
            else:
                sym = value
            ops_by_symbol.append((sym, ops_in_group))
        res = place_openings(doc, ops_by_symbol, options.level, lintel_ft, skip_existing=True, bic=bic)
        if res.placed == 0:
            t.RollBack()
        else:
            t.Commit()
    except Exception as e:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        logger.error(u"{0} failed: {1}".format(title, str(e)))
        forms.alert(u"{0} failed:\n{1}".format(title, str(e)), title=title)
        return

    if res.placed == 0:
        if res.skipped and not res.no_host and not res.errors:
            forms.alert(u"All {0} {1}(s) already exist - nothing new to "
                       u"add.".format(res.skipped, kind.lower()), title=title)
            return
        msg = u"No {0}s were placed.".format(kind.lower())
        if res.no_host:
            msg += u"\n\n{0} opening(s) had no host wall - run AutoWall " \
                   u"first so there are walls to host into.".format(res.no_host)
        if res.errors:
            msg += u"\n\n" + u"\n".join(res.errors[:5])
        forms.alert(msg, title=title)
        return

    extra_msg = u""
    if res.skipped:
        extra_msg += u"\n{0} already existed (skipped).".format(res.skipped)
    if res.no_host:
        extra_msg += u"\n{0} had no host wall (skipped).".format(res.no_host)
    forms.alert(
        u"{0} Generation Complete.\n\n"
        u"Successfully placed {1} {2}(s).{3}".format(kind, res.placed, kind.lower(), extra_msg),
        title=title)
