# -*- coding: utf-8 -*-
__title__ = u"AutoFloor"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Create native Revit floors from closed slab outlines on a CAD
layer. Pick the layer, floor type and level; nested loops become openings.
"""

from pyrevit import revit, DB, forms, script

# Dev reload: always pick up the latest bkbim.automation lib code on each click.
import sys as _sys
for _m in [_n for _n in list(_sys.modules) if _n.startswith("bkbim.automation")]:
    del _sys.modules[_m]

from bkbim.automation import cadreader
from bkbim.automation.common import to_feet
from bkbim.automation.failures import swallow_warnings
from bkbim.automation.floors import create_floors

logger = script.get_logger()
output = script.get_output()
doc = revit.doc


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
        low = n.lower()
        if "slab" in low or "floor" in low:
            default = labels[i]
            break
    pick = forms.SelectFromList.show(
        labels, title="AutoFloor - pick the SLAB / FLOOR layer",
        default=default)
    if not pick:
        return None
    return layers[labels.index(pick)][0]


def _pick_floor_type():
    cat_id = DB.ElementId(DB.BuiltInCategory.OST_Floors)
    fts = [ft for ft in DB.FilteredElementCollector(doc).OfClass(DB.FloorType)
           .ToElements() if ft.Category and ft.Category.Id == cat_id]
    if not fts:
        forms.alert("No floor types found in the model.",
                    title=__title__)
        return None
    by_name = {}
    for ft in fts:
        by_name[_name(ft)] = ft
    pick = forms.SelectFromList.show(sorted(by_name.keys()),
                                     title="Select floor type")
    if not pick:
        return None
    return by_name[pick]


def _pick_level():
    levels = DB.FilteredElementCollector(doc).OfClass(DB.Level).ToElements()
    by_name = {}
    for lv in levels:
        by_name[_name(lv)] = lv
    names = sorted(by_name.keys(), key=lambda nm: by_name[nm].Elevation)
    if not names:
        forms.alert("No levels in the model.", title=__title__)
        return None
    pick = forms.SelectFromList.show(names, title="Select level",
                                     default=names[0])
    return by_name.get(pick)


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
    floor_type = _pick_floor_type()
    if floor_type is None:
        return
    level = _pick_level()
    if level is None:
        return

    # Boundary mode.
    mode = forms.CommandSwitchWindow.show(
        ["Total CAD boundary", "Draw around walls (core face)"],
        message="Floor boundary:")
    if not mode:
        return
    subtract_walls = (mode == "Draw around walls (core face)")

    # Height offset from level (optional).
    unit = forms.CommandSwitchWindow.show(
        ["mm", "in", "ft", "m"], message="Height-offset unit:") or "mm"
    raw = forms.ask_for_string(
        default="0",
        prompt="Height offset from level ({0}, 0 for none):".format(unit),
        title=__title__)
    if raw is None:
        return
    try:
        offset_ft = to_feet(float(raw), unit)
    except (TypeError, ValueError):
        offset_ft = 0.0

    curves = cadreader.curves_on_layer(doc, inst, layer)
    if not curves:
        forms.alert("No curves on layer '{0}'.".format(layer),
                    title=__title__)
        return

    res = None
    t = DB.Transaction(doc, "Generate Floors")
    t.Start()
    swallow_warnings(t)
    try:
        res = create_floors(doc, curves, floor_type.Id, level.Id, offset_ft,
                            subtract_walls=subtract_walls)
        if res.placed == 0:
            t.RollBack()
        else:
            t.Commit()
    except Exception as e:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        logger.error("Floor generation failed: {0}".format(str(e)))
        forms.alert("Floor generation failed:\n{0}".format(str(e)),
                    title=__title__)
        return

    if res.placed == 0:
        if res.skipped and not res.errors:
            forms.alert("All {0} floor(s) already exist - nothing new to "
                        "add.".format(res.skipped), title=__title__)
            return
        msg = "No floors were created."
        if res.errors:
            msg += "\n\n" + "\n".join(res.errors[:5])
        forms.alert(msg, title=__title__)
        return

    extra = ""
    if subtract_walls:
        extra = "\nCut {0} opening(s) around walls.".format(res.openings)
    if res.skipped:
        extra += "\n{0} already existed (skipped).".format(res.skipped)
    forms.alert(
        "Floor Generation Complete.\n\n"
        "Successfully created {0} Floor(s).{1}".format(res.placed, extra),
        title=__title__)
    if res.errors:
        output.print_md("**Notes:** " + "; ".join(res.errors[:5]))


if __name__ == "__main__":
    main()
