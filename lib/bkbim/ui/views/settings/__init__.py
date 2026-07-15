# -*- coding: utf-8 -*-
"""Aggregates every settings page's (and module manifest's) registration
(Settings platform design Sec 2.2). This is the ONE place that changes when
a new module gains a settings page - SettingsWindow itself is never edited
to add one, satisfying "nothing should require manual registration inside
the Settings window" without filesystem/reflection auto-discovery (see
settings_registry.py's docstring for why that was rejected).

register_all_pages()/register_all_manifests() are idempotent: SettingsWindow
may be opened more than once per Revit session, and both registries raise on
a duplicate id - guard against that here rather than making every caller
track whether it already ran this.
"""

from bkbim.ui.views.settings import about_page, general_page, office_standards_page, placeholder_page

_PAGES_REGISTERED = set()
_MANIFESTS_REGISTERED = set()


def register_all_pages(registry):
    # Registration order = nav display order (SettingsPageRegistry preserves
    # it) - matches the platform design's wireframe: General, Office
    # Standards, [placeholder categories], About last.
    if registry in _PAGES_REGISTERED:
        return
    general_page.register(registry)
    office_standards_page.register(registry)
    placeholder_page.register(registry)
    about_page.register(registry)
    _PAGES_REGISTERED.add(registry)


def register_all_manifests(registry):
    if registry in _MANIFESTS_REGISTERED:
        return
    office_standards_page.register_manifest(registry)
    _MANIFESTS_REGISTERED.add(registry)
