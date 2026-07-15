# -*- coding: utf-8 -*-
from bkbim.domain.mep.models.routing_plan import FittingPlan
from bkbim.domain.mep.routing.path_planner import (
    RoutingRequest, SlopeStrategy, plan_direct_route, plan_elbow_route)
from bkbim.domain.standards.standard import default_standard


class _FakeFixture(object):
    def __init__(self, ref):
        self.ref = ref


def test_direct_route_produces_one_segment_with_the_right_endpoints():
    request = RoutingRequest(
        fixture=_FakeFixture(u"fixture-1"), start_point=(0, 0, 1000),
        target_point=(2000, 0, 0), diameter_mm=100, material=u"uPVC")

    plan = plan_direct_route(request)

    assert len(plan.segments) == 1
    segment = plan.segments[0]
    assert segment.start_point == (0, 0, 1000)
    assert segment.end_point == (2000, 0, 0)
    assert segment.source_fixture_ref == u"fixture-1"


def test_no_slope_strategy_means_no_slope_warnings():
    request = RoutingRequest(
        fixture=None, start_point=(0, 0, 100), target_point=(2000, 0, 90),
        diameter_mm=100, material=u"uPVC")

    plan = plan_direct_route(request)

    assert plan.warnings == []
    # Slope is still computed and stored, just not validated
    assert plan.segments[0].slope_percent == 0.5


def test_slope_within_minimum_produces_no_warnings():
    std = default_standard()
    request = RoutingRequest(
        fixture=None, start_point=(0, 0, 1000), target_point=(2000, 0, 0),
        diameter_mm=100, material=u"uPVC", slope_strategy=SlopeStrategy(std))

    plan = plan_direct_route(request)

    assert plan.warnings == []


def test_slope_below_minimum_warns():
    std = default_standard()
    request = RoutingRequest(
        fixture=None, start_point=(0, 0, 100), target_point=(2000, 0, 90),
        diameter_mm=100, material=u"uPVC", slope_strategy=SlopeStrategy(std))

    plan = plan_direct_route(request)

    assert any(u"below" in w for w in plan.warnings)


def test_wrong_direction_warns_instead_of_silently_accepting():
    std = default_standard()
    request = RoutingRequest(
        fixture=None, start_point=(0, 0, 0), target_point=(2000, 0, 100),
        diameter_mm=100, material=u"uPVC", slope_strategy=SlopeStrategy(std))

    plan = plan_direct_route(request)

    assert any(u"rises" in w for w in plan.warnings)


def test_vertical_connection_warns_and_has_no_slope_value():
    std = default_standard()
    request = RoutingRequest(
        fixture=None, start_point=(0, 0, 1000), target_point=(0, 0, 0),
        diameter_mm=100, material=u"uPVC", slope_strategy=SlopeStrategy(std))

    plan = plan_direct_route(request)

    assert plan.segments[0].slope_percent is None
    assert any(u"Vertical connection" in w for w in plan.warnings)


def test_elbow_route_ceiling_drop_shape():
    """CeilingDrop: horizontal leg at the ceiling's Z, then a vertical drop
    down to the fixture connector."""
    request = RoutingRequest(
        fixture=None, start_point=(0, 0, 2400), target_point=(1500, 800, 600),
        diameter_mm=20, material=u"PEX")

    plan = plan_elbow_route(request, horizontal_z_mm=2400)

    assert len(plan.segments) == 2
    horizontal, vertical = plan.segments
    assert horizontal.start_point == (0, 0, 2400)
    assert horizontal.end_point == (1500, 800, 2400)
    assert vertical.start_point == (1500, 800, 2400)
    assert vertical.end_point == (1500, 800, 600)


def test_elbow_route_floor_rise_shape():
    """FloorRise: horizontal leg at the floor void's Z, then a vertical rise
    up to the fixture connector."""
    request = RoutingRequest(
        fixture=None, start_point=(0, 0, -300), target_point=(1500, 800, 600),
        diameter_mm=20, material=u"PEX")

    plan = plan_elbow_route(request, horizontal_z_mm=-300)

    horizontal, vertical = plan.segments
    assert horizontal.end_point == (1500, 800, -300)
    assert vertical.start_point == (1500, 800, -300)
    assert vertical.end_point == (1500, 800, 600)


def test_elbow_route_places_one_elbow_fitting_at_the_joint():
    request = RoutingRequest(
        fixture=None, start_point=(0, 0, 2400), target_point=(1500, 800, 600),
        diameter_mm=20, material=u"PEX")

    plan = plan_elbow_route(request, horizontal_z_mm=2400)

    assert len(plan.fittings) == 1
    assert plan.fittings[0].kind == FittingPlan.KIND_ELBOW
    assert plan.fittings[0].at_point == (1500, 800, 2400)


def test_elbow_route_attaches_target_connector_ref_to_the_final_segment():
    """Water Supply's fixture connector is at the TARGET end (supply flows
    main -> fixture), the mirror image of Sanitary Drainage's start-end
    connector. Regression test for a real bug caught 2026-07-10 building the
    first real Water Supply write: only source_connector_ref existed, which
    is right for drainage but silently wrong for supply.
    """
    request = RoutingRequest(
        fixture=None, start_point=(0, 0, 2400), target_point=(1500, 800, 600),
        diameter_mm=20, material=u"PEX", target_connector_ref=u"fixture-connector")

    plan = plan_elbow_route(request, horizontal_z_mm=2400)

    horizontal, vertical = plan.segments
    assert horizontal.target_connector_ref is None
    assert vertical.target_connector_ref == u"fixture-connector"


def test_elbow_route_never_produces_slope_warnings():
    """Water supply is pressure-fed - no SlopeStrategy concept applies."""
    request = RoutingRequest(
        fixture=None, start_point=(0, 0, 2400), target_point=(1500, 800, 600),
        diameter_mm=20, material=u"PEX")

    plan = plan_elbow_route(request, horizontal_z_mm=2400)

    assert plan.warnings == []
    assert plan.segments[0].slope_percent is None
    assert plan.segments[1].slope_percent is None
