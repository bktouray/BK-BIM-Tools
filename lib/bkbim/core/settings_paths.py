# -*- coding: utf-8 -*-
"""Well-known JSON file paths for SettingsStore layers (Settings platform
design Sec 2.7/2.9). Auto Mark's prefix file
(revit/adapter/mark_flow.py:_settings_path) proved the base convention by
hand for one USER-layer file first - this generalizes it so future
consumers don't each re-derive their own path logic. Auto Mark's own file is
left as-is (not migrated here) - it already works.
"""

import os


def _appdata_pyrevit_dir():
    base = os.path.join(os.getenv(u"APPDATA", u""), u"pyRevit")
    try:
        if base and not os.path.isdir(base):
            os.makedirs(base)
    except Exception:
        pass
    return base


def office_standards_path():
    """OFFICE layer is shared office-wide, not per-user or per-document - one
    fixed file, same base directory Auto Mark's USER-layer file already uses.
    """
    return os.path.join(_appdata_pyrevit_dir(), u"bkbim_office_standards.json")


def user_settings_path():
    """One shared USER-layer file for suite-wide personal preferences
    (General page) and future tool-memory USER-layer entries. Deliberately
    separate from Auto Mark's own bkbim_auto_mark_prefixes.json - that file
    already works and isn't migrated here (Sec 2.7)."""
    return os.path.join(_appdata_pyrevit_dir(), u"bkbim_user_settings.json")


def project_settings_path(doc):
    """PROJECT layer is scoped per-document - reuses bkd_walllegend.py's own
    proven "safe doc title" convention (the one existing precedent for
    doc-scoped storage in this codebase) rather than inventing a new one."""
    title = getattr(doc, u"Title", None) or u"untitled"
    safe = u"".join(c if c.isalnum() else u"_" for c in title)
    return os.path.join(_appdata_pyrevit_dir(), u"bkbim_project_" + safe + u".json")
