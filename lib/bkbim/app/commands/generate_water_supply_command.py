# -*- coding: utf-8 -*-
"""Water Supply generation (ADR-0004 update 2026-07-10: Sanitary Drainage
paused, Water Supply is the active MEP slice). Zero Autodesk.Revit imports -
unit-testable with fakes, same pattern as generate_sanitary_drainage_command.

Rebuilt 2026-07-10 (same day) onto the corridor-based trunk-and-branch
RoutingGraph engine (MEP_Routing_Playbook.md), replacing the original per-
fixture independent-elbow-route model - the product owner tried that first
cut live and rejected it (every fixture routing straight to one shared point
produced a diagonal fan, not how real water supply is installed). This
command's job is now only Phase 1 (build + validate the abstract graph) -
Phases 2-4 (pipe geometry, fittings, accessory placement) are Revit-adapter
concerns, owned by `water_supply_flow.py`, not this command.

Deliberately still no discharge-unit sizing engine - a fixture-unit-based
water-supply sizing method (BS 8558 / BS EN 806-3 or otherwise) hasn't been
decided with the product owner yet, and this command doesn't guess one. Each
branch is sized from the fixture's own connector diameter; the trunk's own
diameter is a plain parameter the caller supplies.
"""

from bkbim.core.result import Result
from bkbim.domain.mep.models.connector_info import ConnectorInfo
from bkbim.domain.mep.routing.routing_graph import build_routing_graph


def _points_close(point_a, point_b, tolerance_mm=1.0):
    return sum(
        (point_b[i] - point_a[i]) ** 2 for i in range(3)
    ) ** 0.5 <= tolerance_mm


def _fixture_label(fixture):
    """Returns diagnostic text without exposing an adapter's connector ref."""
    return u"{0} : {1} [id {2}]".format(
        fixture.family_name or u"Unnamed Family",
        fixture.type_name or u"Unnamed Type",
        fixture.ref)


def run(fixtures, system_classification, corridor_points, wall_penetration_mm,
        max_branch_length_mm=None):
    """fixtures: list[FixtureInfo], each contributing its own
    `system_classification` connector as a routing target (e.g.
    u"DomesticColdWater" or u"DomesticHotWater" - matches Revit's own
    PipeSystemType string form, same convention as SANITARY/VENT in
    system_classification.py).
    corridor_points: ordered list of (x,y,z) - corridor_points[0] is the
    trunk's origin (the valve location); the rest describe the wall
    corridor the trunk runs along (already resolved by the caller from the
    confirmed wall(s) - never auto-discovered).
    wall_penetration_mm: the expected rough-in distance from a fixture to
    its wall - a validation reference, not a literal segment length (see
    routing_graph.py's BranchNode docstring).

    :rtype: Result wrapping {"graph": RoutingGraph, "routed": int,
    "skipped": int, "warnings": list[str]} - "routed"/"skipped" count
    fixtures that did/didn't contribute a target, before any Revit geometry
    exists yet.
    """
    warnings = []
    targets = []
    skipped = 0

    allowed_flows = (ConnectorInfo.FLOW_IN, ConnectorInfo.FLOW_BIDIRECTIONAL)
    for fixture in fixtures:
        connectors = fixture.matching_connectors(
            system_classification, allowed_flow_directions=allowed_flows)
        if not connectors:
            skipped += 1
            warnings.append(
                u"{0} has no {1} inlet connector - skipped.".format(
                    repr(fixture), system_classification))
            continue
        if len(connectors) > 1:
            skipped += 1
            warnings.append(
                u"{0} has {1} possible {2} inlet connectors - skipped because "
                u"the routing target is ambiguous.".format(
                    repr(fixture), len(connectors), system_classification))
            continue
        connector = connectors[0]
        targets.append((
            connector.ref, connector.position, connector.diameter_mm,
            _fixture_label(fixture)))

    if not targets:
        return Result.fail(
            u"No fixtures could be routed - {0} skipped.".format(skipped),
            diagnostics=warnings)

    graph = build_routing_graph(
        corridor_points, targets, wall_penetration_mm=wall_penetration_mm,
        max_branch_length_mm=max_branch_length_mm)
    warnings.extend(graph.warnings)

    accepted_junctions = []
    for junction, branch in graph.junctions:
        for accepted_junction, accepted_branch in accepted_junctions:
            if _points_close(junction.position, accepted_junction.position):
                return Result.fail(
                    u"Two selected fixtures project to the same trunk tap "
                    u"({0} and {1}). This Cold Water slice supports one "
                    u"branch per tap; select one fixture or adjust the "
                    u"layout.".format(
                        accepted_branch.target_label, branch.target_label),
                    diagnostics=warnings)
        accepted_junctions.append((junction, branch))

    return Result.ok(
        value={"graph": graph, "routed": len(targets), "skipped": skipped, "warnings": warnings},
        message=u"{0} fixture(s) added to the routing graph.{1}".format(
            len(targets), u" ({0} skipped)".format(skipped) if skipped else u""))
