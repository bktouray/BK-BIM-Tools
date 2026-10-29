# -*- coding: utf-8 -*-
import pytest
from bkbim.app.commands.master_filter_command import run
from bkbim.domain.filtering.rules import matches, validate_rule


def rule(operator, value="", parameter=("Instance", 1)):
    return {"parameter": parameter, "operator": operator, "value": value}


@pytest.mark.parametrize("operator,expected", [
    ("equals", True), ("not equals", False), ("contains", True),
    ("not contains", False), ("starts with", True), ("ends with", True)])
def test_text_rules_ignore_case(operator, expected):
    assert matches({"text": "Wall", "has_value": True}, rule(operator, "wALL")) == expected


@pytest.mark.parametrize("operator", ["not equals", "not contains", "has no value", "has value"])
def test_absent_parameter_never_matches(operator):
    assert not matches(None, rule(operator, "x"))


def test_empty_parameter_is_distinct_from_missing():
    assert matches({"text": "", "has_value": False}, rule("has no value"))
    assert not matches({"text": "", "has_value": False}, rule("has value"))


@pytest.mark.parametrize("operator,expected", [(">", False), (">=", True), ("<", False), ("<=", True)])
def test_numeric_comparison_uses_number_not_formatted_text(operator, expected):
    assert matches({"text": "1,000 mm", "number": 1000}, rule(operator, "1000")) == expected


def test_numeric_rule_does_not_coerce_text():
    assert not matches({"text": "1000"}, rule(">", "50"))


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "10 mm", ""])
def test_invalid_numeric_operand(value):
    with pytest.raises(ValueError):
        validate_rule(rule(">", value))


def test_criteria_are_and_between_fields_and_or_within_field():
    rows = [{"id": 1, "category": "Walls", "level": "L1"},
            {"id": 2, "category": "Doors", "level": "L2"},
            {"id": 3, "category": "Floors", "level": "L1"}]
    result = run(rows, {"category": ["Walls", "Doors"], "level": ["L1"]}, [], "all", None)
    assert result.success
    assert [row["id"] for row in result.value] == [1]


def test_all_any_and_empty_rules():
    rows = [{"id": 1}]
    reader = lambda record, key: {"text": "A", "has_value": True}
    rules = [rule("equals", "A"), rule("equals", "B")]
    assert run(rows, {}, rules, "all", reader).value == []
    assert run(rows, {}, rules, "any", reader).value == rows
    assert run(rows, {}, [], "any", reader).value == rows


def test_instance_and_type_parameters_keep_their_identity():
    reader = lambda record, key: {"text": key[0]}
    assert run([{}], {}, [rule("equals", "Type", ("Type", 1))], "all", reader).value == [{}]


def test_reader_failure_returns_no_partial_result():
    def reader(record, key):
        raise RuntimeError("Document read failed")
    result = run([{}], {}, [rule("equals", "A")], "all", reader)
    assert not result.success
    assert result.value is None
    assert "Document read failed" in result.message


def test_invalid_rule_is_rejected_even_when_no_elements():
    result = run([], {}, [rule(">", "bad")], "all", None)
    assert not result.success
