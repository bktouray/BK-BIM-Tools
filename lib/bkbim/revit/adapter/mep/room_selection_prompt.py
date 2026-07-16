# -*- coding: utf-8 -*-
"""Lets an MEP flow pick one or more rooms with pyRevit's SelectFromList.

The caller supplies the tool title so this shared prompt does not label
Water Supply work as Sanitary Drainage.
"""

from pyrevit import forms


def pick_rooms(rooms, title=u"Generate Sanitary Drainage"):
    """rooms: list[RoomInfo]. Returns a non-empty list[RoomInfo], or None if
    the user cancelled/selected nothing.
    """
    name_map = {}
    for r in rooms:
        label = u"{0} - {1}".format(r.number, r.name)
        name_map[label] = r

    picked_labels = forms.SelectFromList.show(
        sorted(name_map.keys()),
        title=u"{0} - Pick room(s)".format(title),
        multiselect=True)
    if not picked_labels:
        return None

    return [name_map[label] for label in picked_labels]
