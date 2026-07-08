# -*- coding: utf-8 -*-
"""Tests the pure parts of Stage 4's riskiest technique: converting a family
TYPE-level Reference stable representation into an INSTANCE-level one. No Revit/clr
needed - this is exactly what makes it possible to unit-test this piece without a
live Revit session (the surrounding geometry-scanning code still needs one).
"""
from bkbim.revit.adapter.stable_representation import (
    element_id_token,
    reference_stable_key,
    rewrite_stable_representation_element_id,
)


def test_replaces_leading_token_only():
    result = rewrite_stable_representation_element_id("12345:1:RVTLINK/0:2:1", "99999")
    assert result == "99999:1:RVTLINK/0:2:1"


def test_preserves_everything_after_first_colon():
    result = rewrite_stable_representation_element_id("1:a:b:c", "2")
    assert result == "2:a:b:c"


def test_works_when_only_one_colon_present():
    result = rewrite_stable_representation_element_id("111:222", "444")
    assert result == "444:222"


class _FakeElementIdWithValue(object):
    Value = 777


class _FakeElementIdWithIntegerValueOnly(object):
    IntegerValue = 555


def test_element_id_token_prefers_value():
    assert element_id_token(_FakeElementIdWithValue()) == "777"


def test_element_id_token_falls_back_to_integer_value():
    assert element_id_token(_FakeElementIdWithIntegerValueOnly()) == "555"


class _FakeReference(object):
    def __init__(self, stable):
        self._stable = stable

    def ConvertToStableRepresentation(self, doc):
        return self._stable


def test_reference_stable_key_delegates_to_convert_to_stable_representation():
    ref = _FakeReference("abc-123:1:SURFACE")
    assert reference_stable_key(None, ref) == "abc-123:1:SURFACE"
