# -*- coding: utf-8 -*-
"""Covers Auto Mark's numbering: one base mark per family+type/size, shared
by every instance of that type/size. Door/window variants can split by host
wall thickness into A/B suffixes, while other categories still behave like
one Revit type = one mark group. Base groups are sorted largest-to-smallest
by (dimension_a, dimension_b), wall suffixes are thickest-to-thinnest,
numbering restarts at 1 per family/prefix, and families with no prefix
assigned are skipped entirely.
"""
from bkbim.domain.marking.mark_planner import plan_marks
from bkbim.domain.models.mark_family_group import MarkFamilyGroup
from bkbim.domain.models.mark_type_group import MarkTypeGroup


def _type(name, a, b, instance_refs, host_thickness_mm=None):
    return MarkTypeGroup(
        type_name=name, dimension_a_mm=a, dimension_b_mm=b,
        instance_refs=instance_refs, host_thickness_mm=host_thickness_mm)


def test_every_instance_of_one_type_gets_the_same_mark():
    one_type = _type("900x2100", 900, 2100, ["a", "b", "c"])
    group = MarkFamilyGroup("Single-Flush", [one_type])

    result = plan_marks([group], {"Single-Flush": "D"})

    assert result == [("a", "D1"), ("b", "D1"), ("c", "D1")]


def test_numbers_largest_type_first_within_a_family():
    small = _type("800x2100", 800, 2100, ["small-1"])
    large = _type("900x2100", 900, 2100, ["large-1"])
    group = MarkFamilyGroup("Single-Flush", [small, large])

    result = plan_marks([group], {"Single-Flush": "D"})

    assert result == [("large-1", "D1"), ("small-1", "D2")]


def test_each_type_gets_its_own_number_regardless_of_instance_count():
    t1 = _type("900x2100", 900, 2100, ["a", "b"])
    t2 = _type("800x2100", 800, 2100, ["c"])
    group = MarkFamilyGroup("Single-Flush", [t1, t2])

    result = plan_marks([group], {"Single-Flush": "D"})

    assert result == [("a", "D1"), ("b", "D1"), ("c", "D2")]


def test_numbering_restarts_at_1_per_family():
    doors = MarkFamilyGroup("Single-Flush", [_type("900x2100", 900, 2100, ["d1"])])
    sliders = MarkFamilyGroup("Sliding-Door", [_type("1800x2100", 1800, 2100, ["s1"])])

    result = plan_marks([doors, sliders], {"Single-Flush": "D", "Sliding-Door": "SD"})

    assert result == [("d1", "D1"), ("s1", "SD1")]


def test_family_with_no_prefix_is_skipped_entirely():
    group = MarkFamilyGroup("Single-Flush", [_type("900x2100", 900, 2100, ["d1"])])

    assert plan_marks([group], {}) == []


def test_family_with_blank_prefix_is_skipped():
    group = MarkFamilyGroup("Single-Flush", [_type("900x2100", 900, 2100, ["d1"])])

    assert plan_marks([group], {"Single-Flush": ""}) == []


def test_ties_on_dimension_a_break_on_dimension_b():
    tall = _type("900x2400", 900, 2400, ["tall-1"])
    short = _type("900x2100", 900, 2100, ["short-1"])
    group = MarkFamilyGroup("Single-Flush", [short, tall])

    result = plan_marks([group], {"Single-Flush": "D"})

    assert result == [("tall-1", "D1"), ("short-1", "D2")]


def test_same_size_wall_thickness_variants_share_base_number_with_suffixes():
    wider = _type("1000x2100", 1000, 2100, ["wider"])
    thin_wall = _type("900x2100", 900, 2100, ["thin"], host_thickness_mm=150)
    thick_wall = _type("900x2100", 900, 2100, ["thick"], host_thickness_mm=200)
    group = MarkFamilyGroup("Single-Flush", [thin_wall, wider, thick_wall])

    result = plan_marks([group], {"Single-Flush": "D"})

    assert result == [("wider", "D1"), ("thick", "D2-A"), ("thin", "D2-B")]


def test_wall_suffix_a_is_always_thickest_wall():
    thin_wall = _type("900x2100", 900, 2100, ["thin"], host_thickness_mm=100)
    medium_wall = _type("900x2100", 900, 2100, ["medium"], host_thickness_mm=150)
    thick_wall = _type("900x2100", 900, 2100, ["thick"], host_thickness_mm=250)
    group = MarkFamilyGroup("Single-Flush", [medium_wall, thin_wall, thick_wall])

    result = plan_marks([group], {"Single-Flush": "D"})

    assert result == [("thick", "D1-A"), ("medium", "D1-B"), ("thin", "D1-C")]


def test_missing_host_wall_thickness_sorts_after_known_matching_type():
    unknown_wall = _type("900x2100", 900, 2100, ["unknown"])
    known_wall = _type("900x2100", 900, 2100, ["known"], host_thickness_mm=150)
    group = MarkFamilyGroup("Single-Flush", [unknown_wall, known_wall])

    result = plan_marks([group], {"Single-Flush": "D"})

    assert result == [("known", "D1-A"), ("unknown", "D1-B")]


def test_missing_dimension_sorts_as_smallest_not_largest():
    normal = _type("900x2100", 900, 2100, ["normal"])
    unresolvable = _type("Unknown", None, None, ["unresolvable"])
    group = MarkFamilyGroup("Single-Flush", [unresolvable, normal])

    result = plan_marks([group], {"Single-Flush": "D"})

    assert result == [("normal", "D1"), ("unresolvable", "D2")]
