# -*- coding: utf-8 -*-
"""DWV collector graph command.

This is the app-layer entry point for the resumed Sanitary/DWV work. It stays
Revit-free like the existing command modules: read fixtures in an adapter,
pass plain domain objects here, receive a pure collector graph back. Revit
pipe creation/fittings are deliberately later slices.
"""

from bkbim.core.result import Result
from bkbim.domain.mep.models.connector_info import ConnectorInfo
from bkbim.domain.mep.models.system_classification import SANITARY
from bkbim.domain.mep.sanitary.discharge_sizing import (
    size_pipe_for_discharge_units, total_discharge_units,
)
from bkbim.domain.mep.sanitary.dwv_collector_graph import (
    build_bathroom_dwv_backbone_graph, build_dwv_collector_graph,
    dwv_routing_plan_from_graph,
)
from bkbim.domain.mep.validation.sanitary_validation import validate_fixtures


def _fixture_label(fixture):
    return u"{0} : {1} [id {2}]".format(
        fixture.family_name or u"Unnamed Family",
        fixture.type_name or u"Unnamed Type",
        fixture.ref)


def _is_wc_fixture(fixture, connector):
    key = (fixture.fixture_type_key or u"").lower()
    family = (fixture.family_name or u"").lower()
    type_name = (fixture.type_name or u"").lower()
    if key == u"wc":
        return True
    if u"toilet" in family or u"toilet" in type_name:
        return True
    if u"wc" in family or u"wc" in type_name:
        return True
    return connector.diameter_mm >= 100


def _targets_from_fixtures(fixtures, warnings):
    allowed_flows = (
        ConnectorInfo.FLOW_OUT,
        ConnectorInfo.FLOW_BIDIRECTIONAL,
    )
    targets = []
    target_fixtures = []
    skipped = 0
    for fixture in fixtures:
        connectors = fixture.matching_connectors(
            SANITARY, allowed_flow_directions=allowed_flows)
        if not connectors:
            skipped += 1
            warnings.append(
                u"{0} has no sanitary drain outlet connector - skipped.".format(
                    repr(fixture)))
            continue
        if len(connectors) > 1:
            skipped += 1
            warnings.append(
                u"{0} has {1} possible sanitary drain outlet connectors - "
                u"skipped because the routing target is ambiguous.".format(
                    repr(fixture), len(connectors)))
            continue

        connector = connectors[0]
        targets.append((
            connector.ref,
            connector.position,
            connector.diameter_mm,
            _fixture_label(fixture)))
        target_fixtures.append((fixture, connector, targets[-1]))
    return targets, target_fixtures, skipped


def run(fixtures, corridor_points, stack_point, standard, usage_type,
        collector_diameter_mm, slope_percent, max_branch_length_mm=None):
    """Builds the next DWV graph without creating any Revit geometry.

    fixtures: list[FixtureInfo] selected by the adapter/UI.
    corridor_points: wall-derived collector corridor in mm.
    stack_point: downstream stack/riser point in mm.
    standard/usage_type: current office standard inputs, used for fixture
        validation, DU summary and slope checks.
    collector_diameter_mm: explicit collector size for this first slice.
    slope_percent: positive fall toward the stack.

    :rtype: Result wrapping {"graph": DwvCollectorGraph, "pipe_plan":
        RoutingPlan, "routed": int,
        "skipped": int, "warnings": list[str], "total_discharge_units": float,
        "recommended_downstream_dn_mm": int or None}
    """
    warnings = validate_fixtures(fixtures, standard)
    total_du, unresolved = total_discharge_units(fixtures, standard)
    recommended_dn = None if unresolved else size_pipe_for_discharge_units(
        total_du, standard)

    targets, _target_fixtures, skipped = _targets_from_fixtures(
        fixtures, warnings)

    if not targets:
        return Result.fail(
            u"No DWV fixtures could be routed - {0} skipped.".format(skipped),
            diagnostics=warnings)

    try:
        graph = build_dwv_collector_graph(
            corridor_points=corridor_points,
            stack_point=stack_point,
            targets=targets,
            collector_diameter_mm=collector_diameter_mm,
            slope_percent=slope_percent,
            standard=standard,
            max_branch_length_mm=max_branch_length_mm)
    except ValueError as error:
        return Result.fail(str(error), diagnostics=warnings)

    warnings.extend(graph.warnings)
    pipe_plan = dwv_routing_plan_from_graph(
        graph, material=standard.mep_default_pipe_material)

    return Result.ok(
        value={
            "graph": graph,
            "pipe_plan": pipe_plan,
            "routed": len(targets),
            "skipped": skipped,
            "warnings": warnings,
            "total_discharge_units": total_du,
            "recommended_downstream_dn_mm": recommended_dn,
        },
        message=u"{0} fixture(s) added to the DWV collector graph.{1}".format(
            len(targets), u" ({0} skipped)".format(skipped) if skipped else u""))


def run_bathroom_wc_backbone(fixtures, stack_point, standard, usage_type,
                             collector_diameter_mm, slope_percent,
                             max_branch_length_mm=None, route_preference=None,
                             wc_drop_z_mm=None):
    """Builds the preferred bathroom DWV topology.

    Exactly one selected/routable WC becomes the primary DN110-ish backbone
    from toilet to stack. Other selected fixtures branch into that backbone.
    """
    warnings = validate_fixtures(fixtures, standard)
    total_du, unresolved = total_discharge_units(fixtures, standard)
    recommended_dn = None if unresolved else size_pipe_for_discharge_units(
        total_du, standard)

    targets, target_fixtures, skipped = _targets_from_fixtures(fixtures, warnings)
    if not targets:
        return Result.fail(
            u"No DWV fixtures could be routed - {0} skipped.".format(skipped),
            diagnostics=warnings)

    wc_candidates = [
        item for item in target_fixtures
        if _is_wc_fixture(item[0], item[1])
    ]
    if len(wc_candidates) != 1:
        return Result.fail(
            u"Select exactly one WC/toilet fixture for this DWV bathroom "
            u"slice. Found {0} possible WC fixtures.".format(len(wc_candidates)),
            diagnostics=warnings)

    wc_fixture, _wc_connector, wc_target = wc_candidates[0]
    branch_targets = [
        target for fixture, _connector, target in target_fixtures
        if fixture is not wc_fixture
    ]

    try:
        graph = build_bathroom_dwv_backbone_graph(
            wc_target=wc_target,
            stack_point=stack_point,
            branch_targets=branch_targets,
            collector_diameter_mm=collector_diameter_mm,
            slope_percent=slope_percent,
            standard=standard,
            max_branch_length_mm=max_branch_length_mm,
            route_preference=route_preference,
            wc_drop_z_mm=wc_drop_z_mm)
    except ValueError as error:
        return Result.fail(str(error), diagnostics=warnings)

    warnings.extend(graph.warnings)
    pipe_plan = dwv_routing_plan_from_graph(
        graph, material=standard.mep_default_pipe_material)

    return Result.ok(
        value={
            "graph": graph,
            "pipe_plan": pipe_plan,
            "routed": len(targets),
            "skipped": skipped,
            "warnings": warnings,
            "total_discharge_units": total_du,
            "recommended_downstream_dn_mm": recommended_dn,
            "primary_fixture_ref": wc_fixture.ref,
        },
        message=u"{0} fixture(s) added to the WC-backbone DWV graph.{1}".format(
            len(targets), u" ({0} skipped)".format(skipped) if skipped else u""))
