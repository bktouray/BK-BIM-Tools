# -*- coding: utf-8 -*-
"""Covers Auto Mark's numbering: one mark per family+type, shared by every
instance of that type (product owner: "if the family name and type is the
same, they should have the same mark"), types sorted largest-to-smallest by
(dimension_a, dimension_b) within a family, numbering restarting at 1 per
family/prefix, and families with no prefix assigned being skipped entirely.
"""
from bkbim.domain.marking.mark_planner import plan_marks
from bkbim.domain.models.mark_family_group import MarkFamilyGroup
from bkbim.domain.models.mark_type_group import MarkTypeGroup


def _type(name, a, b, instance_refs):
    return MarkTypeGroup(type_name=name, dimension_a_mm=a, dimension_b_mm=b, instance_refs=instance_refs)


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


def test_missing_dimension_sorts_as_smallest_not_largest():
    normal = _type("900x2100", 900, 2100, ["normal"])
    unresolvable = _type("Unknown", None, None, ["unresolvable"])
    group = MarkFamilyGroup("Single-Flush", [unresolvable, normal])

    result = plan_marks([group], {"Single-Flush": "D"})

    assert result == [("normal", "D1"), ("unresolvable", "D2")]
