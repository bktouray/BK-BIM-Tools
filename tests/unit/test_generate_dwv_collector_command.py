# -*- coding: utf-8 -*-
from bkbim.app.commands.generate_dwv_collector_command import (
    run, run_bathroom_wc_backbone,
)
from bkbim.domain.mep.models.connector_info import ConnectorInfo
from bkbim.domain.mep.models.fixture_info import FixtureInfo
from bkbim.domain.mep.models.system_classification import SANITARY
from bkbim.domain.standards.standard import default_standard


def _fixture(ref=u"wc-1", y=1000, z=500, dn=100, fixture_type_key=u"WC",
             connectors=None, family_name=None):
    if connectors is None:
        connectors = [
            ConnectorInfo(
                position=(100, y, z),
                direction=(0, 0, -1),
                diameter_mm=dn,
                system_classification=SANITARY,
                flow_direction=ConnectorInfo.FLOW_OUT,
                ref=u"{0}-connector".format(ref))
        ]
    return FixtureInfo(
        ref=ref,
        family_name=family_name or (
            u"WC Family" if fixture_type_key == u"WC" else u"Fixture Family"),
        type_name=u"Standard",
        connectors=connectors,
        fixture_type_key=fixture_type_key)


def test_command_builds_dwv_collector_graph_and_du_summary():
    result = run(
        fixtures=[_fixture(u"wc-1", y=1000), _fixture(u"wc-2", y=2500)],
        corridor_points=[(0, 0, 0), (0, 3000, 0)],
        stack_point=(0, 0, 0),
        standard=default_standard(),
        usage_type=u"intermittent",
        collector_diameter_mm=100,
        slope_percent=2.0)

    assert result.success
    assert result.value["routed"] == 2
    assert result.value["skipped"] == 0
    assert result.value["total_discharge_units"] == 4.0
    assert result.value["recommended_downstream_dn_mm"] == 75
    graph = result.value["graph"]
    assert graph.downstream_end == (0, 0, 0.0)
    assert len(graph.junctions) == 2
    pipe_plan = result.value["pipe_plan"]
    assert len(pipe_plan.segments) == 3  # one collector, two branches
    assert pipe_plan.fittings == []
    assert pipe_plan.segments[0].diameter_mm == 100
    assert pipe_plan.segments[0].slope_percent == 2.0


def test_command_skips_fixture_with_no_sanitary_outlet_connector():
    fixture = _fixture(
        ref=u"bad",
        connectors=[
            ConnectorInfo(
                position=(100, 1000, 500),
                direction=(0, 0, -1),
                diameter_mm=100,
                system_classification=SANITARY,
                flow_direction=ConnectorInfo.FLOW_IN)
        ])

    result = run(
        fixtures=[_fixture(u"wc-1", y=1000), fixture],
        corridor_points=[(0, 0, 0), (0, 3000, 0)],
        stack_point=(0, 0, 0),
        standard=default_standard(),
        usage_type=u"intermittent",
        collector_diameter_mm=100,
        slope_percent=2.0)

    assert result.success
    assert result.value["routed"] == 1
    assert result.value["skipped"] == 1
    assert any(u"no sanitary drain outlet" in w for w in result.value["warnings"])


def test_command_skips_ambiguous_fixture_connectors():
    fixture = _fixture(
        ref=u"ambiguous",
        connectors=[
            ConnectorInfo(
                position=(100, 1000, 500),
                direction=(0, 0, -1),
                diameter_mm=100,
                system_classification=SANITARY,
                flow_direction=ConnectorInfo.FLOW_OUT),
            ConnectorInfo(
                position=(150, 1000, 500),
                direction=(0, 0, -1),
                diameter_mm=100,
                system_classification=SANITARY,
                flow_direction=ConnectorInfo.FLOW_BIDIRECTIONAL),
        ])

    result = run(
        fixtures=[fixture],
        corridor_points=[(0, 0, 0), (0, 3000, 0)],
        stack_point=(0, 0, 0),
        standard=default_standard(),
        usage_type=u"intermittent",
        collector_diameter_mm=100,
        slope_percent=2.0)

    assert not result.success
    assert any(u"ambiguous" in d for d in result.diagnostics)


def test_command_reports_collector_orientation_failure_cleanly():
    result = run(
        fixtures=[_fixture(u"left", y=500), _fixture(u"right", y=2500)],
        corridor_points=[(0, 0, 0), (0, 3000, 0)],
        stack_point=(0, 1500, 0),
        standard=default_standard(),
        usage_type=u"intermittent",
        collector_diameter_mm=100,
        slope_percent=2.0)

    assert not result.success
    assert u"both sides" in result.message


def test_unresolved_fixture_type_suppresses_recommended_size_but_routes():
    result = run(
        fixtures=[_fixture(u"mystery", y=1000, fixture_type_key=None)],
        corridor_points=[(0, 0, 0), (0, 3000, 0)],
        stack_point=(0, 0, 0),
        standard=default_standard(),
        usage_type=u"intermittent",
        collector_diameter_mm=100,
        slope_percent=2.0)

    assert result.success
    assert result.value["recommended_downstream_dn_mm"] is None
    assert any(u"discharge-unit data" in w for w in result.value["warnings"])


def test_bathroom_command_uses_exactly_one_wc_as_primary_backbone():
    wc = _fixture(u"wc-1", y=0, z=500, dn=110, fixture_type_key=u"WC")
    basin = _fixture(u"basin-1", y=300, z=700, dn=40,
                     fixture_type_key=u"WashBasin")

    result = run_bathroom_wc_backbone(
        fixtures=[wc, basin],
        stack_point=(2000, 0, 0),
        standard=default_standard(),
        usage_type=u"intermittent",
        collector_diameter_mm=110,
        slope_percent=1.0,
        wc_drop_z_mm=-150.0)

    assert result.success
    assert result.value["primary_fixture_ref"] == u"wc-1"
    assert result.value["graph"].routing_topology == u"WCBackbone"
    assert len(result.value["graph"].lead_segments) == 1
    assert result.value["graph"].lead_segments[0].end_point == (100, 0, -150.0)
    assert len(result.value["graph"].junctions) == 1
    assert result.value["graph"].junctions[0][1].target_ref == u"basin-1-connector"


def test_bathroom_command_rejects_no_wc():
    basin = _fixture(u"basin-1", y=300, z=700, dn=40,
                     fixture_type_key=u"WashBasin")

    result = run_bathroom_wc_backbone(
        fixtures=[basin],
        stack_point=(2000, 0, 0),
        standard=default_standard(),
        usage_type=u"intermittent",
        collector_diameter_mm=110,
        slope_percent=1.0)

    assert not result.success
    assert u"exactly one WC" in result.message


def test_bathroom_command_rejects_multiple_wcs():
    result = run_bathroom_wc_backbone(
        fixtures=[
            _fixture(u"wc-1", y=0, z=500, dn=110, fixture_type_key=u"WC"),
            _fixture(u"wc-2", y=300, z=500, dn=110, fixture_type_key=u"WC"),
        ],
        stack_point=(2000, 0, 0),
        standard=default_standard(),
        usage_type=u"intermittent",
        collector_diameter_mm=110,
        slope_percent=1.0)

    assert not result.success
    assert u"Found 2" in result.message
