# -*- coding: utf-8 -*-
"""Sanitary Drainage generation (ADR-0004 / MEP_SAD.md). Zero Autodesk.Revit
imports - unit-testable with fakes, same pattern as every other app command.
Transaction ownership stays with the caller's flow module, per SAD Sec 4.4.

Known simplification, disclosed rather than silently built around: each
fixture gets its OWN direct segment to the shared target_point - there is no
branch/wye merge geometry yet. MEP_SAD.md Sec 5 originally scoped branch
merging as in-scope for slice 1; building it turned out to need real fixture
connector positions to do safely (exactly the kind of geometry heuristic this
suite's history warns against inventing without live data - see the
wall_run_planner and collision-avoidance lessons in
docs/architecture/PHASE_1_PLAN.md / ROADMAP.md). Deferred until the
ConnectorManager live-testing spike happens and real positions are available
to build and verify a merge against.
"""

from bkbim.core.logging import get_logger
from bkbim.core.result import Result
from bkbim.domain.mep.models.system_classification import SANITARY
from bkbim.domain.mep.routing.path_planner import RoutingRequest, SlopeStrategy, plan_direct_route
from bkbim.domain.mep.sanitary.discharge_sizing import total_discharge_units, size_pipe_for_discharge_units
from bkbim.domain.mep.validation.sanitary_validation import validate_fixtures, validate_routing_plans

_logger = get_logger(u"bkbim.app.generate_sanitary_drainage")


def run(fixtures, target_point, standard, usage_type, pipe_writer):
    """fixtures: list[FixtureInfo], all routed to one shared target_point (a
    stack/riser connection point already resolved by the caller via
    IExistingSystemReader - this command stays Revit-free and never resolves
    it itself).
    target_point: (x, y, z) tuple.
    standard: Standard profile carrying the mep_* fields.
    usage_type: a key into standard.mep_frequency_factor_by_usage
        (e.g. u"intermittent").
    pipe_writer: IPipeWriter port.

    :rtype: Result wrapping {"routed": int, "skipped": int,
        "total_discharge_units": float, "recommended_downstream_dn_mm": int or None,
        "warnings": list[str]}
    """
    fixture_warnings = validate_fixtures(fixtures, standard)
    total_du, unresolved = total_discharge_units(fixtures, standard)
    recommended_dn = None if unresolved else size_pipe_for_discharge_units(total_du, standard)

    slope_strategy = SlopeStrategy(standard)
    plans = []
    skipped = 0
    for fixture in fixtures:
        connector = fixture.primary_connector(SANITARY)
        if connector is None:
            skipped += 1
            continue
        request = RoutingRequest(
            fixture=fixture,
            start_point=connector.position,
            target_point=target_point,
            diameter_mm=connector.diameter_mm,
            material=standard.mep_default_pipe_material,
            slope_strategy=slope_strategy,
            start_connector_ref=connector.ref)
        plans.append(plan_direct_route(request))

    all_warnings = fixture_warnings + validate_routing_plans(plans)

    if not plans:
        return Result.fail(
            u"No fixtures could be routed - {0} skipped.".format(skipped),
            diagnostics=all_warnings)

    routed = 0
    write_failures = 0
    for plan in plans:
        try:
            write_result = pipe_writer.write(plan)
            ok = write_result.success if hasattr(write_result, "success") else bool(write_result)
        except Exception as e:
            _logger.warning(u"Pipe write failed: {0}", str(e))
            ok = False
        if ok:
            routed += 1
        else:
            write_failures += 1

    total_skipped = skipped + write_failures
    _logger.info(u"Sanitary Drainage: {0} routed, {1} skipped", routed, total_skipped)

    value = {
        "routed": routed,
        "skipped": total_skipped,
        "total_discharge_units": total_du,
        "recommended_downstream_dn_mm": recommended_dn,
        "warnings": all_warnings,
    }

    if routed == 0:
        return Result.fail(u"No pipes could be created - {0} skipped.".format(total_skipped),
                            diagnostics=all_warnings)

    return Result.ok(
        value=value,
        message=u"{0} fixture(s) routed.{1}".format(
            routed, u" ({0} skipped)".format(total_skipped) if total_skipped else u""))
