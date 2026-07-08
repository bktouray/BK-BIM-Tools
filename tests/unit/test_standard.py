# -*- coding: utf-8 -*-
from bkbim.domain.standards.standard import Standard, default_standard


def test_default_standard_has_a_name():
    std = default_standard()
    assert std.name == u"Default"


def test_custom_standard_overrides_fields():
    std = Standard(name=u"BS", offset_first_mm=750.0, collision_max_passes=5)
    assert std.name == u"BS"
    assert std.offset_first_mm == 750.0
    assert std.collision_max_passes == 5
    # Untouched fields keep their defaults
    assert std.wall_perimeter_gap_mm == 700.0


def test_two_standards_are_independent():
    a = Standard(name=u"A", offset_first_mm=100.0)
    b = Standard(name=u"B", offset_first_mm=200.0)
    assert a.offset_first_mm == 100.0
    assert b.offset_first_mm == 200.0


def test_default_side_defaults_to_below_left():
    std = default_standard()
    assert std.default_side == -1


def test_default_side_is_overridable():
    std = Standard(name=u"Flipped", default_side=1)
    assert std.default_side == 1
