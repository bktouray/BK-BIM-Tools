# -*- coding: utf-8 -*-
__title__ = u"AutoGrid"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Generate native Revit grids from a CAD layer. Pick the grid
layer and get clean, auto-labelled grid lines (A,B,C across / 1,2,3 down).
"""

from pyrevit import revit, DB, forms, script

# Dev reload: always pick up the latest bkbim.automation lib code on each click.
import sys as _sys
for _m in [_n for _n in list(_sys.modules) if _n.startswith("bkbim.automation")]:
    del _sys.modules[_m]

from bkbim.automation import cadreader
from bkbim.automation.common import to_feet
from bkbim.automation.grids import generate_grids

logger = script.get_logger()
output = script.get_output()

doc = revit.doc


def main():
    if doc is None:
        forms.alert("No active Revit document.", title=__title__)
        return

    imports = cadreader.get_import_instances(doc)
    if not imports:
        forms.alert(
            "No imported CAD (DWG) found in this model.\n\n"
            "Insert > Import CAD, then run this tool again.",
            title=__title__,
        )
        return

    # If several DWGs are present, let the user choose which one.
    if len(imports) == 1:
        chosen_import = imports[0]
    else:
        opts = {}
        for inst in imports:
            type_el = doc.GetElement(inst.GetTypeId())
            name = type_el.Name if type_el else "Import {0}".format(inst.Id)
            opts[name] = inst
        pick = forms.SelectFromList.show(
            sorted(opts.keys()), title="Select CAD import", multiselect=False
        )
        if not pick:
            return
        chosen_import = opts[pick]

    # Build the layer list (only layers that actually have curves).
    layers = cadreader.list_layers(doc, chosen_import)
    layers = [(n, c) for (n, c) in layers if c > 0]
    if not layers:
        forms.alert("No line geometry found in the CAD import.",
                    title=__title__)
        return

    layer_labels = ["{0}   ({1} lines)".format(n, c) for (n, c) in layers]
    # Pre-select a layer that looks grid-ish if present.
    default_idx = 0
    for i, (n, _c) in enumerate(layers):
        if "grid" in n.lower():
            default_idx = i
            break

    picked_label = forms.SelectFromList.show(
        layer_labels,
        title="AutoGrid - pick the GRID layer",
        multiselect=False,
        default=layer_labels[default_idx],
    )
    if not picked_label:
        return
    layer_name = layers[layer_labels.index(picked_label)][0]

    # Options: auto-extend distance + unit.
    auto_extend = forms.alert(
        "Auto-extend grid lines past the building outline?",
        title=__title__,
        yes=True, no=True,
    )
    extend_ft = 0.0
    if auto_extend:
        unit = forms.CommandSwitchWindow.show(
            ["mm", "in", "ft", "m"], message="Extend distance unit:"
        ) or "ft"
        raw = forms.ask_for_string(
            default="60" if unit == "in" else "1500" if unit == "mm" else "5",
            prompt="Extend each grid end by how much ({0})?".format(unit),
            title=__title__,
        )
        try:
            extend_ft = to_feet(float(raw), unit)
        except (TypeError, ValueError):
            extend_ft = 0.0

    curves = cadreader.curves_on_layer(doc, chosen_import, layer_name)
    if not curves:
        forms.alert("No curves on layer '{0}'.".format(layer_name),
                    title=__title__)
        return

    res = None
    t = DB.Transaction(doc, "Generate Grids")
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
        logger.error("Grid generation failed: {0}".format(str(e)))
        forms.alert("Grid generation failed:\n{0}".format(str(e)),
                    title=__title__)
        return

    # Report.
    if res.created == 0:
        if res.exists and not res.errors:
            forms.alert("All {0} grid line(s) already exist - nothing new "
                        "to add.".format(res.exists), title=__title__)
            return
        msg = "No grids were created."
        if res.errors:
            msg += "\n\n" + "\n".join(res.errors[:5])
        forms.alert(msg, title=__title__)
        return

    extra = "\n{0} already existed (skipped).".format(res.exists) if res.exists else ""
    forms.alert(
        "Grid Generation Complete.\n\n"
        "Successfully placed {0} Grid Lines.{1}".format(res.created, extra),
        title=__title__,
    )
    output.print_md("**AutoGrid** - created {0} grids: {1}".format(
        res.created, ", ".join(res.names)))


if __name__ == "__main__":
    main()
