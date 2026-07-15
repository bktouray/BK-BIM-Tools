# -*- coding: utf-8 -*-
"""Highlights the active room in transparent green so the user can see where
they are during the flow (product owner, 2026-07-10). Same technique as
wall_confirmation_prompt.py's blue wall highlight (a transparent solid-fill
color override, applied/cleared via OverrideGraphicSettings) - kept as a
separate module since rooms and walls are cleared independently and use
different colors, not because the mechanism differs.

Live-verified 2026-07-10 against the real "Toilet Test File" project, rolled
back: applying the override (color, transparency, solid-fill pattern all
read back correctly) and clearing it (PatternId back to InvalidElementId,
Transparency back to 0) both confirmed working.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import Color, FilteredElementCollector, FillPatternElement, OverrideGraphicSettings

HIGHLIGHT_COLOR = Color(0, 200, 0)  # green
HIGHLIGHT_TRANSPARENCY = 70


def _solid_fill_pattern_id(doc):
    for fp in FilteredElementCollector(doc).OfClass(FillPatternElement).ToElements():
        try:
            if fp.GetFillPattern().IsSolidFill:
                return fp.Id
        except Exception:
            continue
    return None


def highlight_room(doc, view, room, clear=False):
    """Applies (or clears, if clear=True) the green transparent overlay on
    one room. Caller owns the Transaction (SAD Sec 4.4).
    """
    override = OverrideGraphicSettings()
    if not clear:
        pattern_id = _solid_fill_pattern_id(doc)
        if pattern_id is not None:
            override.SetSurfaceForegroundPatternId(pattern_id)
            override.SetSurfaceForegroundPatternColor(HIGHLIGHT_COLOR)
            override.SetSurfaceTransparency(HIGHLIGHT_TRANSPARENCY)
    view.SetElementOverrides(room.Id, override)
