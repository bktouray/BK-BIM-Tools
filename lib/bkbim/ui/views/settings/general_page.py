# -*- coding: utf-8 -*-
"""Settings page controller for 'General' (Settings platform design Sec 2.8).

Scoped down from the platform design's own draft wording, applying the same
"defer fields with no real consumer" discipline already used for Office
Standards' Naming Conventions/Precision/Annotation Defaults: Units display,
Startup behavior, and Update-check have no reading/enforcing code anywhere
in this suite today (Revit's own project units govern everything; no
updater exists to call) - building controls for them would be exactly the
speculative business logic ADR-0002 forbids. Language and Recent Projects
were already deferred in the platform design itself (no i18n infrastructure,
no "projects" concept in a Revit plugin).

Theme IS built, but only as far as honest: the choice is genuinely
persisted (USER layer - a personal preference, not an office standard), but
actually swapping every open window's palette to a dark variant is separate,
real infrastructure (a Tokens.Dark.xaml + retrofitting every window's
merge_resource_dict call) not built in this pass - same "shape now, behavior
later" pattern already used for Standard.mep_default_pipe_type_name=None.
"""

from System.Windows import HorizontalAlignment, TextWrapping, Thickness
from System.Windows.Controls import ComboBox, StackPanel, TextBlock

from bkbim.core.settings import LAYER_USER, get_settings
from bkbim.core.settings_paths import user_settings_path
from bkbim.core.settings_registry import SettingsPageDescriptor

_SETTINGS_KEY = u"general.theme"
_THEMES = [u"Follow Revit", u"Light", u"Dark"]
_DEFAULT_THEME = u"Follow Revit"


def _load_theme():
    settings = get_settings()
    settings.load_layer_from_json(LAYER_USER, user_settings_path())
    return settings.get(_SETTINGS_KEY) or _DEFAULT_THEME


class GeneralPage(object):
    def __init__(self):
        self._theme = _load_theme()
        self._theme_combo = None

    def build(self):
        panel = StackPanel()

        note = TextBlock()
        note.Text = (
            u"Theme is saved as a preference now; applying it to every open window "
            u"(a dark color palette) is separate work not built yet - it won't "
            u"change any window's colors until that lands.")
        note.TextWrapping = TextWrapping.Wrap
        note.Margin = Thickness(0, 0, 0, 12)
        panel.Children.Add(note)

        label = TextBlock()
        label.Text = u"Theme"
        label.Margin = Thickness(0, 0, 0, 4)
        panel.Children.Add(label)

        combo = ComboBox()
        combo.Width = 200
        combo.Height = 28
        combo.HorizontalAlignment = HorizontalAlignment.Left
        for theme in _THEMES:
            combo.Items.Add(theme)
        combo.SelectedIndex = _THEMES.index(self._theme) if self._theme in _THEMES else 0
        self._theme_combo = combo
        panel.Children.Add(combo)

        return panel

    def read_values(self):
        index = self._theme_combo.SelectedIndex
        theme = _THEMES[index] if 0 <= index < len(_THEMES) else _DEFAULT_THEME
        return {u"theme": theme}

    def validate(self):
        return []  # a pick from a closed ComboBox list is always valid

    def apply(self):
        theme = self.read_values()[u"theme"]
        self._theme = theme
        settings = get_settings()
        settings.set(_SETTINGS_KEY, theme, layer=LAYER_USER)
        settings.save_layer_to_json(LAYER_USER, user_settings_path())

    def reset_to_defaults(self):
        self._theme_combo.SelectedIndex = _THEMES.index(_DEFAULT_THEME)


def register(registry):
    registry.register(SettingsPageDescriptor(
        page_id=u"general",
        category=u"General",
        title=u"General",
        description=u"Suite-wide preferences.",
        page_factory=GeneralPage,
        keywords=[u"theme", u"dark", u"light", u"preferences"],
    ))
