# -*- coding: utf-8 -*-
"""One family type/marking variant actually placed in the model, with the
dimension pair Auto Mark sorts by (largest to smallest) and every placed
instance of it - every one of which gets the SAME mark value in "size only"
mode (product owner: "if the family name and type is the same, they should
have the same mark").

`dimension_a_mm`/`dimension_b_mm` are category-dependent - Width/Height for
doors and windows, B/H for columns and beams, Length/Width for footings - the
Revit adapter decides which real parameters feed these two slots; this class
just holds whatever two numbers matter for sorting that category. Either may
be None when the type has no resolvable parameter for it (sorts last).

`host_thickness_mm` is populated for Doors/Windows when the instance host is
a wall. It deliberately splits one Revit family type into multiple marking
variants when the same door/window is used in different wall thicknesses;
the planner keeps one base number and adds A/B suffixes for those variants.

`reinforcement_groups` (list of MarkReinforcementGroup, or None) - populated
only for categories that support reinforcement-aware marking (Columns/Beams/
Footings; None for Doors/Windows). In "size + reinforcement" mode
(product owner, 2026-07-14: "give me the option to use basic sizes only or
to use size and the reinforcement simultaneously"), instances of this SAME
type/size that carry a genuinely different reinforcement signature get a
letter suffix appended to their shared base mark (e.g. "B1-A"/"B1-B") -
see mark_planner.py.

Pure domain data (ADR-0001) - `instance_refs` are opaque handles the Revit
adapter attaches and later resolves back to real elements for writing.
"""


class MarkTypeGroup(object):
    def __init__(self, type_name, dimension_a_mm, dimension_b_mm, instance_refs,
                 reinforcement_groups=None, host_thickness_mm=None):
        self.type_name = type_name
        self.dimension_a_mm = dimension_a_mm
        self.dimension_b_mm = dimension_b_mm
        self.instance_refs = instance_refs
        self.reinforcement_groups = reinforcement_groups
        self.host_thickness_mm = host_thickness_mm

    @property
    def instance_count(self):
        return len(self.instance_refs)

    def __repr__(self):
        # IronPython 2.7 quirk: ".Nf" format specs raise ValueError on int
        # operands (CPython auto-casts). Explicit float() keeps this safe on
        # both engines.
        a = float(self.dimension_a_mm) if self.dimension_a_mm is not None else 0.0
        b = float(self.dimension_b_mm) if self.dimension_b_mm is not None else 0.0
        host = u"" if self.host_thickness_mm is None else u" wall={0:.0f}".format(float(self.host_thickness_mm))
        return u"<MarkTypeGroup {0} {1:.0f}x{2:.0f}{3} n={4}>".format(
            self.type_name, a, b, host, self.instance_count)
