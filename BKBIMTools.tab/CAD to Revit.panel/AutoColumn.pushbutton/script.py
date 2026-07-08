# -*- coding: utf-8 -*-
__title__ = u"AutoColumn"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Scans a CAD layer for rectangular columns and places native
Revit columns, grouped by section size. Can auto-generate a correctly sized
family type per section.
"""

from pyrevit import revit, DB, forms, script

# Dev reload: always pick up the latest bkbim.automation lib code on each click.
import sys as _sys
for _m in [_n for _n in list(_sys.modules) if _n.startswith("bkbim.automation")]:
    del _sys.modules[_m]

from bkbim.automation import cadreader
from bkbim.automation.failures import swallow_warnings
from bkbim.automation.familyutils import pick_family_symbol
from bkbim.automation.columns import (
    extract_rectangles, group_by_size, get_or_create_sized_type, place_columns,
)

logger = script.get_logger()
output = script.get_output()
doc = revit.doc

_SNAP = 5.0  # mm rounding for section grouping


def _name(el):
    try:
        return el.Name
    except Exception:
        return DB.Element.Name.__get__(el)


def _pick_import():
    imports = cadreader.get_import_instances(doc)
    if not imports:
        forms.alert("No imported CAD (DWG) found in this model.\n\n"
                    "Insert > Import CAD, then run this tool again.",
                    title=__title__)
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


def _pick_layer(inst):
    layers = [(n, c) for (n, c) in cadreader.list_layers(doc, inst) if c > 0]
    if not layers:
        forms.alert("No line geometry in the CAD import.",
                    title=__title__)
        return None
    labels = ["{0}   ({1} segments)".format(n, c) for (n, c) in layers]
    default = labels[0]
    for i, (n, _c) in enumerate(layers):
        if "column" in n.lower() or n.lower() in ("col", "c"):
            default = labels[i]
            break
    pick = forms.SelectFromList.show(
        labels, title="AutoColumn - pick the COLUMN layer",
        default=default)
    if not pick:
        return None
    return layers[labels.index(pick)][0]


def _pick_level(prompt, default_name=None):
    levels = (DB.FilteredElementCollector(doc).OfClass(DB.Level)
              .ToElements())
    by_name = {}
    for lv in levels:
        by_name[_name(lv)] = lv
    names = sorted(by_name.keys(), key=lambda nm: by_name[nm].Elevation)
    if not names:
        forms.alert("No levels in the model.", title=__title__)
        return None
    pick = forms.SelectFromList.show(
        names, title=prompt, default=default_name or names[0])
    return by_name.get(pick)


def _pick_material():
    """Pick a material to apply to all columns, or skip. Returns ElementId|None."""
    mats = DB.FilteredElementCollector(doc).OfClass(DB.Material).ToElements()
    by_name = {}
    for m in mats:
        by_name[_name(m)] = m
    skip = "<Leave family default>"
    names = [skip] + sorted(by_name.keys())
    pick = forms.SelectFromList.show(
        names, title="Select material for all columns", default=skip)
    if not pick or pick == skip:
        return None
    return by_name[pick].Id


def main():
    if doc is None:
        forms.alert("No active Revit document.", title=__title__)
        return

    inst = _pick_import()
    if inst is None:
        return
    layer = _pick_layer(inst)
    if layer is None:
        return

    # Category.
    cat = forms.CommandSwitchWindow.show(
        ["Structural", "Architectural"], message="Column category:")
    if not cat:
        return
    structural = (cat == "Structural")

    # SCAN.
    curves = cadreader.curves_on_layer(doc, inst, layer)
    rects = extract_rectangles(curves)
    if not rects:
        forms.alert("No closed rectangular columns found on layer '{0}'.\n\n"
                    "Columns must be drawn as closed rectangles.".format(layer),
                    title=__title__)
        return
    groups = group_by_size(rects, snap=_SNAP)
    summary = "\n".join("   {0} x {1} mm  ->  {2} columns".format(
        s, l, len(rs)) for (s, l), rs in groups)
    proceed = forms.alert(
        "Scan complete. Found {0} column locations in {1} size(s):\n\n{2}\n\n"
        "Generate columns?".format(len(rects), len(groups), summary),
        title=__title__, yes=True, no=True)
    if not proceed:
        return

    # Start / stop levels (always asked).
    base_level = _pick_level("Start Level (base)")
    if base_level is None:
        return
    top_level = _pick_level("Stop Level (top)")
    if top_level is None:
        return

    # Base family (with the option to load one from an .rfa on the spot).
    bic = (DB.BuiltInCategory.OST_StructuralColumns if structural
           else DB.BuiltInCategory.OST_Columns)
    base_symbol = pick_family_symbol(
        doc, [bic], "Base column family (used for auto-sizing)")
    if base_symbol is None:
        return
    base_label = u"{0} : {1}".format(_name(base_symbol.Family), _name(base_symbol))

    auto_size = forms.alert(
        "Auto-generate a family type sized to each CAD section?\n\n"
        "Yes  = one correctly sized type per size (recommended)\n"
        "No   = use '{0}' as-is for every column".format(base_label),
        title=__title__, yes=True, no=True)

    # Material for all columns (always asked).
    material_id = _pick_material()

    # Build symbol -> rects mapping.
    rects_by_type = []
    t = DB.Transaction(doc, "Generate Columns")
    t.Start()
    swallow_warnings(t)
    try:
        if auto_size:
            cache = {}
            for (s_mm, l_mm), rs in groups:
                sym = get_or_create_sized_type(
                    doc, base_symbol, rs[0].short_ft, rs[0].long_ft,
                    _SNAP, cache)
                rects_by_type.append((sym, rs))
        else:
            rects_by_type.append((base_symbol, rects))

        res = place_columns(doc, rects_by_type, base_level, top_level,
                            structural=structural, material_id=material_id)
        if res.placed == 0:
            t.RollBack()
        else:
            t.Commit()
    except Exception as e:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        logger.error("Column generation failed: {0}".format(str(e)))
        forms.alert("Column generation failed:\n{0}".format(str(e)),
                    title=__title__)
        return

    if res.placed == 0:
        if res.skipped and not res.errors:
            forms.alert("All {0} column(s) already exist - nothing new to "
                        "add.".format(res.skipped), title=__title__)
            return
        msg = "No columns were placed."
        if res.errors:
            msg += "\n\n" + "\n".join(res.errors[:5])
        forms.alert(msg, title=__title__)
        return

    extra = "\n{0} already existed (skipped).".format(res.skipped) if res.skipped else ""
    forms.alert(
        "Column Generation Complete.\n\n"
        "Successfully placed {0} Columns.{1}".format(res.placed, extra),
        title=__title__)
    if res.errors:
        output.print_md("**Notes:** " + "; ".join(res.errors[:5]))


if __name__ == "__main__":
    main()
