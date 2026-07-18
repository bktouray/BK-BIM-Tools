# -*- coding: utf-8 -*-
"""Runs the Sanitary Drainage generation flow: read fixtures -> resolve the
project's real Sanitary system/pipe types -> run the app command -> one
Transaction creating the pipes. Tier 1 (no options window yet, MEP_SAD.md
Sec 7) - the underlying engine only just got its first live verification
(2026-07-10), so a polished WPF wizard isn't earned yet; this mirrors how
Auto Dimension itself shipped Tier 1 first.

`system_type_id`/`pipe_type_id` are resolved by NAME once via
`resolve_sanitary_system_type_id`/`resolve_pipe_type_id_by_name` - a real
gotcha found live: this project's Valsir pipe type's name contains a
registered-trademark byte (0xAE) that crashes this MCP bridge's own
json-encoding when it appears in a returned string, and more generally is
fragile to match by exact string. Prefer picking a PipeType via a live UI
element picker over hardcoding its name, once a picker exists; name lookup
here is a stopgap for this Tier-1 flow.
"""

import clr

clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")

from Autodesk.Revit.DB import FilteredElementCollector, Transaction
from Autodesk.Revit.DB.Plumbing import PipeType, PipingSystemType
from bkbim.app.commands import generate_sanitary_drainage_command
from bkbim.domain.geometry.units import ft_to_mm
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.mep.fixture_reader import RevitFixtureReader
from bkbim.revit.adapter.mep.nearby_wall_finder import find_nearest_walls_for_fixtures
from bkbim.revit.adapter.mep.pipe_writer import RevitPipeWriter
from bkbim.revit.adapter.mep.room_highlight import highlight_room
from bkbim.revit.adapter.mep.room_reader import RevitRoomReader
from bkbim.revit.adapter.mep.room_selection_prompt import pick_rooms
from bkbim.revit.adapter.mep.wall_confirmation_prompt import confirm_walls, highlight_walls
from bkbim.revit.adapter.stable_representation import element_id_token
from bkbim.ui.views.result_dialog import show_result

_TRANSACTION_LABEL = u"Generate Sanitary Drainage"
_TITLE = u"Generate Sanitary Drainage"

# Coarse family-name keyword guess, NOT a persisted Family Mapping (that's
# explicitly deferred, MEP_SAD.md Sec 8) - a fixture this can't classify just
# gets a "no discharge-unit data" warning from validate_fixtures rather than
# blocking the run, same as any other unresolved fixture_type_key.
_FIXTURE_TYPE_KEYWORDS = [
    (u"toilet", u"WC"), (u"wc", u"WC"),
    (u"basin", u"WashBasin"), (u"lavatory", u"WashBasin"), (u"sink", u"KitchenSink"),
    (u"bath", u"Bath"),
    (u"shower", u"Shower"),
    (u"gully", u"FloorGully50"), (u"drain", u"FloorGully50"),
]


def _guess_fixture_type_key(family_name):
    lowered = (family_name or u"").lower()
    for keyword, key in _FIXTURE_TYPE_KEYWORDS:
        if keyword in lowered:
            return key
    return None


def resolve_piping_system_type_id(doc, system_type_name=u"Sanitary"):
    for st in FilteredElementCollector(doc).OfClass(PipingSystemType).ToElements():
        if type_name(st) == system_type_name:
            return st.Id
    return None


def resolve_pipe_type_id_by_name(doc, pipe_type_name):
    for pt in FilteredElementCollector(doc).OfClass(PipeType).ToElements():
        if type_name(pt) == pipe_type_name:
            return pt.Id
    return None


def run_sanitary_drainage_flow(doc, fixtures, target_point_mm, standard, usage_type,
                                level_id, pipe_type_name):
    """fixtures: list[FixtureInfo] (already read + filtered by the caller).
    target_point_mm: (x, y, z) tuple - the stack/riser connection point,
    already resolved to a plain point by the caller (never auto-discovered,
    MEP_SAD.md Sec 5).
    pipe_type_name: the real Revit PipeType name to route with (e.g. the
    project's PVC type) - resolved to an ElementId here.

    Returns (result, message) - result is None if a required project element
    (Sanitary system type or the named pipe type) couldn't be resolved.
    """
    system_type_id = resolve_piping_system_type_id(doc)
    if system_type_id is None:
        return None, u"No 'Sanitary' Piping System Type found in this project."

    pipe_type_id = resolve_pipe_type_id_by_name(doc, pipe_type_name)
    if pipe_type_id is None:
        return None, u"Pipe type '{0}' not found in this project.".format(pipe_type_name)

    writer = RevitPipeWriter(doc, system_type_id, pipe_type_id, level_id)

    t = Transaction(doc, _TRANSACTION_LABEL)
    t.Start()
    try:
        result = generate_sanitary_drainage_command.run(
            fixtures, target_point_mm, standard, usage_type, writer)
    except Exception as e:
        t.RollBack()
        return None, u"Error:\n{0}".format(str(e))

    if result.success:
        t.Commit()
    else:
        t.RollBack()

    return result, result.message


