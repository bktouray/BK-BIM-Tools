# -*- coding: utf-8 -*-
from bkbim.ui.views.options_memory import dimension_style_index, to_remembered


class _FakeType(object):
    def __init__(self, name, id_token):
        self._name = name
        self._id_token = id_token


def _name_fn(t):
    return t._name


def _id_fn(t):
    return t._id_token


def test_to_remembered_builds_id_and_name_dict():
    t = _FakeType(u"Linear - Tick", u"555")
    assert to_remembered(t, _name_fn, _id_fn) == {u"id": u"555", u"name": u"Linear - Tick"}


def test_matches_by_id_even_with_duplicate_names():
    # The real bug this fix addresses: two distinct types share a name.
    types = [_FakeType(u"Linear Dimension Style", u"111"), _FakeType(u"Linear Dimension Style", u"222")]
    remembered = {u"id": u"222", u"name": u"Linear Dimension Style"}
    assert dimension_style_index(types, _name_fn, remembered, id_token_fn=_id_fn) == 1


def test_falls_back_to_name_when_no_id_token_fn_given():
    types = [_FakeType(u"Linear - Arial", u"111"), _FakeType(u"Linear - Tick", u"222")]
    remembered = {u"id": u"222", u"name": u"Linear - Tick"}
    assert dimension_style_index(types, _name_fn, remembered) == 1  # no id_token_fn -> name match


def test_falls_back_to_name_when_remembered_id_not_found():
    types = [_FakeType(u"Linear - Arial", u"111"), _FakeType(u"Linear - Tick", u"222")]
    remembered = {u"id": u"999-deleted", u"name": u"Linear - Tick"}
    assert dimension_style_index(types, _name_fn, remembered, id_token_fn=_id_fn) == 1


def test_backward_compatible_with_plain_string_remembered_value():
    types = [_FakeType(u"Linear - Arial", u"111"), _FakeType(u"Linear - Tick", u"222")]
    assert dimension_style_index(types, _name_fn, u"Linear - Tick", id_token_fn=_id_fn) == 1


def test_returns_zero_when_nothing_remembered():
    types = [_FakeType(u"Linear - Arial", u"111")]
    assert dimension_style_index(types, _name_fn, None, id_token_fn=_id_fn) == 0
    assert dimension_style_index(types, _name_fn, u"", id_token_fn=_id_fn) == 0


def test_returns_zero_when_nothing_matches_at_all():
    types = [_FakeType(u"Linear - Arial", u"111")]
    remembered = {u"id": u"999", u"name": u"Nonexistent"}
    assert dimension_style_index(types, _name_fn, remembered, id_token_fn=_id_fn) == 0


def test_returns_zero_for_empty_types_list():
    assert dimension_style_index([], _name_fn, {u"id": u"1", u"name": u"anything"}, id_token_fn=_id_fn) == 0
