# -*- coding: utf-8 -*-
"""Settings Page registration API (Settings platform design Sec 2.2).

A module registers one SettingsPageDescriptor per settings page it owns; the
Settings window discovers every registered page from SettingsPageRegistry and
never needs its own source touched to add one. Registration is explicit-
import (each page module exposes a register(registry) function; one
aggregator - ui/views/settings/__init__.py:register_all_pages - imports and
calls each one), not filesystem/reflection auto-discovery - this suite
already has a documented, real quirk (pyRevit doesn't share sys.path across
extensions; sys.modules caches stale code across a Revit session) that makes
reflection-based plugin loading a genuine reliability risk for a marginal
convenience gain over one-line imports.

page_factory is a zero-arg callable returning whatever the settings shell
needs to render the page - this module doesn't prescribe that shape beyond
"caller and page agree on it," matching how every existing options window in
this suite already decouples its window class from its caller.
"""


class SettingsPageDescriptor(object):
    def __init__(self, page_id, category, title, description, page_factory,
                 icon=None, keywords=None, validate=None, defaults=None,
                 import_handler=None, export_handler=None,
                 visible=None, workspace_presets=None):
        self.page_id = page_id
        self.category = category
        self.title = title
        self.description = description
        self.page_factory = page_factory
        self.icon = icon
        self.keywords = list(keywords or [])
        # Pure function (values_dict) -> list of validation messages, or None
        # if this page has nothing to validate (e.g. a placeholder page).
        self.validate = validate
        self.defaults = dict(defaults or {})
        self.import_handler = import_handler
        self.export_handler = export_handler
        self.visible = visible if visible is not None else (lambda: True)
        self.workspace_presets = list(workspace_presets or [])

    def matches(self, query):
        """Case-insensitive match against title/description/keywords."""
        q = (query or u"").strip().lower()
        if not q:
            return True
        haystacks = [self.title, self.description] + self.keywords
        for haystack in haystacks:
            if haystack and q in haystack.lower():
                return True
        return False

    def __repr__(self):
        return u"<SettingsPageDescriptor {0}>".format(self.page_id)


class SettingsPageRegistry(object):
    """page_id -> SettingsPageDescriptor. Registration order preserved for stable nav listing."""

    def __init__(self):
        self._pages = {}
        self._order = []

    def register(self, descriptor):
        if descriptor.page_id in self._pages:
            raise ValueError(u"Settings page already registered: {0}".format(descriptor.page_id))
        self._pages[descriptor.page_id] = descriptor
        self._order.append(descriptor.page_id)

    def get(self, page_id):
        return self._pages.get(page_id)

    def all(self):
        return [self._pages[pid] for pid in self._order]

    def by_category(self, category):
        return [page for page in self.all() if page.category == category]

    def categories(self):
        """Distinct categories, in first-registered order."""
        seen = []
        for page in self.all():
            if page.category not in seen:
                seen.append(page.category)
        return seen

    def search(self, query):
        return [page for page in self.all() if page.matches(query)]


_registry = SettingsPageRegistry()


def get_settings_page_registry():
    """Returns the process-wide SettingsPageRegistry singleton."""
    return _registry
