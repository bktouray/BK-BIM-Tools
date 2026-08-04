# -*- coding: utf-8 -*-
from bkbim.domain.mep.models.routing_plan import FittingPlan
from bkbim.domain.mep.sanitary.dwv_collector_graph import (
    ROUTE_X_THEN_Y, build_bathroom_dwv_backbone_graph,
    build_dwv_collector_graph, dwv_routing_plan_from_graph,
    orient_collector_corridor, wc_backbone_corridor,
)
from bkbim.domain.standards.standard import default_standard


def test_orients_collector_from_furthest_fixture_toward_stack():
    corridor = [(0, 0, 0), (0, 3000, 0)]

    oriented = orient_collector_corridor(
        corridor,
        stack_point=(0, 0, -100),
        target_points=[(100, 1000, 400), (100, 2500, 400)])

    assert oriented == [(0, 2500, 0), (0, 0, 0)]


def test_orients_collector_when_wall_order_is_opposite_flow():
    corridor = [(0, 3000, 0), (0, 0, 0)]

    oriented = orient_collector_corridor(
        corridor,
        stack_point=(0, 0, -100),
        target_points=[(100, 1000, 400), (100, 2500, 400)])

    assert oriented == [(0, 2500, 0), (0, 0, 0)]


def test_collector_preserves_corridor_corner_to_stack():
    corridor = [(0, 0, 0), (1000, 0, 0), (1000, 2000, 0)]

    oriented = orient_collector_corridor(
        corridor,
        stack_point=(0, 0, -100),
        target_points=[(900, 1500, 400)])

    assert oriented == [(1000, 1500, 0), (1000, 0, 0), (0, 0, 0)]


def test_rejects_fixtures_on_both_sides_of_stack():
    try:
        orient_collector_corridor(
            [(0, 0, 0), (0, 3000, 0)],
            stack_point=(0, 1500, -100),
            target_points=[(100, 500, 400), (100, 2500, 400)])
        assert False, "expected ValueError"
    except ValueError as error:
        assert u"both sides" in str(error)


def test_builds_sloped_collector_falling_to_stack():
    graph = build_dwv_collector_graph(
        corridor_points=[(0, 0, 0), (0, 3000, 0)],
        stack_point=(0, 0, 0),
        targets=[(u"wc", (100, 2000, 500), 100, u"WC")],
        collector_diameter_mm=100,
        slope_percent=2.0,
        standard=default_standard())

    assert graph.downstream_end == (0, 0, 0.0)
    assert graph.upstream_end == (0, 2000, 40.0)
    assert graph.slope_percent == 2.0
    assert graph.warnings == []


def test_junctions_are_ordered_upstream_to_downstream():
    graph = build_dwv_collector_graph(
        corridor_points=[(0, 0, 0), (0, 3000, 0)],
        stack_point=(0, 0, 0),
        targets=[
            (u"near-stack", (100, 500, 500), 50, u"Basin"),
            (u"far", (100, 2500, 500), 100, u"WC"),
        ],
        collector_diameter_mm=100,
        slope_percent=2.0)

    ordered_refs = [branch.target_ref for _junction, branch in graph.junctions]
    assert ordered_refs == [u"far", u"near-stack"]


def test_branch_taps_collector_at_sloped_elevation():
    graph = build_dwv_collector_graph(
        corridor_points=[(0, 0, 0), (0, 3000, 0)],
        stack_point=(0, 0, 0),
        targets=[(u"basin", (100, 1000, 500), 50, u"Basin")],
        collector_diameter_mm=75,
        slope_percent=2.0)

    junction, branch = graph.junctions[0]
    assert junction.position == (0, 1000, 20.0)
    assert branch.segments[0].start_point == (100, 1000, 500)
    assert branch.segments[0].end_point == (0, 1000, 20.0)
    assert branch.slope_percent == 480.0


def test_branch_rising_to_collector_warns_but_still_builds():
    graph = build_dwv_collector_graph(
        corridor_points=[(0, 0, 0), (0, 3000, 0)],
        stack_point=(0, 0, 0),
        targets=[(u"bad", (100, 1000, 0), 50, u"Bad Drain")],
        collector_diameter_mm=75,
        slope_percent=2.0)

    assert len(graph.junctions) == 1
    assert any(u"rises toward the collector" in w for w in graph.warnings)


def test_fitting_intents_are_sanitary_wyes_not_water_supply_tees():
    graph = build_dwv_collector_graph(
        corridor_points=[(0, 0, 0), (0, 3000, 0)],
        stack_point=(0, 0, 0),
        targets=[(u"wc", (100, 1000, 500), 100, u"WC")],
        collector_diameter_mm=100,
        slope_percent=2.0)

    assert len(graph.fitting_intents) == 1
    assert graph.fitting_intents[0].kind == FittingPlan.KIND_WYE_45
    assert graph.fitting_intents[0].angle_deg == 45.0


def test_branch_length_warning_does_not_block_graph():
    graph = build_dwv_collector_graph(
        corridor_points=[(0, 0, 0), (0, 3000, 0)],
        stack_point=(0, 0, 0),
        targets=[(u"far", (5000, 1000, 500), 50, u"Far Basin")],
        collector_diameter_mm=75,
        slope_percent=2.0,
        max_branch_length_mm=1000)

    assert len(graph.junctions) == 1
    assert any(u"exceeds" in w for w in graph.warnings)


