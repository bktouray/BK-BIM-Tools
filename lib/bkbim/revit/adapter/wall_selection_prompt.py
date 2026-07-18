# -*- coding: utf-8 -*-
"""Prompts for exterior perimeter wall treatment, for the 3-string exterior
wall dimensioning. Shown AFTER the options window (product owner: "make it
after I select the autodimension walls and openings and after I select
dimension styles and other stuff, prompt me to select exterior walls").

Three-way choice (2026-07-08 follow-up - Wall.Function is unreliable in this
project's models, see wall_context_builder.py, so "just detect it" needed a
real geometric answer): Auto-detect (via exterior_wall_detector - Room
adjacency if Rooms are placed, a geometric boundary trace otherwise), Pick
manually (today's PickObjects flow, unchanged), or Skip (just conventional
dimensioning). Auto-detect finding nothing offers one fallback prompt to
switch to manual picking instead of silently dimensioning nothing.

(2026-07-07: originally just a Yes/No to manual picking, with a real
`forms.alert()` popup before the interactive pick starts - "make a visible
prompt alerting the user that its time to select the exterior walls" - kept
unchanged for the Pick Manually branch.)

The manual-pick step itself lives in `pick_walls_manually()`, extracted
2026-07-08 so ExteriorWallDimension.pushbutton (a small standalone tool that
always wants manual picking - "give me a small push button... so that i can
manually select walls if i wish to") can call it directly without going
through this module's 3-way choice first.

`pick_exterior_walls` also asks for a dimension style for the 2 EXTRA
exterior perimeter strings (2026-07-08 follow-up: "one more option that
would be nice is to be able to select a specific dimension style for
exterior walls if i choose it") via `pick_exterior_perimeter_style()` -
asked only once exterior treatment is actually confirmed (AUTO_DETECT found
something, or PICK_MANUALLY yielded a non-empty selection), never in the
SKIP_EXTERIOR branch, since there's nothing to ask about otherwise. The
normal wall-run string always keeps whichever style was already chosen in
the main options window; this only affects the perpendicular-wall chain +
overall strings.
"""

import clr

clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")

from Autodesk.Revit.DB import Wall
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType

from bkbim.revit.adapter.dimension_type_reader import list_linear_dimension_types
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.exterior_wall_detector import detect_exterior_walls
from bkbim.revit.adapter.stable_representation import element_id_token
from bkbim.ui.views.category_picker import show_category_picker
from bkbim.ui.views.list_picker import show_list_picker
from bkbim.ui.views.result_dialog import show_result

AUTO_DETECT = u"Auto-detect exterior walls"
PICK_MANUALLY = u"Pick manually"
SKIP_EXTERIOR = u"No, just conventional dimensioning"
SAME_AS_MAIN_STYLE = u"Same as the main dimension style"


class _WallOnlyFilter(ISelectionFilter):
    def AllowElement(self, elem):
        return isinstance(elem, Wall)

    def AllowReference(self, reference, point):
        return False


def pick_exterior_walls(uidoc, doc, view, dimensionable_walls, title):
    """Asks how (or whether) to do exterior-wall perimeter dimensioning.
    Returns (exterior_wall_ids, exterior_perimeter_dimension_type):

    - exterior_wall_ids: a set of element-id-token strings - empty if the
      user chose "just conventional dimensioning," auto-detection found
      nothing and the user declined to switch to manual picking, pressed
      Escape while picking, or finished with nothing picked. Every one of
      those is a normal, expected outcome (every wall just gets the usual
      single-string treatment), never an error.
    - exterior_perimeter_dimension_type: the chosen DimensionType for the 2
      extra perimeter strings, or None to keep using the main style. Always
      None when exterior_wall_ids is empty (nothing to ask about).
    """
    choice = show_category_picker(
        title,
        u"Also dimension exterior walls with the extra perimeter strings "
        u"(openings / perpendicular walls / overall), or just run the "
        u"normal single-string dimensioning for every wall?",
        [AUTO_DETECT, PICK_MANUALLY, SKIP_EXTERIOR])

    if choice == AUTO_DETECT:
        detected = detect_exterior_walls(doc, view, dimensionable_walls)
        if detected:
            return detected, pick_exterior_perimeter_style(doc, title)
        fallback = show_category_picker(
            title,
            u"Auto-detect didn't find any exterior walls in this view (no "
            u"Rooms placed, and the wall layout doesn't form a closed "
            u"boundary). Pick them manually instead?",
            [PICK_MANUALLY, SKIP_EXTERIOR])
        if fallback != PICK_MANUALLY:
            return set(), None
        choice = PICK_MANUALLY

    if choice != PICK_MANUALLY:
        return set(), None

    picked_walls = pick_walls_manually(uidoc, doc, title)
    exterior_wall_ids = set(element_id_token(w.Id) for w in picked_walls)
    if not exterior_wall_ids:
        return exterior_wall_ids, None
    return exterior_wall_ids, pick_exterior_perimeter_style(doc, title)


def pick_exterior_perimeter_style(doc, title):
    """Asks which dimension style to use for the 2 EXTRA exterior perimeter
    strings (the perpendicular-wall chain + overall) - the main wall-run
    string always keeps whichever style was chosen in the main options
    window. Returns a DimensionType, or None to keep using the main style.
    """
    dimension_types = list_linear_dimension_types(doc)
    if not dimension_types:
        return None

    names = [SAME_AS_MAIN_STYLE] + [type_name(dt) for dt in dimension_types]
    picked = show_list_picker(
        title,
        u"Dimension style for the 2 extra exterior strings.",
        names,
        default_label=SAME_AS_MAIN_STYLE)
    if not picked or picked == SAME_AS_MAIN_STYLE:
        return None

    index = names.index(picked) - 1
    return dimension_types[index]


def pick_walls_manually(uidoc, doc, title):
    """Shows the visible "it's time to pick" alert, then interactively
    prompts for walls via PickObjects. Returns a list of Wall elements -
    empty if the user pressed Escape or finished with nothing picked
    (normal outcomes, not errors). Standalone so a tool that always wants
    manual picking (no auto-detect/skip choice first) can call this
    directly - see ExteriorWallDimension.pushbutton.
    """
    show_result(
        title,
        u"It's time to select the exterior walls.\n\n"
        u"Click each exterior wall in the view (Ctrl+click or drag a box for "
        u"more than one), then click Finish on the ribbon/status bar.\n\n"
        u"Press Escape instead to skip - every wall will just get the "
        u"normal single-string dimensioning.",
        subtitle=u"After this window closes, continue in Revit.")

    try:
        picked_refs = uidoc.Selection.PickObjects(
            ObjectType.Element, _WallOnlyFilter(),
            u"{0}: click exterior walls, then Finish".format(title))
    except Exception:
        return []

    return [doc.GetElement(ref.ElementId) for ref in picked_refs]
