# -*- coding: utf-8 -*-
"""Small helpers for Revit selection prompts that can be interrupted by view changes.

Revit cancels active PickPoint/PickObject/PickObjects prompts when the user
switches views. For longer MEP workflows, treating that interruption as a full
tool cancel is hostile because the user loses all previous room/fixture/wall
choices. These helpers let the caller retry the same pick step instead.
"""

from bkbim.ui.views.confirmation_dialog import show_confirmation


def ask_retry_selection(title, detail=None):
    message = (
        u"The Revit pick step was interrupted.\n\n"
        u"This often happens when switching between plan and 3D views during "
        u"a command.\n\n"
        u"Continue from this same step?")
    if detail:
        message = u"{0}\n\n{1}".format(message, detail)
    return show_confirmation(title, message, yes_text=u"Continue", no_text=u"Cancel")
