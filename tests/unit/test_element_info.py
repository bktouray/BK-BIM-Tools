# -*- coding: utf-8 -*-
from bkbim.domain.models.element_info import ElementInfo


def test_dimensions_and_center():
    ei = ElementInfo(ref="wall-1", category="Wall", min_x=0.0, max_x=10.0, min_y=2.0, max_y=5.0)

    assert ei.width_x == 10.0
    assert ei.width_y == 3.0
    assert ei.center_x == 5.0
    assert ei.center_y == 3.5


def test_width_is_absolute_regardless_of_min_max_order():
    ei = ElementInfo(ref="x", category="Wall", min_x=10.0, max_x=0.0, min_y=0.0, max_y=0.0)
    assert ei.width_x == 10.0


def test_ref_is_opaque_and_preserved():
    sentinel = object()
    ei = ElementInfo(ref=sentinel, category="Column", min_x=0, max_x=1, min_y=0, max_y=1)
    assert ei.ref is sentinel


def test_repr_works_with_plain_int_coordinates():
    # Regression test: IronPython 2.7 raises ValueError on ".Nf" format specs applied
    # to int operands (CPython silently casts). Caught live in Revit, not under
    # CPython-only tests - repr() must not assume float inputs.
    ei = ElementInfo(ref=None, category="Wall", min_x=0, max_x=10, min_y=0, max_y=3)
    text = repr(ei)
    assert "Wall" in text
    assert "0.0" in text
