# -*- coding: utf-8 -*-
"""Covers slab_outline_planner: true perimeter tracing for a notched/stepped
slab footprint, per product owner (2026-07-07, screenshot of a real
notched slab with the whole outline traced in red): "I want dimensions to
follow every slab face." The fixture below is the REAL geometry read live
from the product owner's actual notched slab (8 side faces - a rectangle
with a rectangular notch removed from the bottom-middle), not a synthetic
guess - see column_grid_planner/slab_outline_planner module docstrings for
the live investigation this was built from.
"""
from bkbim.domain.dimensioning.slab_outline_planner import plan_slab_outline_dimensions
from bkbim.domain.models.dimension_plan import DimensionPlan
from bkbim.domain.models.outline_edge import OutlineEdge
from bkbim.domain.standards.standard import Standard


def _standard(**overrides):
    return Standard(name=u"Test", **overrides)


def _notched_slab_edges():
    # Real coordinates (feet) read live from the product owner's actual
    # notched slab via face.Origin/GetBoundingBox - a rectangle from
    # x[-35.6..35.6] y[-15.75..21.0], with a rectangular notch removed from
    # x[-21.24..21.24] y[-17.72..-15.75] (deeper than the rest of the bottom).
    return [
        OutlineEdge(ref=u"left", axis=u"x", coord=-35.6, span_lo=-15.75, span_hi=21.0, sign=-1),
        OutlineEdge(ref=u"top", axis=u"y", coord=21.0, span_lo=-35.6, span_hi=35.6, sign=1),
        OutlineEdge(ref=u"right", axis=u"x", coord=35.6, span_lo=-15.75, span_hi=21.0, sign=1),
        OutlineEdge(ref=u"bottom-right", axis=u"y", coord=-15.75, span_lo=21.24, span_hi=35.6, sign=-1),
        OutlineEdge(ref=u"notch-right", axis=u"x", coord=21.24, span_lo=-17.72, span_hi=-15.75, sign=1),
        OutlineEdge(ref=u"notch-bottom", axis=u"y", coord=-17.72, span_lo=-21.24, span_hi=21.24, sign=-1),
        OutlineEdge(ref=u"notch-left", axis=u"x", coord=-21.24, span_lo=-17.72, span_hi=-15.75, sign=-1),
        OutlineEdge(ref=u"bottom-left", axis=u"y", coord=-15.75, span_lo=-35.6, span_hi=-21.24, sign=-1),
    ]


def test_notched_slab_produces_one_dimension_per_real_edge():
    plans = plan_slab_outline_dimensions([_notched_slab_edges()], _standard())
    # 8 real edges, not 4 bounding-box sides - proves the notch is traced,
    # not collapsed into the overall envelope.
    assert len(plans) == 8
    assert all(p.kind == DimensionPlan.KIND_SLAB_OUTLINE_EDGE for p in plans)


def test_top_edge_references_the_left_and_right_edges_at_its_own_corners():
    plans = plan_slab_outline_dimensions([_notched_slab_edges()], _standard())
    top = [p for p in plans if p.line_coord_lo == -35.6 and p.line_coord_hi == 35.6 and p.axis == "x"]
    assert len(top) == 1
    assert top[0].refs == ["left", "right"]


def test_notch_bottom_references_the_notch_side_walls_not_the_outer_edges():
    # The deepest edge of the notch must reference notch-left/notch-right
    # (its real neighbors), never bottom-left/bottom-right (which sit at a
    # different Y level and don't actually touch it).
    plans = plan_slab_outline_dimensions([_notched_slab_edges()], _standard())
    notch_bottom = [p for p in plans if p.line_coord_lo == -21.24 and p.line_coord_hi == 21.24 and p.axis == "x"]
    assert len(notch_bottom) == 1
    assert notch_bottom[0].refs == ["notch-left", "notch-right"]


def test_each_edges_perp_pos_is_offset_outward_by_its_own_sign():
    std = _standard(structural_chain_offset_mm=300.0)
    plans = plan_slab_outline_dimensions([_notched_slab_edges()], std)
    from bkbim.domain.geometry.units import mm_to_ft
    offset_ft = mm_to_ft(300.0)

    top = [p for p in plans if p.refs == ["left", "right"]][0]
    assert top.perp_pos == 21.0 + offset_ft  # sign=+1, offset AWAY from slab (north)

    left = [p for p in plans if "left" not in p.refs and "bottom-left" in p.refs][0]
    assert left.perp_pos == -35.6 - offset_ft  # sign=-1, offset west


def test_two_slabs_edges_never_cross_match_each_other():
    slab_a = _notched_slab_edges()
    slab_b = [
        OutlineEdge(ref=u"b-left", axis=u"x", coord=100.0, span_lo=0.0, span_hi=10.0, sign=-1),
        OutlineEdge(ref=u"b-top", axis=u"y", coord=10.0, span_lo=100.0, span_hi=110.0, sign=1),
        OutlineEdge(ref=u"b-right", axis=u"x", coord=110.0, span_lo=0.0, span_hi=10.0, sign=1),
        OutlineEdge(ref=u"b-bottom", axis=u"y", coord=0.0, span_lo=100.0, span_hi=110.0, sign=-1),
    ]
    plans = plan_slab_outline_dimensions([slab_a, slab_b], _standard())
    assert len(plans) == 12  # 8 (slab_a) + 4 (slab_b)
    for p in plans:
        refs_are_a = all(r.startswith(("left", "top", "right", "bottom", "notch")) for r in p.refs)
        refs_are_b = all(r.startswith("b-") for r in p.refs)
        assert refs_are_a or refs_are_b  # never one ref from each slab


def test_an_edge_with_no_matching_neighbor_is_skipped_not_guessed_at():
    # Two edges of the SAME axis never have a perpendicular-axis neighbor to
    # match against - both must be skipped, not matched to something wrong.
    edges = [
        OutlineEdge(ref=u"a", axis=u"x", coord=0.0, span_lo=0.0, span_hi=10.0, sign=-1),
        OutlineEdge(ref=u"b", axis=u"x", coord=5.0, span_lo=0.0, span_hi=10.0, sign=1),
    ]
    plans = plan_slab_outline_dimensions([edges], _standard())
    assert plans == []


def test_an_edge_missing_only_one_corner_is_still_skipped():
    # "left" and "right" are missing their bottom neighbor (only "top" is
    # present) - each needs BOTH corners resolved, so both are skipped even
    # though "top" itself (which only needs left/right, both present)
    # resolves fine.
    edges = [
        OutlineEdge(ref=u"left", axis=u"x", coord=0.0, span_lo=0.0, span_hi=10.0, sign=-1),
        OutlineEdge(ref=u"top", axis=u"y", coord=10.0, span_lo=0.0, span_hi=10.0, sign=1),
        OutlineEdge(ref=u"right", axis=u"x", coord=10.0, span_lo=0.0, span_hi=10.0, sign=1),
    ]
    plans = plan_slab_outline_dimensions([edges], _standard())
    assert len(plans) == 1
    assert plans[0].refs == ["left", "right"]
