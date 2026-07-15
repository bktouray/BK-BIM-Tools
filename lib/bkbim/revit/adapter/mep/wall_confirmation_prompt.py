# -*- coding: utf-8 -*-
"""Lets the user confirm/adjust which wall(s) a fixture's pipe routes
through - auto-detects via nearby_wall_finder, highlights them blue in the
view, and requires explicit confirmation before proceeding (product owner,
2026-07-10, after reviewing a reference tool's "wet walls detected in blue,
Yes/No" pattern). The pick/deselect mechanism reuses the exact PickObjects +
Wall-only-filter technique already proven in wall_selection_prompt.py's
`pick_walls_manually` (ADR-0002 second-consumer rule) - Revit's own picker
already supports ctrl-click add/remove and an explicit Finish confirmation,
so no custom pick-loop needed.

Live-verified 2026-07-10: the highlight overlay itself (apply a transparent
solid-fill color via OverrideGraphicSettings, then clear it back to
default) - confirmed both directions against the real "Toilet Test File"
project, rolled back. NOT verified end-to-end: the interactive click-to-
pick/deselect gesture needs a live human at the keyboard - this MCP testing
channel can only confirm the API calls are correctly formed, same
limitation already documented for the drag-multiselect gesture in
[[bkbim-pushbutton-convention]]. Try this live before trusting it fully.
"""

import clr

clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")

from Autodesk.Revit.DB import Color, FilteredElementCollector, FillPatternElement, OverrideGraphicSettings, Wall
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
from pyrevit import forms

from bkbim.revit.adapter.element_naming import type_name
from bkbim.ui.views.category_picker import show_category_picker

HIGHLIGHT_COLOR = Color(0, 120, 220)  # blue, matches the reference tool's "wet wall" convention
HIGHLIGHT_TRANSPARENCY = 60

USE_DETECTED = u"Yes, use these"
PICK_DIFFERENT = u"No, let me pick different ones"


class _WallOnlyFilter(ISelectionFilter):
    def AllowElement(self, elem):
        return isinstance(elem, Wall)

    def AllowReference(self, reference, point):
        return False


def _solid_fill_pattern_id(doc):
    for fp in FilteredElementCollector(doc).OfClass(FillPatternElement).ToElements():
        try:
            if fp.GetFillPattern().IsSolidFill:
                return fp.Id
        except Exception:
            continue
    return None


def highlight_walls(doc, view, walls, clear=False):
    """Applies (or clears, if clear=True) the blue transparent overlay on
    each wall. Caller owns the Transaction - same convention as every writer
    in this codebase (SAD Sec 4.4).
    """
    override = OverrideGraphicSettings()
    if not clear:
        pattern_id = _solid_fill_pattern_id(doc)
        if pattern_id is not None:
            override.SetSurfaceForegroundPatternId(pattern_id)
            override.SetSurfaceForegroundPatternColor(HIGHLIGHT_COLOR)
            override.SetSurfaceTransparency(HIGHLIGHT_TRANSPARENCY)
    for wall in walls:
        view.SetElementOverrides(wall.Id, override)


def confirm_walls(uidoc, doc, detected_walls, title=u"Confirm walls"):
    """detected_walls: list[Wall] already auto-detected (e.g. via
    nearby_wall_finder.find_nearest_wall per fixture) - caller has already
    highlighted them via highlight_walls() inside its own Transaction before
    calling this, since showing the highlight and asking the confirmation
    question happen in the same view state.

    Returns the final list[Wall] the user confirmed - empty if they
    cancelled at every step (a normal, expected outcome, not an error).
    """
    if detected_walls:
        wall_list_text = u"\n".join(
            u"  - {0} (id {1})".format(type_name(w), w.Id) for w in detected_walls)
        forms.alert(
            u"Detected {0} wall(s), highlighted in blue in the view:\n\n{1}".format(
                len(detected_walls), wall_list_text),
            title=title)

        choice = show_category_picker(
            title, u"Use these wall(s)?", [USE_DETECTED, PICK_DIFFERENT])
        if choice == USE_DETECTED:
            return detected_walls
        if choice is None:
            return []

    forms.alert(
        u"Click each wall this pipe should route through (Ctrl+click for "
        u"more than one; click an already-selected wall again to remove it), "
        u"then click Finish on the ribbon/status bar. Press Escape to select none.",
        title=title)
    try:
        picked_refs = uidoc.Selection.PickObjects(
            ObjectType.Element, _WallOnlyFilter(),
            u"{0}: click wall(s), then Finish".format(title))
    except Exception:
        return []

    picked_walls = [doc.GetElement(ref.ElementId) for ref in picked_refs]
    if picked_walls:
        names = u"\n".join(u"  - {0}".format(type_name(w)) for w in picked_walls)
        forms.alert(u"Selected:\n\n{0}".format(names), title=title)
    return picked_walls
