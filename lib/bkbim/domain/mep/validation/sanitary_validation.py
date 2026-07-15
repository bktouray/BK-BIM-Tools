# -*- coding: utf-8 -*-
"""Pre-generation validation for Sanitary Drainage (MEP_SAD.md Sec 7). Returns
plain warning strings, same shape as slope_rules.check_slope and the rest of
this package - the app command wraps these into a Result, this module never
raises or aborts on its own.
"""
from bkbim.domain.mep.models.system_classification import SANITARY
from bkbim.domain.mep.sanitary.discharge_sizing import discharge_units_for_fixture


def validate_fixtures(fixtures, standard):
    """One warning per problem found; does not stop at the first one, so a
    single run surfaces every fixable issue instead of one-at-a-time.
    """
    warnings = []
    for fixture in fixtures:
        if not fixture.connectors:
            warnings.append(
                u"{0} has no connectors - cannot route.".format(repr(fixture)))
            continue

        if fixture.primary_connector(SANITARY) is None:
            warnings.append(
                u"{0} has no primary Sanitary connector.".format(repr(fixture)))

        if discharge_units_for_fixture(fixture, standard) is None:
            warnings.append(
                u"{0} has no discharge-unit data for fixture_type_key={1!r} - "
                u"add a mapping before generating.".format(
                    repr(fixture), fixture.fixture_type_key))

    return warnings


def validate_routing_plans(routing_plans):
    """Flattens every RoutingPlan's own warnings into one list - the plans
    themselves already carry slope/direction warnings from path_planner.
    """
    warnings = []
    for plan in routing_plans:
        warnings.extend(plan.warnings)
    return warnings
