# -*- coding: utf-8 -*-
"""BS EN 12056-2 discharge-unit sizing (MEP_SAD.md Sec 4).

Qww = K * sqrt(sum(discharge units)) - the standard's own design-flow
quantity, kept here for reporting/traceability even though pipe SELECTION
below uses a simpler DU-indexed capacity table (Standard.mep_pipe_capacity_table_du)
rather than deriving DN from Qww directly. See standard.py's mep_* fields for
why: correct calculation shape, placeholder numbers pending verification.
"""
import math


def discharge_units_for_fixture(fixture, standard):
    """None if the fixture has no fixture_type_key, or the key isn't in the
    Standard's table - callers must treat None as "cannot size", not zero.
    """
    if not fixture.fixture_type_key:
        return None
    return standard.mep_discharge_units_by_fixture_type.get(fixture.fixture_type_key)


def total_discharge_units(fixtures, standard):
    """Returns (total_du, unresolved_fixtures) - unresolved_fixtures is every
    fixture whose discharge units could not be resolved; total_du only sums
    the resolvable ones. Callers (sanitary_validation) turn unresolved
    fixtures into user-visible warnings rather than silently zero-rating them.
    """
    total = 0.0
    unresolved = []
    for fixture in fixtures:
        du = discharge_units_for_fixture(fixture, standard)
        if du is None:
            unresolved.append(fixture)
        else:
            total += du
    return total, unresolved


def frequency_factor(usage_type, standard):
    return standard.mep_frequency_factor_by_usage.get(usage_type)


def design_flow_rate_ls(total_du, usage_type, standard):
    """Qww in L/s, or None if usage_type isn't a recognised key."""
    k = frequency_factor(usage_type, standard)
    if k is None:
        return None
    return k * math.sqrt(total_du)


def size_pipe_for_discharge_units(total_du, standard):
    """Smallest DN (mm) whose capacity table entry covers total_du, or None
    if it exceeds every entry (a real "this run needs engineering judgement,
    not an auto-pick" case - never silently returns the largest DN as a guess).
    """
    for dn_mm, max_du in sorted(standard.mep_pipe_capacity_table_du, key=lambda t: t[0]):
        if total_du <= max_du:
            return dn_mm
    return None
