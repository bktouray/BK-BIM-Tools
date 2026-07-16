# -*- coding: utf-8 -*-
"""Covers the MEP fields added to Standard for Sanitary Drainage (ADR-0004) -
defaults exist, are independent per instance, and are overridable, same
guarantees test_standard.py already covers for the dimensioning fields.
"""
from bkbim.domain.standards.standard import Standard, default_standard


def test_default_standard_has_mep_defaults():
    std = default_standard()
    assert std.mep_frequency_factor_by_usage[u"intermittent"] == 0.5
    assert std.mep_discharge_units_by_fixture_type[u"WC"] == 2.0
    assert std.mep_default_pipe_material == u"uPVC"
    assert std.mep_default_pipe_type_name is None
    assert std.mep_max_slope_percent is None


def test_mep_fields_are_overridable():
    std = Standard(name=u"Custom", mep_default_pipe_material=u"Cast Iron",
                    mep_max_slope_percent=10.0)
    assert std.mep_default_pipe_material == u"Cast Iron"
    assert std.mep_max_slope_percent == 10.0


def test_mep_dicts_are_independent_per_instance():
    a = Standard(name=u"A")
    b = Standard(name=u"B", mep_discharge_units_by_fixture_type={u"WC": 3.5})
    assert a.mep_discharge_units_by_fixture_type[u"WC"] == 2.0
    assert b.mep_discharge_units_by_fixture_type[u"WC"] == 3.5


def test_pipe_capacity_table_defaults_ascend_by_dn():
    std = default_standard()
    dns = [row[0] for row in std.mep_pipe_capacity_table_du]
    assert dns == sorted(dns)


def test_default_valve_height_matches_office_convention():
    std = default_standard()
    assert std.mep_valve_height_mm == 1800.0


def test_default_wall_penetration_matches_office_convention():
    std = default_standard()
    assert std.mep_wall_penetration_mm == 80.0
    assert std.mep_max_branch_length_mm is None


def test_default_hot_cold_spacing_matches_office_convention():
    std = default_standard()
    assert std.mep_hot_cold_spacing_mm == 50.0
