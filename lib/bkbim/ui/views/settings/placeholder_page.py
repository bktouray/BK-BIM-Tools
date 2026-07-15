# -*- coding: utf-8 -*-
"""Shared placeholder settings page (Settings platform design Sec 2.10) - one
component, parameterized per category, for every roadmap category with no
real module/settings behind it yet.

Read-only by design: no validate/apply/reset/import/export methods - a
placeholder page has nothing to persist, so the shell's duck-typed
hasattr() checks (ui/shell/settings_window.py) correctly disable those
footer actions for it rather than needing special-casing there.
"""

from System.Windows import TextWrapping, Thickness
from System.Windows.Controls import TextBlock

from bkbim.core.settings_registry import SettingsPageDescriptor

_MESSAGE = u"This module will become available as BK BIM Tools grows."

# Sec 2.10's explicit list. Documentation/MEP are deliberately NOT here -
# both already have real ribbon tools, and their only configurable data
# (dimension offsets, MEP tables) already lives on the Office Standards
# page rather than needing a second, module-scoped placeholder.
_CATEGORIES = [
    (u"architecture", u"Architecture"),
    (u"structural", u"Structural"),
    (u"ai", u"AI"),
    (u"performance", u"Performance"),
    (u"developer", u"Developer"),
    (u"licensing", u"Licensing"),
    (u"analytics", u"Analytics"),
    (u"workspace", u"Workspace"),
    (u"cloud", u"Cloud"),
]


class PlaceholderPage(object):
    def build(self):
        block = TextBlock()
        block.Text = _MESSAGE
        block.TextWrapping = TextWrapping.Wrap
        block.Margin = Thickness(0, 8, 0, 0)
        return block


def register(registry):
    for page_id, title in _CATEGORIES:
        registry.register(SettingsPageDescriptor(
            page_id=page_id,
            category=title,
            title=title,
            description=_MESSAGE,
            page_factory=PlaceholderPage,
            keywords=[title.lower()],
        ))
