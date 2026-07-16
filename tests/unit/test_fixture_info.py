# -*- coding: utf-8 -*-
from bkbim.domain.mep.models.connector_info import ConnectorInfo
from bkbim.domain.mep.models.fixture_info import FixtureInfo
from bkbim.domain.mep.models.system_classification import SANITARY


_COLD_WATER = u"DomesticColdWater"


def _fixture(connectors):
    return FixtureInfo(
        ref=u"fixture-1", family_name=u"Fixture", type_name=u"Type A",
        connectors=connectors)


def test_default_primary_connector_keeps_sanitary_outlet_semantics():
    inlet = ConnectorInfo(
        position=(0, 0, 0), direction=(0, 0, 1), diameter_mm=20,
        system_classification=SANITARY, flow_direction=ConnectorInfo.FLOW_IN)
    outlet = ConnectorInfo(
        position=(0, 0, 0), direction=(0, 0, -1), diameter_mm=100,
        system_classification=SANITARY, flow_direction=ConnectorInfo.FLOW_OUT)

    assert _fixture([inlet, outlet]).primary_connector(SANITARY) is outlet


def test_water_supply_can_select_an_inlet_connector_explicitly():
    inlet = ConnectorInfo(
        position=(0, 0, 500), direction=(0, 0, 1), diameter_mm=15,
        system_classification=_COLD_WATER, flow_direction=ConnectorInfo.FLOW_IN)

    selected = _fixture([inlet]).primary_connector(
        _COLD_WATER,
        allowed_flow_directions=(
            ConnectorInfo.FLOW_IN, ConnectorInfo.FLOW_BIDIRECTIONAL))

    assert selected is inlet


def test_matching_connectors_surfaces_ambiguous_water_connectors():
    connector_a = ConnectorInfo(
        position=(0, 0, 500), direction=(0, 0, 1), diameter_mm=15,
        system_classification=_COLD_WATER, flow_direction=ConnectorInfo.FLOW_IN)
    connector_b = ConnectorInfo(
        position=(0, 0, 600), direction=(0, 0, 1), diameter_mm=15,
        system_classification=_COLD_WATER,
        flow_direction=ConnectorInfo.FLOW_BIDIRECTIONAL)

    matches = _fixture([connector_a, connector_b]).matching_connectors(
        _COLD_WATER,
        allowed_flow_directions=(
            ConnectorInfo.FLOW_IN, ConnectorInfo.FLOW_BIDIRECTIONAL))

    assert matches == [connector_a, connector_b]
