# -*- coding: utf-8 -*-
"""Shared UI flow for the AutoDoor / AutoWindow tools.

Both tools are identical apart from the Revit category and a couple of
labels, so the whole interaction lives here and each pushbutton just calls
run() with its BuiltInCategory.

IronPython 2.7.
"""

from pyrevit import DB, forms, script

from bkbim.automation import cadreader, familyutils
from bkbim.automation.common import to_feet
from bkbim.automation.failures import swallow_warnings
from bkbim.automation.openings import (
    extract_openings, extract_openings_from_markers, group_by_width,
    get_or_create_sized_symbol, place_openings,
)

_SNAP = 5.0


def _name(el):
    try:
        return el.Name
    except Exception:
        return DB.Element.Name.__get__(el)


def _pick_import(doc, title):
    imports = cadreader.get_import_instances(doc)
    if not imports:
        forms.alert("No imported CAD (DWG) found in this model.", title=title)
        return None
    if len(imports) == 1:
        return imports[0]
    opts = {}
    for inst in imports:
        te = doc.GetElement(inst.GetTypeId())
        opts[_name(te) if te else str(inst.Id)] = inst
    pick = forms.SelectFromList.show(sorted(opts.keys()),
                                     title="Select CAD import")
    return opts.get(pick)


def _pick_layer(doc, inst, title, hint):
    layers = [(n, c) for (n, c) in cadreader.list_layers(doc, inst) if c > 0]
    if not layers:
        forms.alert("No line geometry in the CAD import.", title=title)
        return None
    labels = ["{0}   ({1} segments)".format(n, c) for (n, c) in layers]
    default = labels[0]
    for i, (n, _c) in enumerate(layers):
        if hint in n.lower():
            default = labels[i]
            break
    pick = forms.SelectFromList.show(
        labels, title="{0} - pick the {1} layer".format(title, hint.upper()),
        default=default)
    if not pick:
        return None
    return layers[labels.index(pick)][0]


def _pick_level(doc, title):
    levels = DB.FilteredElementCollector(doc).OfClass(DB.Level).ToElements()
    by_name = {}
    for lv in levels:
        by_name[_name(lv)] = lv
    names = sorted(by_name.keys(), key=lambda nm: by_name[nm].Elevation)
    if not names:
        forms.alert("No levels in the model.", title=title)
        return None
    pick = forms.SelectFromList.show(names, title="Host level", default=names[0])
    return by_name.get(pick)


def _pick_for_width(doc, bic, width_mm, title):
    """Per-width family choice: auto-generate, load .rfa, or pick existing."""
    auto = u"⚙ Auto-generate {0}mm".format(width_mm)
    while True:
        symbols = familyutils.collect_symbols(doc, [bic])
        labels = sorted(symbols.keys())
        choice = forms.SelectFromList.show(
            [auto, familyutils._LOAD_LABEL] + labels,
            title="{0}: family type for {1}mm openings".format(title, width_mm),
            default=auto)
        if not choice:
            return ("cancel", None)
        if choice == familyutils._LOAD_LABEL:
            familyutils.load_family_from_file(doc)
            continue
        if choice == auto:
            return ("auto", None)
        return ("type", symbols[choice])


