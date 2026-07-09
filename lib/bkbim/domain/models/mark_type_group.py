# -*- coding: utf-8 -*-
"""One family type actually placed in the model, with the dimension pair
Auto Mark sorts by (largest to smallest) and every placed instance of it -
every one of which gets the SAME mark value (product owner: "if the family
name and type is the same, they should have the same mark").

`dimension_a_mm`/`dimension_b_mm` are category-dependent - Width/Height for
doors and windows, B/H for columns and beams, Length/Width for footings - the
Revit adapter decides which real parameters feed these two slots; this class
just holds whatever two numbers matter for sorting that category. Either may
be None when the type has no resolvable parameter for it (sorts last).

Pure domain data (ADR-0001) - `instance_refs` are opaque handles the Revit
adapter attaches and later resolves back to real elements for writing; since
every instance of a type shares one mark, there's no need for anything
richer than the bare ref (no per-instance sort key - see mark_planner.py).
"""


class MarkTypeGroup(object):
    def __init__(self, type_name, dimension_a_mm, dimension_b_mm, instance_refs):
        self.type_name = type_name
        self.dimension_a_mm = dimension_a_mm
        self.dimension_b_mm = dimension_b_mm
        self.instance_refs = instance_refs

    @property
    def instance_count(self):
        return len(self.instance_refs)

    def __repr__(self):
        # IronPython 2.7 quirk: ".Nf" format specs raise ValueError on int
        # operands (CPython auto-casts). Explicit float() keeps this safe on
        # both engines.
        a = float(self.dimension_a_mm) if self.dimension_a_mm is not None else 0.0
        b = float(self.dimension_b_mm) if self.dimension_b_mm is not None else 0.0
        return u"<MarkTypeGroup {0} {1:.0f}x{2:.0f} n={3}>".format(
            self.type_name, a, b, self.instance_count)
