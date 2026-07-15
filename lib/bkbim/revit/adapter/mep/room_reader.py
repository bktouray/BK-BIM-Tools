# -*- coding: utf-8 -*-
"""Reads native Revit Rooms doc-wide (MEP_SAD.md Sec 3). MEP Spaces, linked-
model rooms, worksets/design options/phases are explicitly deferred (Sec 3/8)
- this reads OST_Rooms only, matching the slice-1 scope.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import BuiltInCategory, BuiltInParameter, FilteredElementCollector

from bkbim.domain.mep.models.room_info import RoomInfo


class RevitRoomReader(object):
    def __init__(self, doc):
        self._doc = doc

    def read_rooms(self):
        """Only rooms with real placed area are returned - an unplaced Room
        (Area == 0) has no usable location to filter fixtures against.

        :rtype: list[bkbim.domain.mep.models.room_info.RoomInfo]
        """
        elements = (FilteredElementCollector(self._doc)
                    .OfCategory(BuiltInCategory.OST_Rooms)
                    .WhereElementIsNotElementType().ToElements())

        rooms = []
        for room in elements:
            try:
                if room.Area <= 0:
                    continue
            except Exception:
                continue
            try:
                name = room.get_Parameter(BuiltInParameter.ROOM_NAME).AsString() or u"?"
            except Exception:
                name = u"?"
            try:
                number = room.Number or u"?"
            except Exception:
                number = u"?"
            rooms.append(RoomInfo(
                ref=room.Id, name=name, number=number,
                level_ref=getattr(room, u"LevelId", None)))
        return rooms
