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

A family with no prefix assigned (blank/missing in the `prefixes` map) is
skipped entirely - lets the user leave a family out of a given run instead of
forcing every family present to be numbered.

Pure domain code (ADR-0001) - each ref stays an opaque handle the Revit
adapter attaches and later resolves back to a real element for writing.
"""


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


def plan_marks(family_groups, prefixes):
    """family_groups: list of MarkFamilyGroup.
    prefixes: dict {family_name: prefix string}.

    :rtype: list of (ref, mark_value) tuples, in assignment order. Every ref
        belonging to the same type appears with the identical mark_value.
    """
    assignments = []
    for family_group in family_groups:
        prefix = prefixes.get(family_group.family_name)
        if not prefix:
            continue

        n = 0
        for type_group in sorted_type_groups(family_group.type_groups):
            n += 1
            mark_value = u"{0}{1}".format(prefix, n)
            for ref in type_group.instance_refs:
                assignments.append((ref, mark_value))

    return assignments
