# -*- coding: utf-8 -*-
from bkbim.domain.mep.routing.routing_graph import (
    RoutingCorridor, build_routing_graph,
)


def test_corridor_needs_at_least_two_points():
    try:
        RoutingCorridor([(0, 0, 0)])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_corridor_projects_onto_the_nearest_segment():
    corridor = RoutingCorridor([(0, 0, 0), (1000, 0, 0), (1000, 1000, 0)])

    # A point off to the side of the first leg
    proj = corridor.project((500, 200, 0))

    assert proj.nearest_point == (500, 0, 0)
    assert proj.distance_along == 500
    assert proj.distance_from_corridor == 200


def test_corridor_projects_onto_the_second_leg_correctly():
    corridor = RoutingCorridor([(0, 0, 0), (1000, 0, 0), (1000, 1000, 0)])

    proj = corridor.project((1200, 500, 0))

    assert proj.nearest_point == (1000, 500, 0)
    # 1000 (first leg) + 500 (along second leg)
    assert proj.distance_along == 1500
    assert proj.distance_from_corridor == 200


def test_corridor_direction_at_matches_the_containing_segment():
    corridor = RoutingCorridor([(0, 0, 0), (1000, 0, 0), (1000, 1000, 0)])

    assert corridor.direction_at(500) == (1, 0, 0)
    assert corridor.direction_at(1500) == (0, 1, 0)


def test_corridor_total_length_sums_every_leg():
    corridor = RoutingCorridor([(0, 0, 0), (1000, 0, 0), (1000, 1000, 0)])
    assert corridor.total_length == 2000


def test_build_routing_graph_orders_junctions_by_distance_along_not_crow_flies():
    """The key correction: a target physically CLOSE to the origin but far
    ALONG the corridor must still come last - distance-along-corridor is
    what determines order, not straight-line distance from the origin.
    """
    corridor_points = [(0, 0, 0), (0, 3000, 0)]  # a straight corridor along Y
    targets = [
        (u"far-along-corridor", (100, 2900, 0), 15),   # near the origin in a straight line...
        (u"near-along-corridor", (100, 100, 0), 15),   # ...but this one is genuinely closer along the corridor
    ]

    graph = build_routing_graph(corridor_points, targets, wall_penetration_mm=80)

    ordered_refs = [branch.target_ref for _junction, branch in graph.junctions]
    assert ordered_refs == [u"near-along-corridor", u"far-along-corridor"]


def test_build_routing_graph_end_node_is_the_furthest_junction():
    corridor_points = [(0, 0, 0), (0, 3000, 0)]
    targets = [
        (u"t1", (100, 500, 0), 15),
        (u"t2", (100, 2000, 0), 15),
    ]

    graph = build_routing_graph(corridor_points, targets, wall_penetration_mm=80)

    last_junction_position = graph.junctions[-1][0].position
    assert graph.end_node.position == last_junction_position


def test_branch_at_the_same_elevation_as_the_corridor_is_one_horizontal_segment():
    """When the target's own Z already matches the corridor's, there's
    nothing for a vertical segment to do - the branch collapses to a single
    horizontal run, not an artificial 2-segment shape.
    """
    corridor_points = [(0, 0, 0), (0, 3000, 0)]
    targets = [(u"t1", (500, 1000, 0), 15)]

    graph = build_routing_graph(corridor_points, targets, wall_penetration_mm=80)

    junction, branch = graph.junctions[0]
    assert len(branch.segments) == 1
    assert branch.segments[0].start_point == (500, 1000, 0)
    assert branch.segments[0].end_point == (0, 1000, 0)
    assert junction.position == (0, 1000, 0)


