# -*- coding: utf-8 -*-
"""Lets an MEP flow pick one or more rooms with the branded BK picker.

The caller supplies the tool title so this shared prompt does not label
Water Supply work as Sanitary Drainage.
"""

from bkbim.ui.views.list_picker import show_multi_list_picker


def pick_rooms(rooms, title=u"Generate Sanitary Drainage"):
    """rooms: list[RoomInfo]. Returns a non-empty list[RoomInfo], or None if
    the user cancelled/selected nothing.
    """
    name_map = {}
    for r in rooms:
        label = u"{0} - {1}".format(r.number, r.name)
        name_map[label] = r

    picked_labels = show_multi_list_picker(
        title,
        u"Pick the room(s) to include.",
        sorted(name_map.keys()))
    if not picked_labels:
        return None

    return [name_map[label] for label in picked_labels]
