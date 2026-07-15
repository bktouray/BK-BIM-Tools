# -*- coding: utf-8 -*-
from bkbim.domain.mep.sanitary.slope_rules import min_slope_percent_for_dn, check_slope
from bkbim.domain.standards.standard import default_standard, Standard


def test_min_slope_picks_the_smallest_covering_band():
    std = default_standard()
    assert min_slope_percent_for_dn(50, std) == 2.5   # covered by the 75mm band
    assert min_slope_percent_for_dn(75, std) == 2.5
    assert min_slope_percent_for_dn(100, std) == 1.25
    assert min_slope_percent_for_dn(150, std) == 1.0


def test_min_slope_none_when_dn_exceeds_every_band():
    std = default_standard()
    assert min_slope_percent_for_dn(300, std) is None


def test_check_slope_ok_produces_no_warnings():
    std = default_standard()
    assert check_slope(2.0, 100, std) == []


def test_check_slope_below_minimum_warns():
    std = default_standard()
    warnings = check_slope(0.5, 100, std)
    assert len(warnings) == 1
    assert u"below" in warnings[0]


def test_check_slope_above_configured_maximum_warns():
    std = Standard(name=u"Capped", mep_max_slope_percent=5.0)
    warnings = check_slope(8.0, 100, std)
    assert any(u"exceeds" in w for w in warnings)


def test_check_slope_no_maximum_configured_never_warns_on_steepness():
    std = default_standard()
    assert check_slope(50.0, 100, std) == []


def test_check_slope_missing_band_data_warns():
    std = default_standard()
    warnings = check_slope(1.0, 300, std)
    assert any(u"No minimum-slope data" in w for w in warnings)
