# -*- coding: utf-8 -*-
"""Shared pre-scan pickers and readers for the CAD-to-Revit tools (AutoColumn,
AutoWall, AutoFloor, AutoGrid, the Door/Window opening flow).

`pick_cad_import`/`pick_cad_layer` were copy-pasted near-verbatim across 5
different script.py/automation modules (2026-07-15 CAD to Revit panel
redesign) - this is a pure dedup, same forms.SelectFromList calls and
defaults as before, no UX change. They stay interactive/pre-scan (picking
the CAD source is inherently sequential - the layer list depends on which
import was chosen), unlike Level/Material, which moved INTO each tool's new
themed options window as ComboBoxes - so `list_levels`/`list_materials`
here are plain readers (no forms popup), returning the ordered element list
for a flow module to pass into its options window constructor, matching how
structural_dimension_flow.py passes pre-fetched dimension_types/
structural_types into show_structural_dimension_options() rather than
letting the window read Revit itself.
"""

from pyrevit import DB, forms

from bkbim.automation import cadreader
from bkbim.revit.adapter.element_naming import type_name


def pick_cad_import(doc, title):
    """Pick which ImportInstance to read from. Auto-picks the only one."""
    imports = cadreader.get_import_instances(doc)
    if not imports:
        forms.alert(u"No imported CAD (DWG) found in this model.\n\n"
                    u"Insert > Import CAD, then run this tool again.",
                    title=title)
        return None
    if len(imports) == 1:
        return imports[0]
    opts = {}
    for inst in imports:
        te = doc.GetElement(inst.GetTypeId())
        opts[type_name(te) if te else str(inst.Id)] = inst
    pick = forms.SelectFromList.show(sorted(opts.keys()), title=u"Select CAD import")
    return opts.get(pick)


def pick_cad_layer(doc, inst, title, hint):
    """Pick a CAD layer, pre-selecting the first one whose name contains `hint`."""
    layers = [(n, c) for (n, c) in cadreader.list_layers(doc, inst) if c > 0]
    if not layers:
        forms.alert(u"No line geometry in the CAD import.", title=title)
        return None
    labels = [u"{0}   ({1} segments)".format(n, c) for (n, c) in layers]
    default = labels[0]
    for i, (n, _c) in enumerate(layers):
        if hint in n.lower():
            default = labels[i]
            break
    pick = forms.SelectFromList.show(
        labels, title=u"{0} - pick the {1} layer".format(title, hint.upper()),
        default=default)
    if not pick:
        return None
    return layers[labels.index(pick)][0]


def list_levels(doc):
    """All Levels in the doc, sorted low -> high by elevation."""
    levels = DB.FilteredElementCollector(doc).OfClass(DB.Level).ToElements()
    return sorted(levels, key=lambda lv: lv.Elevation)


def list_materials(doc):
    """All Materials in the doc, sorted by name."""
    mats = DB.FilteredElementCollector(doc).OfClass(DB.Material).ToElements()
    return sorted(mats, key=lambda m: type_name(m).lower())
