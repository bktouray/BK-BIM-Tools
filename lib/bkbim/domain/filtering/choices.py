# -*- coding: utf-8 -*-
"""Cascading choices, independent of WPF and Revit."""
FIELDS = ("category", "family", "type", "level")


def cascade(records, selections):
    """Narrow left to right, keeping only selections valid under their parents."""
    candidates = list(records)
    options = {}
    selected = {}
    for field in FIELDS:
        options[field] = sorted(set(row[field] for row in candidates))
        selected[field] = [value for value in selections.get(field, [])
                           if value in options[field]]
        if selected[field]:
            candidates = [row for row in candidates if row[field] in selected[field]]
    parameter_keys = set()
    for row in candidates:
        parameter_keys.update(row.get("parameters", ()))
    return options, selected, candidates, parameter_keys