def test_branch_at_a_different_elevation_gets_a_horizontal_then_vertical_segment():
    """Regression test for the real bug caught live 2026-07-10: a wash
    basin connector 400mm above the trunk previously had its 3D-distance
    projection fold that elevation difference into a mostly-vertical
    "perpendicular" stub, producing a diagonal-looking branch. Fixed shape:
    a horizontal segment (at the target's own Z) aligning with the tap
    point's plan position, then a purely vertical segment down/up to the
    corridor's Z - never diagonal.
    """
    corridor_points = [(0, 0, 0), (0, 3000, 0)]
    targets = [(u"basin-cold", (500, 1000, 400), 15)]

    graph = build_routing_graph(corridor_points, targets, wall_penetration_mm=80)

    junction, branch = graph.junctions[0]
    assert len(branch.segments) == 2

    horizontal, vertical = branch.segments
    assert horizontal.start_point == (500, 1000, 400)
    assert horizontal.end_point == (0, 1000, 400)   # aligns in plan, stays at target's own Z
    assert vertical.start_point == (0, 1000, 400)
    assert vertical.end_point == (0, 1000, 0)         # drops straight down to the corridor's Z
    assert junction.position == (0, 1000, 0)


def test_branch_warns_when_real_distance_differs_a_lot_from_configured_penetration():
    corridor_points = [(0, 0, 0), (0, 3000, 0)]
    # Real horizontal distance is 500mm; configured expectation is 80mm -
    # more than double the tolerance (wall_penetration_mm itself), so warn.
    targets = [(u"far-from-wall", (500, 1000, 0), 15)]

    graph = build_routing_graph(corridor_points, targets, wall_penetration_mm=80)

    assert any(u"far-from-wall" in w and u"differs substantially" in w for w in graph.warnings)


def test_branch_does_not_warn_when_real_distance_is_close_to_configured_penetration():
    corridor_points = [(0, 0, 0), (0, 3000, 0)]
    targets = [(u"near-the-wall", (100, 1000, 0), 15)]  # 100mm real vs 80mm configured

    graph = build_routing_graph(corridor_points, targets, wall_penetration_mm=80)

    assert graph.warnings == []


def test_branch_exceeding_max_length_warns_but_does_not_block():
    corridor_points = [(0, 0, 0), (0, 3000, 0)]
    targets = [(u"far-fixture", (5000, 1000, 0), 15)]

    graph = build_routing_graph(corridor_points, targets, wall_penetration_mm=80,
                                 max_branch_length_mm=1000)

    assert len(graph.junctions) == 1  # still built, not blocked
    assert any(u"far-fixture" in w and u"exceeds" in w for w in graph.warnings)


def test_branch_within_max_length_has_no_warning():
    corridor_points = [(0, 0, 0), (0, 3000, 0)]
    targets = [(u"close-fixture", (100, 1000, 0), 15)]

    graph = build_routing_graph(corridor_points, targets, wall_penetration_mm=80,
                                 max_branch_length_mm=1000)

    assert graph.warnings == []


def test_no_targets_produces_an_empty_graph_with_end_at_origin():
    corridor_points = [(0, 0, 0), (0, 3000, 0)]

    graph = build_routing_graph(corridor_points, [], wall_penetration_mm=80)

    assert graph.junctions == []
    assert graph.end_node.position == corridor_points[0]


def test_origin_node_position_is_the_corridors_first_point():
    corridor_points = [(100, 200, 300), (100, 3000, 300)]
    graph = build_routing_graph(corridor_points, [], wall_penetration_mm=80)
    assert graph.origin.position == (100, 200, 300)


def test_trunk_points_with_no_junctions_is_just_the_origin():
    corridor_points = [(0, 0, 0), (0, 3000, 0)]
    graph = build_routing_graph(corridor_points, [], wall_penetration_mm=80)
    assert graph.trunk_points == [(0, 0, 0)]


def test_trunk_points_visits_junctions_in_order():
    corridor_points = [(0, 0, 0), (0, 3000, 0)]
    targets = [
        (u"t1", (100, 500, 0), 15),
        (u"t2", (100, 2000, 0), 15),
    ]
    graph = build_routing_graph(corridor_points, targets, wall_penetration_mm=80)

    assert graph.trunk_points == [(0, 0, 0), (0, 500, 0), (0, 2000, 0)]
