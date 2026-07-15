# -*- coding: utf-8 -*-
"""A room/space as read by IRoomReader (MEP_SAD.md Sec 3). Pure domain data
(ADR-0001) - `ref`/`level_ref` are opaque ElementId handles, same convention
as every other *_ref field in this suite.
"""


class RoomInfo(object):
    def __init__(self, ref, name, number, level_ref=None):
        self.ref = ref
        self.name = name
        self.number = number
        self.level_ref = level_ref

    def __repr__(self):
        return u"<RoomInfo {0} {1}>".format(self.number, self.name)
