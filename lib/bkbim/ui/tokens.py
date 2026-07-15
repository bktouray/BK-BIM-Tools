# -*- coding: utf-8 -*-
"""Absolute paths to the suite's shared design-token ResourceDictionaries
(UX_SPEC.md Sec 2) - the 7 SolidColorBrush values every options window used
to duplicate inline in its own <Window.Resources> (Brand.Primary, Text.Primary,
Text.Secondary, Surface.Base, Surface.Raised, Surface.Hover, Border.Default).

Merge into a window via pyrevit.forms.WPFWindow's OWN built-in
merge_resource_dict() (pyrevitlib/pyrevit/forms/__init__.py, already used
internally there for localization dictionaries) - call
self.merge_resource_dict(resolve_tokens_path()) BEFORE
forms.WPFWindow.__init__(self, xaml_path), so the merged brushes are already
present in self.Resources when wpf.LoadComponent parses the window's own XAML
(needed for any StaticResource lookup inside a Style Setter or the root
Window's own Background attribute, both of which resolve at parse time, not
just for runtime FindResource() calls). Absolute path required -
merge_resource_dict() builds its Uri with UriKind.Absolute.
"""

import os

from bkbim.core.settings import LAYER_USER, get_settings
from bkbim.core.settings_paths import user_settings_path

TOKENS_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), u"themes", u"Tokens.xaml"))
TOKENS_DARK_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), u"themes", u"Tokens.Dark.xaml"))

_THEME_KEY = u"general.theme"


def _is_revit_dark_theme():
    """Reads Revit's own current UI theme (Autodesk.Revit.UI.UIThemeManager,
    available since Revit 2021 - confirmed live on this Revit 2026 build).
    Never raises: an older Revit build or any other lookup failure just
    falls back to Light rather than crashing a window over a theme read."""
    try:
        import clr
        clr.AddReference("RevitAPIUI")
        from Autodesk.Revit.UI import UIThemeManager, UITheme
        return UIThemeManager.CurrentTheme == UITheme.Dark
    except Exception:
        return False


def resolve_tokens_path():
    """Returns TOKENS_PATH or TOKENS_DARK_PATH based on the General settings
    page's saved Theme preference ("Follow Revit" / "Light" / "Dark",
    USER layer - a personal preference, not an office standard). "Follow
    Revit" reads Revit's own current UI theme; defaults to Light (the
    original, always-worked behavior) if nothing's been saved yet.
    """
    settings = get_settings()
    settings.load_layer_from_json(LAYER_USER, user_settings_path())
    theme = settings.get(_THEME_KEY) or u"Follow Revit"

    if theme == u"Dark":
        return TOKENS_DARK_PATH
    if theme == u"Light":
        return TOKENS_PATH
    return TOKENS_DARK_PATH if _is_revit_dark_theme() else TOKENS_PATH
