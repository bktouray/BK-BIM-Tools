# -*- coding: utf-8 -*-
"""Rules operate on display values; numeric operands use displayed project units."""
import math

try:
    unicode
except NameError:
    unicode = str

OPERATORS = (u"equals", u"not equals", u"contains", u"not contains",
             u"starts with", u"ends with", u"has value", u"has no value",
             u">", u">=", u"<", u"<=")


def validate_rule(rule):
    if not rule.get("parameter"):
        raise ValueError("Choose a parameter.")
    op = rule.get("operator")
    if op not in OPERATORS:
        raise ValueError("Unknown rule operator.")
    if op in (">", ">=", "<", "<="):
        try:
            value = float(rule.get("value", ""))
        except (ValueError, TypeError):
            raise ValueError("Enter a number in project display units (without a unit suffix).")
        if math.isnan(value) or math.isinf(value):
            raise ValueError("Enter a finite number.")


def matches(value, rule):
    """Missing parameters never match, including negative/empty predicates."""
    if value is None:
        return False
    text = unicode(value.get("text", u"") or u"").lower()
    expected = unicode(rule.get("value", u"") or u"").lower()
    op = rule["operator"]
    if op == "has value":
        return bool(value.get("has_value", False)) and bool(text)
    if op == "has no value":
        return not value.get("has_value", False) or not text
    if op in (">", ">=", "<", "<="):
        number = value.get("number")
        if number is None:
            return False
        target = float(rule["value"])
        if op == ">":
            return number > target
        if op == ">=":
            return number >= target
        if op == "<":
            return number < target
        return number <= target
    if op == "equals":
        return text == expected
    if op == "not equals":
        return text != expected
    if op == "contains":
        return expected in text
    if op == "not contains":
        return expected not in text
    if op == "starts with":
        return text.startswith(expected)
    if op == "ends with":
        return text.endswith(expected)
    raise ValueError("Unknown rule operator.")


def filter_records(records, criteria, rules, mode, value_reader):
    if mode not in ("all", "any"):
        raise ValueError("Choose all or any rules.")
    for rule in rules:
        validate_rule(rule)
    result = []
    for record in records:
        if any(criteria.get(key) and record.get(key) not in criteria[key]
               for key in ("category", "family", "type", "level")):
            continue
        checks = [matches(value_reader(record, rule["parameter"]), rule)
                  for rule in rules]
        if not checks or (all(checks) if mode == "all" else any(checks)):
            result.append(record)
    return result
