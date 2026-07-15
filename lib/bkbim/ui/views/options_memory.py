# -*- coding: utf-8 -*-
"""Shared helpers for pre-selecting a remembered dimension style / type
filter in an options window's ComboBox/ListBox.

Matches by ElementId token FIRST (via the existing
revit.adapter.stable_representation.element_id_token - stable across
sessions within the same project file), falling back to NAME only when no
id is remembered/given or the id no longer resolves (the type was deleted,
or this is genuinely a different project). Name-only was the original
design; upgraded after live-testing found a real data quirk in this
project - multiple distinct DimensionType elements share the exact display
name "Linear Dimension Style" - which made name-only matching
non-deterministic (a remembered name could match several real types at
once, over-selecting in a multi-select list). Extracted here (not left
inline per-window) because 5 windows need the identical logic at once -
ADR-0002's "second consumer" rule is satisfied 5 times over from the start.
"""


def to_remembered(item, type_name_fn, id_token_fn):
    """Builds the {"id":..., "name":...} payload tool_memory should store
    for one dimension-style/type-filter choice. Storing both lets recall
    prefer the id (see module docstring) while still falling back to name.
    """
    return {u"id": id_token_fn(item), u"name": type_name_fn(item)}


def _remembered_id_and_name(entry):
    """Normalizes one remembered entry - a to_remembered() dict (current
    format), or a plain name string (the format used before this fix
    existed, kept working rather than silently discarded on old data)."""
    if isinstance(entry, dict):
        return entry.get(u"id"), entry.get(u"name")
    return None, entry


def dimension_style_index(dimension_types, type_name_fn, remembered, id_token_fn=None):
    """Index into `dimension_types` matching the remembered dimension
    style. `remembered` is a to_remembered() dict, a plain name string
    (backward compatible), or None/falsy. Returns 0 (every window's
    original default) if nothing remembered or nothing matches.
    """
    if not remembered:
        return 0
    remembered_id, remembered_name = _remembered_id_and_name(remembered)

    if remembered_id and id_token_fn:
        tokens = [id_token_fn(dt) for dt in dimension_types]
        if remembered_id in tokens:
            return tokens.index(remembered_id)

    if remembered_name:
        names = [type_name_fn(dt) for dt in dimension_types]
        if remembered_name in names:
            return names.index(remembered_name)

    return 0


def select_remembered_types(list_box, type_name_fn, types, remembered, id_token_fn=None):
    """Pre-selects `list_box` items matching `remembered` - a list of
    to_remembered() dicts (or plain name strings, backward compatible). If
    `remembered` is empty/None (nothing remembered yet), selects
    EVERYTHING instead - preserves every window's original "all selected
    by default" behavior for a first run.
    """
    if not remembered:
        for i in range(list_box.Items.Count):
            list_box.SelectedItems.Add(list_box.Items[i])
        return

    id_tokens = [id_token_fn(t) for t in types] if id_token_fn else None
    names = [type_name_fn(t) for t in types]

    matched_indices = set()
    for entry in remembered:
        remembered_id, remembered_name = _remembered_id_and_name(entry)
        matched = False
        if remembered_id and id_tokens and remembered_id in id_tokens:
            matched_indices.add(id_tokens.index(remembered_id))
            matched = True
        if not matched and remembered_name and remembered_name in names:
            matched_indices.add(names.index(remembered_name))

    for i in sorted(matched_indices):
        list_box.SelectedItems.Add(list_box.Items[i])