def run(doc, bic, kind, default_width_mm, default_lintel_mm,
        default_height_mm):
    """kind: 'Door' or 'Window'. bic: DB.BuiltInCategory."""
    title = "Auto{0}".format(kind)
    if doc is None:
        forms.alert("No active Revit document.", title=title)
        return

    inst = _pick_import(doc, title)
    if inst is None:
        return

    # Detection mode (centre-line marker is the default).
    mode = forms.CommandSwitchWindow.show(
        ["Centre-line marker (one line per opening)",
         "Parallel jamb lines (distance = width)"],
        message="How are the openings drawn in the CAD?")
    if not mode:
        return
    marker_mode = mode.startswith("Centre-line")

    layer = _pick_layer(doc, inst, title, kind.lower())
    if layer is None:
        return
    curves = cadreader.curves_on_layer(doc, inst, layer)

    if marker_mode:
        # Each marker line IS one opening - great for sliding / close openings.
        ops = extract_openings_from_markers(curves)
    else:
        raw = forms.ask_for_string(
            default=str(int(default_width_mm * 1.6)),
            prompt="Maximum opening width to detect (mm):", title=title)
        if raw is None:
            return
        try:
            max_w_ft = to_feet(float(raw), "mm")
        except (TypeError, ValueError):
            max_w_ft = to_feet(default_width_mm * 1.6, "mm")
        ops = extract_openings(curves, max_width_ft=max_w_ft)
    if not ops:
        forms.alert("No openings found on layer '{0}'.\n\n"
                    "Openings must be drawn as two parallel lines.".format(layer),
                    title=title)
        return
    groups = group_by_width(ops, snap=_SNAP)
    summary = "\n".join("   {0} mm  ->  {1}".format(w, len(o))
                        for w, o in groups)
    if not forms.alert(
            "Detected {0} {1}(s) in {2} width(s):\n\n{3}\n\n"
            "Generate?".format(len(ops), kind.lower(), len(groups), summary),
            title=title, yes=True, no=True):
        return

    level = _pick_level(doc, title)
    if level is None:
        return

    raw = forms.ask_for_string(
        default=str(int(default_lintel_mm)),
        prompt="Lintel / head height above level ({0}) (mm):".format(_name(level)),
        title=title)
    if raw is None:
        return
    try:
        lintel_ft = to_feet(float(raw), "mm")
    except (TypeError, ValueError):
        lintel_ft = to_feet(default_lintel_mm, "mm")

    # Per-width family mapping. Each width can use its OWN base family, since
    # different widths often mean different families (e.g. sliding vs single).
    # Value is ("auto", base_symbol, height_ft) or ("type", symbol).
    mapping = {}
    for w, _o in groups:
        sel_kind, sym = _pick_for_width(doc, bic, w, title)
        if sel_kind == "cancel":
            return
        if sel_kind == "auto":
            # Base family to size from FOR THIS WIDTH.
            base = familyutils.pick_family_symbol(
                doc, [bic],
                "{0}: base family for {1}mm openings (size from)".format(
                    title, w))
            if base is None:
                return
            # Height typed per width (depends on the opening width).
            raw = forms.ask_for_string(
                default=str(int(default_height_mm)),
                prompt="Opening HEIGHT for {0}mm-wide {1}s (mm):".format(
                    w, kind.lower()),
                title=title)
            if raw is None:
                return
            try:
                h_ft = to_feet(float(raw), "mm")
            except (TypeError, ValueError):
                h_ft = to_feet(default_height_mm, "mm")
            mapping[w] = ("auto", base, h_ft)
        else:
            mapping[w] = ("type", sym)

    t = DB.Transaction(doc, "Generate {0}s".format(kind))
    t.Start()
    swallow_warnings(t)
    try:
        ops_by_symbol = []
        cache = {}
        for w, o in groups:
            entry = mapping[w]
            if entry[0] == "auto":
                _kind, base, h_ft = entry
                sym = get_or_create_sized_symbol(
                    doc, base, o[0].width_ft, h_ft, _SNAP, cache)
            else:
                sym = entry[1]
            ops_by_symbol.append((sym, o))
        res = place_openings(doc, ops_by_symbol, level, lintel_ft,
                             skip_existing=True, bic=bic)
        if res.placed == 0:
            t.RollBack()
        else:
            t.Commit()
    except Exception as e:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        script.get_logger().error("{0} failed: {1}".format(title, str(e)))
        forms.alert("{0} failed:\n{1}".format(title, str(e)), title=title)
        return

    if res.placed == 0:
        if res.skipped and not res.no_host and not res.errors:
            forms.alert("All {0} {1}(s) already exist - nothing new to "
                        "add.".format(res.skipped, kind.lower()), title=title)
            return
        msg = "No {0}s were placed.".format(kind.lower())
        if res.no_host:
            msg += "\n\n{0} opening(s) had no host wall - run AutoWall " \
                   "first so there are walls to host into.".format(res.no_host)
        if res.errors:
            msg += "\n\n" + "\n".join(res.errors[:5])
        forms.alert(msg, title=title)
        return

    extra = ""
    if res.skipped:
        extra += "\n{0} already existed (skipped).".format(res.skipped)
    if res.no_host:
        extra += "\n{0} had no host wall (skipped).".format(res.no_host)
    forms.alert(
        "{0} Generation Complete.\n\n"
        "Successfully placed {1} {2}(s).{3}".format(
            kind, res.placed, kind.lower(), extra),
        title=title)
