# -*- coding: utf-8 -*-
"""Revit adapter for the DWV collector Stage 2 pipe-only slice.

This module intentionally does not own the interactive wizard yet. It is the
small adapter seam we can exercise from a future button/MCP validation:

    fixtures + corridor + stack + options
        -> pure DWV collector graph
        -> pipe-only RoutingPlan
        -> Revit Pipe elements in one transaction

No fittings, no connector joining and no accessory placement are attempted in
this slice.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import Transaction

from bkbim.app.commands import generate_dwv_collector_command
from bkbim.domain.geometry.units import ft_to_mm
from bkbim.domain.mep.models.connector_info import ConnectorInfo
from bkbim.domain.mep.models.system_classification import SANITARY
from bkbim.domain.mep.sanitary.slope_rules import min_slope_percent_for_dn
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.mep.fixture_reader import RevitFixtureReader
from bkbim.revit.adapter.mep.pipe_writer import RevitPipeWriter
from bkbim.revit.adapter.mep.room_highlight import highlight_room
from bkbim.revit.adapter.mep.room_reader import RevitRoomReader
from bkbim.revit.adapter.mep.room_selection_prompt import pick_rooms
from bkbim.revit.adapter.mep.sanitary_drainage_flow import (
    resolve_pipe_type_id_by_name, resolve_piping_system_type_id,
)
from bkbim.revit.adapter.mep.selection_retry import ask_retry_selection
from bkbim.revit.adapter.stable_representation import element_id_token
from bkbim.ui.views.dwv_collector_options import show_dwv_collector_options
from bkbim.ui.views.list_picker import show_multi_list_picker
from bkbim.ui.views.result_dialog import show_result

_TRANSACTION_LABEL = u"Generate DWV Collector Pipes"
_TITLE = u"Generate Sanitary Drainage"
_SANITARY_ALLOWED_FLOWS = (
    ConnectorInfo.FLOW_OUT,
    ConnectorInfo.FLOW_BIDIRECTIONAL,
)

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


def _fixture_label(fixture):
    return u"{0} : {1}  [id {2}]".format(
        fixture.family_name, fixture.type_name, element_id_token(fixture.ref))


def _sanitary_connectors(fixture):
    return fixture.matching_connectors(
        SANITARY, allowed_flow_directions=_SANITARY_ALLOWED_FLOWS)


def _connector_is_connected(connector):
    try:
        return bool(connector.ref.IsConnected)
    except Exception:
        return False


def _eligible_dwv_fixtures(fixtures):
    eligible = []
    skipped = []
    for fixture in fixtures:
        connectors = _sanitary_connectors(fixture)
        if len(connectors) != 1:
            skipped.append(fixture)
            continue
        # For the pipe-only stage, already-connected outlets would make the
        # later connector pass ambiguous and can trigger Revit network errors.
        if _connector_is_connected(connectors[0]):
            skipped.append(fixture)
            continue
        eligible.append(fixture)
    return eligible, skipped


def _pick_fixtures(fixtures, title=_TITLE):
    by_label = {}
    for fixture in fixtures:
        by_label[_fixture_label(fixture)] = fixture
    labels = sorted(by_label.keys())
    picked = show_multi_list_picker(
        title,
        u"Pick the fixtures to drain into the DWV collector.",
        labels)
    if not picked:
        return None
    return [by_label[label] for label in picked]


def _pick_stack_point(uidoc, title=_TITLE):
    while True:
        try:
            picked = uidoc.Selection.PickPoint(
                u"{0}: click the downstream stack/riser point".format(title))
            return (ft_to_mm(picked.X), ft_to_mm(picked.Y), ft_to_mm(picked.Z))
        except Exception:
            if not ask_retry_selection(title):
                return None


def _default_slope_percent(diameter_mm, standard):
    value = min_slope_percent_for_dn(diameter_mm, standard)
    return value if value is not None else 2.0


def run_dwv_collector_pipe_geometry_flow(
        doc, fixtures, corridor_points, stack_point, standard, usage_type,
        level_id, pipe_type_name, collector_diameter_mm, slope_percent,
        max_branch_length_mm=None):
    """Creates DWV collector/branch pipes only.

    Returns (result, message). ``result`` is a Result from the app command or
    pipe writer; ``None`` means required Revit project setup could not be
    resolved before opening a transaction.
    """
    system_type_id = resolve_piping_system_type_id(doc)
    if system_type_id is None:
        return None, u"No 'Sanitary' Piping System Type found in this project."

    pipe_type_id = resolve_pipe_type_id_by_name(doc, pipe_type_name)
    if pipe_type_id is None:
        return None, u"Pipe type '{0}' not found in this project.".format(
            pipe_type_name)

    command_result = generate_dwv_collector_command.run(
        fixtures=fixtures,
        corridor_points=corridor_points,
        stack_point=stack_point,
        standard=standard,
        usage_type=usage_type,
        collector_diameter_mm=collector_diameter_mm,
        slope_percent=slope_percent,
        max_branch_length_mm=max_branch_length_mm)
    if not command_result.success:
        return command_result, command_result.message

    writer = RevitPipeWriter(doc, system_type_id, pipe_type_id, level_id)
    transaction = Transaction(doc, _TRANSACTION_LABEL)
    transaction.Start()
    try:
        write_result = writer.write(command_result.value["pipe_plan"])
    except Exception as error:
        transaction.RollBack()
        return None, u"Error:\n{0}".format(str(error))

    if write_result.success:
        transaction.Commit()
    else:
        transaction.RollBack()
        return write_result, write_result.message

    warnings = command_result.value.get("warnings", [])
    message = (
        u"{0} fixture(s) routed into a DWV collector. "
        u"{1} pipe segment(s) created. Fittings are not placed in this slice.".format(
            command_result.value["routed"],
            write_result.value.get("created", 0)))
    if warnings:
        message += u"\n\nWarnings:\n- " + u"\n- ".join(warnings)
    return command_result, message


def run_bathroom_dwv_pipe_geometry_flow(
        doc, fixtures, stack_point, standard, usage_type, level_id,
        pipe_type_name, collector_diameter_mm, slope_percent,
        max_branch_length_mm=None, wc_drop_z_mm=None):
    """Creates the product-owner-preferred bathroom DWV pipe-only topology."""
    system_type_id = resolve_piping_system_type_id(doc)
    if system_type_id is None:
        return None, u"No 'Sanitary' Piping System Type found in this project."

    pipe_type_id = resolve_pipe_type_id_by_name(doc, pipe_type_name)
    if pipe_type_id is None:
        return None, u"Pipe type '{0}' not found in this project.".format(
            pipe_type_name)

    command_result = generate_dwv_collector_command.run_bathroom_wc_backbone(
        fixtures=fixtures,
        stack_point=stack_point,
        standard=standard,
        usage_type=usage_type,
        collector_diameter_mm=collector_diameter_mm,
        slope_percent=slope_percent,
        max_branch_length_mm=max_branch_length_mm,
        wc_drop_z_mm=wc_drop_z_mm)
    if not command_result.success:
        return command_result, command_result.message

    writer = RevitPipeWriter(doc, system_type_id, pipe_type_id, level_id)
    transaction = Transaction(doc, _TRANSACTION_LABEL)
    transaction.Start()
    try:
        write_result = writer.write(command_result.value["pipe_plan"])
    except Exception as error:
        transaction.RollBack()
        return None, u"Error:\n{0}".format(str(error))

    if write_result.success:
        transaction.Commit()
    else:
        transaction.RollBack()
        return write_result, write_result.message

    warnings = command_result.value.get("warnings", [])
    message = (
        u"{0} fixture(s) routed using the WC drain as the main DWV backbone. "
        u"{1} pipe segment(s) created. Fittings are not placed in this slice.".format(
            command_result.value["routed"],
            write_result.value.get("created", 0)))
    if warnings:
        message += u"\n\nWarnings:\n- " + u"\n- ".join(warnings)
    return command_result, message


def run_wizard(uidoc, doc, standard, usage_type, pipe_type_name):
    """Interactive first DWV vertical slice.

    This intentionally creates pipes only. The default topology is the
    product-owner bathroom practice: the WC DN110 drain is the main backbone
    to the stack; sinks/floor drains/showers branch into that drain.
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

        eligible, skipped = _eligible_dwv_fixtures(fixtures)
        if skipped:
            show_result(
                _TITLE,
                u"{0} fixture(s) were skipped because they have no usable "
                u"single unconnected Sanitary outlet connector.\n\n"
                u"{1} fixture(s) remain eligible for this pipe-only DWV "
                u"slice.".format(len(skipped), len(eligible)))
        if not eligible:
            return None, u"No eligible DWV fixtures found in the selected room(s)."

        selected_fixtures = _pick_fixtures(eligible, title=_TITLE)
        if not selected_fixtures:
            return None, None

        selected_connectors = [
            _sanitary_connectors(fixture)[0]
            for fixture in selected_fixtures]
        default_collector_diameter = max(
            connector.diameter_mm for connector in selected_connectors)
        options = show_dwv_collector_options(
            _TITLE,
            default_collector_diameter_mm=default_collector_diameter,
            minimum_collector_diameter_mm=default_collector_diameter,
            default_slope_percent=_default_slope_percent(
                default_collector_diameter, standard))
        if options is None:
            return None, None

        show_result(
            _TITLE,
            u"Click the downstream stack/riser point.\n\n"
            u"The WC drain will run as the main DWV backbone toward this point.")
        stack_point = _pick_stack_point(uidoc, title=_TITLE)
        if stack_point is None:
            return None, None

        level_id = picked_rooms[0].level_ref
        level = doc.GetElement(level_id)
        if level is None:
            return None, u"The selected room does not have a usable Revit level."
        level_elevation_mm = ft_to_mm(level.Elevation)
        wc_drop_z_mm = level_elevation_mm - options.wc_drop_below_level_mm
        result, message = run_bathroom_dwv_pipe_geometry_flow(
            doc=doc,
            fixtures=selected_fixtures,
            stack_point=stack_point,
            standard=standard,
            usage_type=usage_type,
            level_id=level_id,
            pipe_type_name=pipe_type_name,
            collector_diameter_mm=options.collector_diameter_mm,
            slope_percent=options.slope_percent,
            max_branch_length_mm=standard.mep_max_branch_length_mm,
            wc_drop_z_mm=wc_drop_z_mm)

        if message:
            message = (
                u"{0}\n\n"
                u"DWV mode: pipe-only WC-backbone bathroom slice\n"
                u"Collector diameter: {1:g} mm\n"
                u"Slope toward stack: {2:g}%\n"
                u"WC drop below level/slab: {3:g} mm\n\n"
                u"Note: wyes, elbows, stack tie-in and fixture connector joins "
                u"are intentionally deferred to the next DWV fitting pass.".format(
                    message,
                    float(options.collector_diameter_mm),
                    float(options.slope_percent),
                    float(options.wc_drop_below_level_mm)))
        return result, message
    finally:
        room_clear_t = Transaction(doc, u"Clear room highlight")
        room_clear_t.Start()
        for room_info in picked_rooms:
            room_elem = doc.GetElement(room_info.ref)
            if room_elem is not None:
                highlight_room(doc, view, room_elem, clear=True)
        room_clear_t.Commit()
