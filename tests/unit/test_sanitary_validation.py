# -*- coding: utf-8 -*-
from bkbim.domain.mep.models.connector_info import ConnectorInfo
from bkbim.domain.mep.models.fixture_info import FixtureInfo
from bkbim.domain.mep.models.routing_plan import RoutingPlan
from bkbim.domain.mep.models.system_classification import SANITARY, VENT
from bkbim.domain.mep.validation.sanitary_validation import (
    validate_fixtures, validate_routing_plans)
from bkbim.domain.standards.standard import default_standard


def _sanitary_connector():
    return ConnectorInfo(position=(0, 0, 0), direction=(0, 0, -1),
                          diameter_mm=100, system_classification=SANITARY)


def test_fixture_with_no_connectors_warns():
    fixture = FixtureInfo(ref=u"f1", family_name=u"WC Family", type_name=u"Standard",
                           connectors=[], fixture_type_key=u"WC")
    warnings = validate_fixtures([fixture], default_standard())
    assert any(u"no connectors" in w for w in warnings)


def test_fixture_missing_primary_sanitary_connector_warns():
    vent_only = ConnectorInfo(position=(0, 0, 0), direction=(0, 0, 1),
                               diameter_mm=50, system_classification=VENT)
    fixture = FixtureInfo(ref=u"f1", family_name=u"WC Family", type_name=u"Standard",
                           connectors=[vent_only], fixture_type_key=u"WC")
    warnings = validate_fixtures([fixture], default_standard())
    assert any(u"no primary Sanitary connector" in w for w in warnings)


def test_mislabeled_inlet_connector_is_not_treated_as_a_sanitary_outlet():
    """Regression test for a real family bug found live 2026-07-10: a Roca
    shower column's water-supply connectors were both labelled
    system_classification=SANITARY but correctly recorded as FLOW_IN. An
    inlet must never be picked as the drain outlet just because the family
    mislabels its system.
    """
    mislabeled_inlet = ConnectorInfo(
        position=(0, 0, 1100), direction=(0, 0, 1), diameter_mm=25,
        system_classification=SANITARY, flow_direction=ConnectorInfo.FLOW_IN)
    fixture = FixtureInfo(ref=u"f1", family_name=u"Shower Column", type_name=u"Standard",
                           connectors=[mislabeled_inlet], fixture_type_key=u"Shower")
    warnings = validate_fixtures([fixture], default_standard())
    assert any(u"no primary Sanitary connector" in w for w in warnings)


def test_fixture_with_unmapped_fixture_type_key_warns():
    fixture = FixtureInfo(ref=u"f1", family_name=u"Weird Family", type_name=u"Type A",
                           connectors=[_sanitary_connector()], fixture_type_key=None)
    warnings = validate_fixtures([fixture], default_standard())
    assert any(u"discharge-unit data" in w for w in warnings)


def test_fully_valid_fixture_has_no_warnings():
    fixture = FixtureInfo(ref=u"f1", family_name=u"WC Family", type_name=u"Standard",
                           connectors=[_sanitary_connector()], fixture_type_key=u"WC")
    assert validate_fixtures([fixture], default_standard()) == []


def test_validate_routing_plans_flattens_every_plans_warnings():
    plan_a = RoutingPlan(warnings=[u"warning A"])
    plan_b = RoutingPlan(warnings=[u"warning B1", u"warning B2"])
    assert validate_routing_plans([plan_a, plan_b]) == [u"warning A", u"warning B1", u"warning B2"]
