# -*- coding: utf-8 -*-
from bkbim.domain.mep.sanitary.discharge_sizing import (
    discharge_units_for_fixture, total_discharge_units, frequency_factor,
    design_flow_rate_ls, size_pipe_for_discharge_units)
from bkbim.domain.standards.standard import default_standard


class _FakeFixture(object):
    def __init__(self, fixture_type_key):
        self.fixture_type_key = fixture_type_key

    def __repr__(self):
        return u"<FakeFixture {0}>".format(self.fixture_type_key)


def test_discharge_units_resolved_for_known_fixture_type():
    std = default_standard()
    assert discharge_units_for_fixture(_FakeFixture(u"WC"), std) == 2.0


def test_discharge_units_none_for_unknown_fixture_type():
    std = default_standard()
    assert discharge_units_for_fixture(_FakeFixture(u"UnknownThing"), std) is None


def test_discharge_units_none_when_no_fixture_type_key():
    std = default_standard()
    assert discharge_units_for_fixture(_FakeFixture(None), std) is None


def test_total_discharge_units_sums_resolvable_and_flags_the_rest():
    std = default_standard()
    fixtures = [_FakeFixture(u"WC"), _FakeFixture(u"WashBasin"), _FakeFixture(u"Mystery")]

    total, unresolved = total_discharge_units(fixtures, std)

    assert total == 2.5  # 2.0 (WC) + 0.5 (WashBasin)
    assert len(unresolved) == 1
    assert unresolved[0].fixture_type_key == u"Mystery"


def test_frequency_factor_known_and_unknown():
    std = default_standard()
    assert frequency_factor(u"intermittent", std) == 0.5
    assert frequency_factor(u"nonsense", std) is None


def test_design_flow_rate_uses_k_sqrt_sum_du():
    std = default_standard()
    # K=0.5, total_du=4 -> 0.5 * sqrt(4) = 1.0
    assert design_flow_rate_ls(4.0, u"intermittent", std) == 1.0


def test_design_flow_rate_none_for_unknown_usage():
    std = default_standard()
    assert design_flow_rate_ls(4.0, u"nonsense", std) is None


def test_size_pipe_picks_smallest_dn_that_fits():
    std = default_standard()
    assert size_pipe_for_discharge_units(0.5, std) == 50
    assert size_pipe_for_discharge_units(2.0, std) == 75
    assert size_pipe_for_discharge_units(8.0, std) == 100


def test_size_pipe_none_when_it_exceeds_every_band():
    std = default_standard()
    assert size_pipe_for_discharge_units(999.0, std) is None