def test_rejects_zero_or_negative_slope():
    try:
        build_dwv_collector_graph(
            corridor_points=[(0, 0, 0), (0, 3000, 0)],
            stack_point=(0, 0, 0),
            targets=[(u"wc", (100, 1000, 500), 100, u"WC")],
            collector_diameter_mm=100,
            slope_percent=0.0)
        assert False, "expected ValueError"
    except ValueError as error:
        assert u"slope" in str(error)


def test_pipe_plan_contains_collector_segments_then_branch_segments_no_fittings():
    graph = build_dwv_collector_graph(
        corridor_points=[(0, 0, 0), (1000, 0, 0), (1000, 2000, 0)],
        stack_point=(0, 0, 0),
        targets=[(u"wc", (900, 1500, 500), 100, u"WC")],
        collector_diameter_mm=100,
        slope_percent=2.0)

    plan = dwv_routing_plan_from_graph(graph, material=u"PVC")

    assert len(plan.segments) == 3
    assert plan.fittings == []

    collector_1, collector_2, branch = plan.segments
    assert collector_1.start_point == graph.collector_points[0]
    assert collector_1.end_point == graph.collector_points[1]
    assert collector_1.slope_percent == 2.0
    assert collector_2.start_point == graph.collector_points[1]
    assert collector_2.end_point == graph.collector_points[2]
    assert collector_2.slope_percent == 2.0
    assert branch.start_point == (900, 1500, 500)
    assert branch.end_point == graph.junctions[0][0].position


def test_wc_backbone_routes_from_wc_to_stack_not_wall_corridor():
    graph = build_bathroom_dwv_backbone_graph(
        wc_target=(u"wc", (0, 0, 500), 100, u"WC"),
        stack_point=(2000, 1000, 0),
        branch_targets=[],
        collector_diameter_mm=100,
        slope_percent=2.0,
        route_preference=ROUTE_X_THEN_Y)

    assert graph.routing_topology == u"WCBackbone"
    assert graph.primary_fixture_ref == u"wc"
    assert graph.collector_diameter_mm == 110.0
    assert graph.lead_segments == []
    assert graph.collector_points == [
        (0, 0, 500.0),
        (2000, 0, 460.0),
        (2000, 1000, 440.0),
    ]
    assert graph.stack_point == (2000, 1000, 440.0)


def test_wc_backbone_can_drop_below_slab_before_sloping_to_stack():
    graph = build_bathroom_dwv_backbone_graph(
        wc_target=(u"wc", (0, 0, 500), 110, u"WC"),
        stack_point=(2000, 0, 0),
        branch_targets=[],
        collector_diameter_mm=110,
        slope_percent=1.0,
        wc_drop_z_mm=-150.0)

    assert len(graph.lead_segments) == 1
    assert graph.lead_segments[0].start_point == (0, 0, 500)
    assert graph.lead_segments[0].end_point == (0, 0, -150.0)
    assert graph.collector_points == [(0, 0, -150.0), (2000, 0, -170.0)]
    assert graph.stack_point == (2000, 0, -170.0)


def test_wc_backbone_other_fixtures_tap_into_wc_drain():
    graph = build_bathroom_dwv_backbone_graph(
        wc_target=(u"wc", (0, 0, 500), 110, u"WC"),
        stack_point=(2000, 0, 0),
        branch_targets=[
            (u"floor-drain", (1000, 400, 520), 50, u"Floor Drain"),
            (u"sink", (1500, 300, 700), 40, u"Sink"),
        ],
        collector_diameter_mm=110,
        slope_percent=1.0)

    assert graph.collector_points == [(0, 0, 500.0), (2000, 0, 480.0)]
    assert [branch.target_ref for _j, branch in graph.junctions] == [
        u"floor-drain", u"sink"]
    assert graph.junctions[0][0].position == (1000, 0, 490.0)
    assert graph.junctions[1][0].position == (1500, 0, 485.0)


def test_wc_backbone_auto_prefers_path_closer_to_secondary_fixtures():
    corridor = wc_backbone_corridor(
        wc_point=(0, 0, 500),
        stack_point=(2000, 2000, 0),
        branch_points=[(100, 1500, 520)])

    assert corridor == [(0, 0, 500), (0, 2000, 500), (2000, 2000, 500)]


def test_wc_backbone_pipe_plan_has_wc_main_then_secondary_branches():
    graph = build_bathroom_dwv_backbone_graph(
        wc_target=(u"wc", (0, 0, 500), 110, u"WC"),
        stack_point=(2000, 0, 0),
        branch_targets=[(u"sink", (1500, 300, 700), 40, u"Sink")],
        collector_diameter_mm=110,
        slope_percent=1.0,
        wc_drop_z_mm=-150.0)

    plan = dwv_routing_plan_from_graph(graph, material=u"PVC")

    assert len(plan.segments) == 3
    wc_drop, wc_main, sink_branch = plan.segments
    assert wc_drop.start_point == (0, 0, 500)
    assert wc_drop.end_point == (0, 0, -150.0)
    assert wc_drop.slope_percent is None
    assert wc_main.start_point == (0, 0, -150.0)
    assert wc_main.end_point == (2000, 0, -170.0)
    assert wc_main.diameter_mm == 110
    assert sink_branch.start_point == (1500, 300, 700)
    assert sink_branch.end_point == (1500, 0, -165.0)
