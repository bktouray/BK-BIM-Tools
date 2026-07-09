# -*- coding: utf-8 -*-
"""One family, with every one of its placed types (MarkTypeGroup) grouped
under it. Auto Mark's review window shows one of these per row group, with a
single user-editable prefix applying to every type/instance inside it.

Pure domain data (ADR-0001).
"""


class MarkFamilyGroup(object):
    def __init__(self, family_name, type_groups):
        self.family_name = family_name
        self.type_groups = type_groups

    @property
    def instance_count(self):
        return sum(tg.instance_count for tg in self.type_groups)

    def __repr__(self):
        return u"<MarkFamilyGroup {0} types={1} instances={2}>".format(
            self.family_name, len(self.type_groups), self.instance_count)
