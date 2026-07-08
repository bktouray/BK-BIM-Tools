# -*- coding: utf-8 -*-
from bkbim.domain.models.dimension_plan import DimensionPlan


def test_holds_fields_as_given():
    plan = DimensionPlan(
        kind=DimensionPlan.KIND_INSIDE_CHAIN,
        refs=["a", "b", "c"],
        axis="x",
        line_coord_lo=0.0,
        line_coord_hi=10.0,
        perp_pos=-2.5,
    )
    assert plan.kind == DimensionPlan.KIND_INSIDE_CHAIN
    assert plan.refs == ["a", "b", "c"]
    assert plan.axis == "x"
    assert plan.line_coord_lo == 0.0
    assert plan.line_coord_hi == 10.0
    assert plan.perp_pos == -2.5


def test_kind_constants_are_distinct():
    kinds = {
        DimensionPlan.KIND_OVERALL,
        DimensionPlan.KIND_SNAP_ON_EDGE,
        DimensionPlan.KIND_INSIDE_CHAIN,
        DimensionPlan.KIND_OUTSIDE_CHAIN,
    }
    assert len(kinds) == 4
