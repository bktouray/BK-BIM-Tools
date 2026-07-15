# -*- coding: utf-8 -*-
from bkbim.app.commands.generate_sanitary_drainage_command import run
from bkbim.core.result import Result
from bkbim.domain.mep.models.connector_info import ConnectorInfo
from bkbim.domain.mep.models.fixture_info import FixtureInfo
from bkbim.domain.mep.models.system_classification import SANITARY
from bkbim.domain.standards.standard import default_standard

_TARGET = (5000, 0, -500)


class _FakePipeWriter(object):
    def __init__(self, should_succeed=True):
        self.should_succeed = should_succeed
        self.written = []

    def write(self, plan):
        self.written.append(plan)
        return Result.ok() if self.should_succeed else Result.fail(u"boom")


def _wc(ref=u"wc-1", x=0):
    connector = ConnectorInfo(position=(x, 0, 0), direction=(0, 0, -1),
                               diameter_mm=100, system_classification=SANITARY)
    return FixtureInfo(ref=ref, family_name=u"WC Family", type_name=u"Standard",
                        connectors=[connector], fixture_type_key=u"WC")


def test_routes_every_fixture_and_reports_recommended_downstream_size():
    writer = _FakePipeWriter()
    std = default_standard()

    result = run([_wc(u"wc-1"), _wc(u"wc-2", x=1000)], _TARGET, std, u"intermittent", writer)

    assert result.success
    assert result.value["routed"] == 2
    assert result.value["skipped"] == 0
    assert result.value["total_discharge_units"] == 4.0
    assert result.value["recommended_downstream_dn_mm"] == 75
    assert len(writer.written) == 2


def test_each_fixture_gets_its_own_direct_segment_no_merge():
    writer = _FakePipeWriter()
    std = default_standard()

    run([_wc(u"wc-1"), _wc(u"wc-2", x=1000)], _TARGET, std, u"intermittent", writer)

    # Known slice-1 simplification: two fixtures produce two independently
    # written plans, each a single direct segment - no shared branch fitting.
    assert len(writer.written) == 2
    for plan in writer.written:
        assert len(plan.segments) == 1
        assert plan.segments[0].end_point == _TARGET


def test_fixture_with_no_sanitary_connector_is_skipped_not_crashed():
    fixture = FixtureInfo(ref=u"broken", family_name=u"Weird", type_name=u"A",
                           connectors=[], fixture_type_key=u"WC")
    writer = _FakePipeWriter()
    std = default_standard()

    result = run([_wc(u"wc-1"), fixture], _TARGET, std, u"intermittent", writer)

    assert result.success
    assert result.value["routed"] == 1
    assert result.value["skipped"] == 1


def test_no_routable_fixtures_fails_cleanly():
    fixture = FixtureInfo(ref=u"broken", family_name=u"Weird", type_name=u"A",
                           connectors=[], fixture_type_key=u"WC")
    writer = _FakePipeWriter()
    std = default_standard()

    result = run([fixture], _TARGET, std, u"intermittent", writer)

    assert not result.success
    assert writer.written == []


def test_pipe_writer_failure_counts_as_skipped_not_a_crash():
    writer = _FakePipeWriter(should_succeed=False)
    std = default_standard()

    result = run([_wc(u"wc-1")], _TARGET, std, u"intermittent", writer)

    assert not result.success
    assert result.value is None


def test_unresolved_fixture_type_suppresses_the_recommended_size_but_still_routes():
    unmapped = FixtureInfo(
        ref=u"mystery", family_name=u"Mystery Family", type_name=u"A",
        connectors=[ConnectorInfo(position=(0, 0, 0), direction=(0, 0, -1),
                                   diameter_mm=100, system_classification=SANITARY)],
        fixture_type_key=None)
    writer = _FakePipeWriter()
    std = default_standard()

    result = run([unmapped], _TARGET, std, u"intermittent", writer)

    assert result.success
    assert result.value["routed"] == 1
    assert result.value["recommended_downstream_dn_mm"] is None
    assert any(u"discharge-unit data" in w for w in result.value["warnings"])
