# -*- coding: utf-8 -*-
from bkbim.app.commands.generate_water_supply_command import run
from bkbim.domain.mep.models.connector_info import ConnectorInfo
from bkbim.domain.mep.models.fixture_info import FixtureInfo

_COLD_WATER = u"DomesticColdWater"
_HOT_WATER = u"DomesticHotWater"
_CORRIDOR_POINTS = [(0, 0, 200), (0, 3000, 200)]


def _basin(ref=u"basin-1", x=100, y=1000, z=200, conn_ref=None):
    connector = ConnectorInfo(position=(x, y, z), direction=(0, 0, 1),
                               diameter_mm=15, system_classification=_COLD_WATER,
                               flow_direction=ConnectorInfo.FLOW_IN,
                               ref=conn_ref or (u"conn-" + ref))
    return FixtureInfo(ref=ref, family_name=u"Basin Family", type_name=u"Standard",
                        connectors=[connector])


def _hot_basin(ref=u"hot-basin-1", x=100, y=1000, z=200, conn_ref=None):
    connector = ConnectorInfo(position=(x, y, z), direction=(0, 0, 1),
                               diameter_mm=15, system_classification=_HOT_WATER,
                               flow_direction=ConnectorInfo.FLOW_IN,
                               ref=conn_ref or (u"conn-" + ref))
    return FixtureInfo(ref=ref, family_name=u"Basin Family", type_name=u"Standard",
                       connectors=[connector])


def test_builds_a_routing_graph_from_every_matching_fixture():
    result = run([_basin(u"b1"), _basin(u"b2", y=2000)], _COLD_WATER,
                 _CORRIDOR_POINTS, wall_penetration_mm=80)

    assert result.success
    assert result.value["routed"] == 2
    assert result.value["skipped"] == 0
    graph = result.value["graph"]
    assert len(graph.junctions) == 2


def test_builds_a_hot_water_routing_graph_from_hot_connectors():
    result = run([_hot_basin(u"h1"), _hot_basin(u"h2", y=2000)], _HOT_WATER,
                 _CORRIDOR_POINTS, wall_penetration_mm=80)

    assert result.success
    assert result.value["routed"] == 2
    assert len(result.value["graph"].junctions) == 2


def test_fixture_with_no_matching_connector_is_skipped_not_crashed():
    hot_only = FixtureInfo(
        ref=u"weird", family_name=u"Weird", type_name=u"A",
        connectors=[ConnectorInfo(position=(0, 0, 0), direction=(0, 0, 1),
                                   diameter_mm=15, system_classification=u"DomesticHotWater")])

    result = run([_basin(u"b1"), hot_only], _COLD_WATER, _CORRIDOR_POINTS, wall_penetration_mm=80)

    assert result.success
    assert result.value["routed"] == 1
    assert result.value["skipped"] == 1


def test_no_routable_fixtures_fails_cleanly():
    hot_only = FixtureInfo(
        ref=u"weird", family_name=u"Weird", type_name=u"A",
        connectors=[ConnectorInfo(position=(0, 0, 0), direction=(0, 0, 1),
                                   diameter_mm=15, system_classification=u"DomesticHotWater")])

    result = run([hot_only], _COLD_WATER, _CORRIDOR_POINTS, wall_penetration_mm=80)

    assert not result.success


def test_graph_warnings_are_surfaced_in_the_result():
    far_basin = _basin(u"far", x=5000, y=1000)  # real distance >> wall_penetration_mm

    result = run([far_basin], _COLD_WATER, _CORRIDOR_POINTS, wall_penetration_mm=80)

    assert result.success
    assert any(u"far" in w and u"differs substantially" in w for w in result.value["warnings"])


def test_graph_warnings_identify_the_fixture_not_its_connector_ref():
    result = run(
        [_basin(u"far", x=5000, y=1000, conn_ref=u"opaque-connector")],
        _COLD_WATER, _CORRIDOR_POINTS, wall_penetration_mm=80)

    assert result.success
    assert any(u"Basin Family : Standard [id far]" in w
               for w in result.value["warnings"])
    assert not any(u"opaque-connector" in w for w in result.value["warnings"])


def test_connector_ref_is_preserved_as_the_graphs_target_ref():
    result = run([_basin(u"b1", conn_ref=u"real-connector-object")], _COLD_WATER,
                 _CORRIDOR_POINTS, wall_penetration_mm=80)

    graph = result.value["graph"]
    _junction, branch = graph.junctions[0]
    assert branch.target_ref == u"real-connector-object"


def test_ambiguous_matching_connectors_are_skipped_with_a_warning():
    fixture = _basin(u"ambiguous")
    fixture.connectors.append(ConnectorInfo(
        position=(100, 1000, 250), direction=(0, 0, 1),
        diameter_mm=15, system_classification=_COLD_WATER,
        flow_direction=ConnectorInfo.FLOW_BIDIRECTIONAL,
        ref=u"second-connector"))

    result = run(
        [fixture], _COLD_WATER, _CORRIDOR_POINTS, wall_penetration_mm=80)

    assert not result.success
    assert any(u"ambiguous" in warning.lower() for warning in result.diagnostics)


def test_fixtures_at_the_same_trunk_tap_fail_before_revit_geometry():
    result = run(
        [_basin(u"b1", x=100, y=1000),
         _basin(u"b2", x=200, y=1000)],
        _COLD_WATER, _CORRIDOR_POINTS, wall_penetration_mm=80)

    assert not result.success
    assert u"same trunk tap" in result.message
