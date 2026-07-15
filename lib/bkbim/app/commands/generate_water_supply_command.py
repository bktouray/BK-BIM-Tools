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
from bkbim.domain.mep.routing.routing_graph import build_routing_graph


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

    for fixture in fixtures:
        connector = fixture.primary_connector(system_classification)
        if connector is None:
            skipped += 1
            warnings.append(
                u"{0} has no primary {1} connector - skipped.".format(
                    repr(fixture), system_classification))
            continue
        targets.append((connector.ref, connector.position, connector.diameter_mm))

    if not targets:
        return Result.fail(
            u"No fixtures could be routed - {0} skipped.".format(skipped),
            diagnostics=warnings)

    graph = build_routing_graph(
        corridor_points, targets, wall_penetration_mm=wall_penetration_mm,
        max_branch_length_mm=max_branch_length_mm)
    warnings.extend(graph.warnings)

    return Result.ok(
        value={"graph": graph, "routed": len(targets), "skipped": skipped, "warnings": warnings},
        message=u"{0} fixture(s) added to the routing graph.{1}".format(
            len(targets), u" ({0} skipped)".format(skipped) if skipped else u""))
