# -*- coding: utf-8 -*-
"""Lets the user pick which room(s) to generate Sanitary Drainage for -
Tier 1 (MEP_SAD.md Sec 7), reusing pyRevit's own forms.SelectFromList same
as pick_target_views does for view selection, not a custom WPF window yet.
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
        title=u"Pick the room(s) to generate Sanitary Drainage for",
        multiselect=True)
    if not picked_labels:
        return None

    return [name_map[label] for label in picked_labels]
