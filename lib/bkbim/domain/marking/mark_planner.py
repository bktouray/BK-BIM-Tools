# -*- coding: utf-8 -*-
"""Turns family groups of placed types into a flat list of (instance ref,
mark value) assignments - the pure logic behind Auto Mark.

Numbering rule: one mark per family+type, shared by every instance of that
type (product owner: "if the family name and type is the same, they should
have the same mark" - corrected from an earlier per-instance-unique design).
Within a family (assigned one prefix), types are ordered largest-to-smallest
by (dimension_a, dimension_b) and numbered 1, 2, 3... - every instance of
type N gets that same "{prefix}{N}" value. Numbering restarts at 1 for every
family/prefix.

MODE_SIZE_AND_REINFORCEMENT (product owner, 2026-07-14: "give me the option
to use basic sizes only or to use size and the reinforcement simultaniously
and if theyre the same size but different reinforcement... use the same
prefix and number but add a letter suffix... B1-A and B1-B") - when a type
carries more than one distinct reinforcement signature
(MarkTypeGroup.reinforcement_groups, populated by the adapter for Columns/
Beams/Footings only), that type's base "{prefix}{N}" mark gets a letter
suffix per signature instead of being shared unmodified. Sub-groups are
ordered by instance count descending (most common design = "-A") - a
stable, sensible convention since "A" then reads as the typical/default one.
A type with only one signature (or MODE_SIZE_ONLY) is unaffected - same
plain "{prefix}{N}" as before.

A family with no prefix assigned (blank/missing in the `prefixes` map) is
skipped entirely - lets the user leave a family out of a given run instead of
forcing every family present to be numbered.

Pure domain code (ADR-0001) - each ref stays an opaque handle the Revit
adapter attaches and later resolves back to a real element for writing.
"""

MODE_SIZE_ONLY = u"size_only"
MODE_SIZE_AND_REINFORCEMENT = u"size_and_reinforcement"


def _type_sort_key(type_group):
    # Largest to smallest - negate since sort() is ascending. None (missing
    # parameter) sorts as smallest, not largest, so it doesn't jump the queue.
    a = type_group.dimension_a_mm
    b = type_group.dimension_b_mm
    a_key = -a if a is not None else float(u"inf")
    b_key = -b if b is not None else float(u"inf")
    return (a_key, b_key)


def sorted_type_groups(type_groups):
    """Public so the review window can preview types in the exact order
    plan_marks() will number them in - largest to smallest.
    """
    return sorted(type_groups, key=_type_sort_key)


def _letter_suffix(index):
    """0 -> 'A', 25 -> 'Z', 26 -> 'AA'... - bijective base-26, same scheme
    as bkbim.automation.common.column_letter, reimplemented locally (not
    imported) since that module lives outside the domain layer and pulls in
    a Revit import at module scope (ADR-0001: domain stays pure/Revit-free).
    """
    n = index + 1
    label = u""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        label = chr(ord(u"A") + rem) + label
    return label


def reinforcement_sorted_groups(reinforcement_groups):
    """Public so the review window can preview sub-groups in the exact
    order plan_marks() will letter-suffix them in - most instances first.
    """
    return sorted(reinforcement_groups, key=lambda g: -g.instance_count)


def plan_marks(family_groups, prefixes, mode=MODE_SIZE_ONLY):
    """family_groups: list of MarkFamilyGroup.
    prefixes: dict {family_name: prefix string}.
    mode: MODE_SIZE_ONLY (default, unchanged legacy behavior) or
        MODE_SIZE_AND_REINFORCEMENT.

    :rtype: list of (ref, mark_value) tuples, in assignment order.
    """
    assignments = []
    for family_group in family_groups:
        prefix = prefixes.get(family_group.family_name)
        if not prefix:
            continue

        n = 0
        for type_group in sorted_type_groups(family_group.type_groups):
            n += 1
            base_mark = u"{0}{1}".format(prefix, n)

            reinforcement_groups = (
                type_group.reinforcement_groups if mode == MODE_SIZE_AND_REINFORCEMENT else None)
            if not reinforcement_groups or len(reinforcement_groups) <= 1:
                for ref in type_group.instance_refs:
                    assignments.append((ref, base_mark))
                continue

            for i, sub_group in enumerate(reinforcement_sorted_groups(reinforcement_groups)):
                mark_value = u"{0}-{1}".format(base_mark, _letter_suffix(i))
                for ref in sub_group.instance_refs:
                    assignments.append((ref, mark_value))

    return assignments
