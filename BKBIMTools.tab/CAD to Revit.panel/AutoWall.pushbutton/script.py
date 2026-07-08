# -*- coding: utf-8 -*-
__title__ = u"AutoWall"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Build native Revit walls from double-line walls on a CAD
layer. Detects each wall's thickness and can auto-generate a wall type per
thickness, bound between two levels.
"""

from pyrevit import revit, DB, forms, script

# Dev reload: always pick up the latest bkbim.automation lib code on each click.
import sys as _sys
for _m in [_n for _n in list(_sys.modules) if _n.startswith("bkbim.automation")]:
    del _sys.modules[_m]

from bkbim.automation import cadreader
from bkbim.automation.common import to_feet
from bkbim.automation.failures import swallow_warnings
from bkbim.automation.walls import (
    extract_wall_runs, extract_centerlines, group_by_thickness,
    basic_wall_types, get_or_create_wall_type, place_walls,
)

logger = script.get_logger()
output = script.get_output()
doc = revit.doc

_SNAP = 5.0


def _name(el):
    try:
        return el.Name
    except Exception:
        return DB.Element.Name.__get__(el)


def _pick_import():
    imports = cadreader.get_import_instances(doc)
    if not imports:
        forms.alert("No imported CAD (DWG) found in this model.",
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
        if "wall" in n.lower():
            default = labels[i]
            break
    pick = forms.SelectFromList.show(
        labels, title="AutoWall - pick the WALL layer",
        default=default)
    if not pick:
        return None
    return layers[labels.index(pick)][0]


def _pick_level(prompt):
    levels = DB.FilteredElementCollector(doc).OfClass(DB.Level).ToElements()
    by_name = {}
    for lv in levels:
        by_name[_name(lv)] = lv
    names = sorted(by_name.keys(), key=lambda nm: by_name[nm].Elevation)
    if not names:
        forms.alert("No levels in the model.", title=__title__)
        return None
    pick = forms.SelectFromList.show(names, title=prompt, default=names[0])
    return by_name.get(pick)


def _pick_material():
    mats = DB.FilteredElementCollector(doc).OfClass(DB.Material).ToElements()
    by_name = {}
    for m in mats:
        by_name[_name(m)] = m
    skip = "<Leave family default>"
    pick = forms.SelectFromList.show([skip] + sorted(by_name.keys()),
                                     title="Material for all walls",
                                     default=skip)
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

    types = basic_wall_types(doc)
    if not types:
        forms.alert("No basic wall types in the model.",
                    title=__title__)
        return
    type_names = sorted(types.keys())
    curves = cadreader.curves_on_layer(doc, inst, layer)

    # How are walls drawn?
    mode = forms.CommandSwitchWindow.show(
        ["Two parallel lines (double-line)", "Centreline"],
        message="How are the walls drawn in the CAD?")
    if not mode:
        return
    parallel = mode.startswith("Two parallel")

    # Start / stop levels (both modes).
    base_level = _pick_level("Start Level (base)")
    if base_level is None:
        return
    top_level = _pick_level("Stop Level (top)")
    if top_level is None:
        return

    runs_by_type = []
    groups = None
    base_type = None
    material_id = None
    location_line = None

    if not parallel:
        # ---- CENTRELINE MODE: each CAD line is a wall centre line ----
        runs = extract_centerlines(curves)
        if not runs:
            forms.alert("No lines found on layer '{0}'.".format(layer),
                        title=__title__)
            return
        pick = forms.SelectFromList.show(
            type_names, title="Wall type for all centre lines")
        if not pick:
            return
        runs_by_type = [(types[pick], runs)]
        location_line = DB.WallLocationLine.WallCenterline
    else:
        # ---- TWO PARALLEL LINES MODE ----
        raw = forms.ask_for_string(
            default="450", prompt="Maximum wall thickness to detect (mm):",
            title=__title__)
        if raw is None:
            return
        try:
            max_thk_ft = to_feet(float(raw), "mm")
        except (TypeError, ValueError):
            max_thk_ft = to_feet(450.0, "mm")

        runs = extract_wall_runs(curves, max_thickness_ft=max_thk_ft)
        if not runs:
            forms.alert("No double-line walls found on layer '{0}'.\n\n"
                        "Walls must be drawn as two parallel lines.".format(layer),
                        title=__title__)
            return
        groups = group_by_thickness(runs, snap=_SNAP)
        summary = "\n".join("   {0} mm  ->  {1} walls".format(thk, len(rs))
                            for thk, rs in groups)
        if not forms.alert(
                "Detected {0} walls in {1} thickness(es):\n\n{2}\n\n"
                "Generate walls?".format(len(runs), len(groups), summary),
                title=__title__, yes=True, no=True):
            return

        # Do the parallel lines mark finish faces or core faces?
        face = forms.CommandSwitchWindow.show(
            ["Finish faces", "Core faces"],
            message="The two parallel lines represent the wall's:")
        if not face:
            return
        location_line = (DB.WallLocationLine.WallCenterline if face == "Finish faces"
                         else DB.WallLocationLine.CoreCenterline)

        # Per-thickness: choose an existing type or auto-generate.
        mapping = {}
        for thk, rs in groups:
            auto = u"⚙ Auto-generate {0}mm".format(thk)
            choice = forms.SelectFromList.show(
                [auto] + type_names,
                title="Wall type for {0}mm walls ({1})".format(thk, len(rs)),
                default=auto)
            if not choice:
                return
            mapping[thk] = None if choice == auto else types[choice]

        if any(v is None for v in mapping.values()):
            bp = forms.SelectFromList.show(
                type_names,
                title="Base type to duplicate for auto-generated walls")
            if not bp:
                return
            base_type = types[bp]
            material_id = _pick_material()

    # Build.
    t = DB.Transaction(doc, "Generate Walls")
    t.Start()
    swallow_warnings(t)
    try:
        if parallel:
            cache = {}
            for thk, rs in groups:
                sel = mapping[thk]
                wt = (sel if sel is not None else get_or_create_wall_type(
                    doc, base_type, rs[0].thickness_ft, material_id,
                    _SNAP, cache))
                runs_by_type.append((wt, rs))

        res = place_walls(doc, runs_by_type, base_level, top_level,
                         structural=False, location_line=location_line)
        if res.placed == 0:
            t.RollBack()
        else:
            t.Commit()
    except Exception as e:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        logger.error("Wall generation failed: {0}".format(str(e)))
        forms.alert("Wall generation failed:\n{0}".format(str(e)),
                    title=__title__)
        return

    if res.placed == 0:
        if res.skipped and not res.errors:
            forms.alert("All {0} wall(s) already exist - nothing new to "
                        "add.".format(res.skipped), title=__title__)
            return
        msg = "No walls were created."
        if res.errors:
            msg += "\n\n" + "\n".join(res.errors[:5])
        forms.alert(msg, title=__title__)
        return

    extra = "\n{0} already existed (skipped).".format(res.skipped) if res.skipped else ""
    forms.alert(
        "Wall Generation Complete.\n\n"
        "Successfully created {0} Walls.{1}".format(res.placed, extra),
        title=__title__)
    if res.errors:
        output.print_md("**Notes:** " + "; ".join(res.errors[:5]))


if __name__ == "__main__":
    main()
