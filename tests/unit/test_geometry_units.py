# -*- coding: utf-8 -*-
from bkbim.domain.geometry.units import ft_to_mm, mm_to_ft


def test_mm_to_ft_roundtrip():
    assert abs(mm_to_ft(304.8) - 1.0) < 1e-9


def test_ft_to_mm_roundtrip():
    assert abs(ft_to_mm(1.0) - 304.8) < 1e-9


def test_roundtrip_is_identity():
    for value_mm in (0, 1, 800, 1500, 12345.6):
        assert abs(ft_to_mm(mm_to_ft(value_mm)) - value_mm) < 1e-6