def read_all_fixtures(doc):
    return RevitFixtureReader(doc).read_fixtures()


def run_wizard(uidoc, doc, standard, usage_type, pipe_type_name):
    """Full Tier-1/2 flow (product owner, 2026-07-10, after reviewing a
    reference tool's step structure): pick room(s), highlighted green so the
    user always knows where they are -> read that room's fixtures -> for
    each, detect the nearest wall and let the user confirm/reselect it
    (highlighted blue) -> pick the target/stack point -> run the command.

    Wall confirmation is informational only right now (MEP_SAD.md Sec 5's
    direct point-to-point routing doesn't route THROUGH the confirmed wall
    yet) - the chosen walls are shown in the final summary so the user can
    see what was recorded, not silently discarded.

    Returns (result, message) same shape as run_sanitary_drainage_flow -
    None/None if the user cancelled at any step (normal, not an error).
    """
    view = doc.ActiveView

    rooms = RevitRoomReader(doc).read_rooms()
    if not rooms:
        return None, u"No rooms found in this project."

    picked_rooms = pick_rooms(rooms, title=_TITLE)
    if not picked_rooms:
        return None, None

    highlight_t = Transaction(doc, u"Highlight selected rooms")
    highlight_t.Start()
    for room_info in picked_rooms:
        room_elem = doc.GetElement(room_info.ref)
        if room_elem is not None:
            highlight_room(doc, view, room_elem)
    highlight_t.Commit()

    try:
        fixtures = RevitFixtureReader(doc).read_fixtures(rooms=picked_rooms)
        if not fixtures:
            show_result(_TITLE, u"No plumbing fixtures found in the selected room(s).")
            return None, None

        for fixture in fixtures:
            if fixture.fixture_type_key is None:
                fixture.fixture_type_key = _guess_fixture_type_key(fixture.family_name)

        wall_map = find_nearest_walls_for_fixtures(doc, fixtures)
        candidate_walls = []
        seen_ids = set()
        for fixture in fixtures:
            nearest = wall_map.get(element_id_token(fixture.ref))
            if nearest is not None and element_id_token(nearest.wall_ref) not in seen_ids:
                seen_ids.add(element_id_token(nearest.wall_ref))
                wall_elem = doc.GetElement(nearest.wall_ref)
                if wall_elem is not None:
                    candidate_walls.append(wall_elem)

        wall_highlight_t = Transaction(doc, u"Highlight candidate walls")
        wall_highlight_t.Start()
        if candidate_walls:
            highlight_walls(doc, view, candidate_walls)
        wall_highlight_t.Commit()

        try:
            confirmed_walls = confirm_walls(uidoc, doc, candidate_walls, title=_TITLE)
        finally:
            clear_t = Transaction(doc, u"Clear wall highlight")
            clear_t.Start()
            if candidate_walls:
                highlight_walls(doc, view, candidate_walls, clear=True)
            if confirmed_walls:
                highlight_walls(doc, view, confirmed_walls, clear=True)
            clear_t.Commit()

        show_result(
            _TITLE,
            u"Click the point this room's drainage connects to (the stack/riser).",
            subtitle=u"After this window closes, click the target point in Revit.")
        try:
            picked_point = uidoc.Selection.PickPoint(u"{0}: click the target/stack point".format(_TITLE))
        except Exception:
            return None, None
        target_point_mm = (ft_to_mm(picked_point.X), ft_to_mm(picked_point.Y), ft_to_mm(picked_point.Z))

        level_id = fixtures[0].level_ref

        result, message = run_sanitary_drainage_flow(
            doc, fixtures, target_point_mm, standard, usage_type, level_id, pipe_type_name)

        if confirmed_walls:
            wall_names = u", ".join(type_name(w) for w in confirmed_walls)
            message = u"{0}\n\nWalls recorded near these fixtures: {1}".format(message, wall_names)

        return result, message
    finally:
        room_clear_t = Transaction(doc, u"Clear room highlight")
        room_clear_t.Start()
        for room_info in picked_rooms:
            room_elem = doc.GetElement(room_info.ref)
            if room_elem is not None:
                highlight_room(doc, view, room_elem, clear=True)
        room_clear_t.Commit()
