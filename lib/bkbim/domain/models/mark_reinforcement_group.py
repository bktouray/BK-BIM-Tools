# -*- coding: utf-8 -*-
"""One distinct reinforcement signature within a single MarkTypeGroup (same
family+type/size, but a different normalized rebar signature - see
bkbim.domain.marking.reinforcement_signature). Only populated for
categories that support reinforcement-aware marking (Columns/Beams/
Footings); Doors/Windows leave MarkTypeGroup.reinforcement_groups as None.

`sources` (product owner, 2026-07-15: "make me notice that difference
when marking") - the distinct reinforcement_signature.SOURCE_* labels
seen among this group's instances, first-appearance order. Usually one
entry (every instance in a signature group came from the same tier), but
can hold more than one: since the modeled-rebar and text-tier signature
builders deliberately share one token vocabulary (see
reinforcement_signature.py), a modeled-rebar instance and a text-only
instance of the truly identical real design land in the SAME group here -
`sources` is what lets the UI still show that mix rather than hiding it.

Pure domain data (ADR-0001).
"""


class MarkReinforcementGroup(object):
    def __init__(self, signature, instance_refs, sources=None):
        self.signature = signature
        self.instance_refs = instance_refs
        self.sources = sources or []

    @property
    def instance_count(self):
        return len(self.instance_refs)

    def __repr__(self):
        return u"<MarkReinforcementGroup {0!r} n={1} sources={2!r}>".format(
            self.signature, self.instance_count, self.sources)
