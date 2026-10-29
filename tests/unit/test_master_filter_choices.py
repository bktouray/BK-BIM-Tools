# -*- coding: utf-8 -*-
from bkbim.domain.filtering.choices import cascade


ROWS = [
    {"category": "Doors", "family": "Single", "type": "900", "level": "L1", "parameters": [("Type", 1)]},
    {"category": "Doors", "family": "Double", "type": "1800", "level": "L2", "parameters": [("Type", 2)]},
    {"category": "Walls", "family": "Basic Wall", "type": "200", "level": "L3", "parameters": [("Instance", 3)]},
]


def test_category_limits_every_downstream_choice_and_parameters():
    options, selected, rows, parameters = cascade(ROWS, {"category": ["Doors"]})
    assert options["category"] == ["Doors", "Walls"]
    assert options["family"] == ["Double", "Single"]
    assert options["type"] == ["1800", "900"]
    assert options["level"] == ["L1", "L2"]
    assert rows == ROWS[:2]
    assert parameters == set([("Type", 1), ("Type", 2)])


def test_family_narrows_types_and_levels_without_hiding_sibling_families():
    options, selected, rows, parameters = cascade(ROWS, {"category": ["Doors"], "family": ["Single"]})
    assert options["family"] == ["Double", "Single"]
    assert options["type"] == ["900"]
    assert options["level"] == ["L1"]
    assert rows == ROWS[:1]


def test_switching_category_clears_invalid_descendants():
    options, selected, rows, parameters = cascade(ROWS, {
        "category": ["Walls"], "family": ["Single"], "type": ["900"], "level": ["L1"]})
    assert selected == {"category": ["Walls"], "family": [], "type": [], "level": []}
    assert options["type"] == ["200"]
    assert rows == ROWS[2:]


def test_multiselect_uses_union_and_preserves_valid_children():
    options, selected, rows, parameters = cascade(ROWS, {
        "category": ["Doors", "Walls"], "family": ["Single", "Basic Wall"]})
    assert options["type"] == ["200", "900"]
    assert rows == [ROWS[0], ROWS[2]]
    assert selected["family"] == ["Single", "Basic Wall"]


def test_clear_restores_all_choices():
    options, selected, rows, parameters = cascade(ROWS, {})
    assert rows == ROWS
    assert options["level"] == ["L1", "L2", "L3"]
    assert all(not values for values in selected.values())


def test_empty_scope_has_no_choices_or_parameters():
    options, selected, rows, parameters = cascade([], {"category": ["Doors"]})
    assert all(not values for values in options.values())
    assert rows == []
    assert parameters == set()


def test_type_narrows_level_and_level_narrows_parameter_choices():
    options, selected, rows, parameters = cascade(ROWS, {"type": ["900"]})
    assert options["level"] == ["L1"]
    assert parameters == set([("Type", 1)])
    options, selected, rows, parameters = cascade(ROWS, {"level": ["L2"]})
    assert rows == [ROWS[1]]
    assert parameters == set([("Type", 2)])
