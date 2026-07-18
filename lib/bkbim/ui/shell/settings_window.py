# -*- coding: utf-8 -*-
"""Code-behind for SettingsWindow.xaml - the suite's Settings control center
(Settings platform design Sec 2.3). Header (brand + search + workspace
preset) / left nav (one entry per registered SettingsPageDescriptor,
grouped by category) / content (the active page's own controls) / footer
(Restore Defaults / Import / Export / Cancel / Apply / OK).

Discovers every page from SettingsPageRegistry via
register_all_pages() (ui/views/settings/__init__.py) - this file is never
edited to add a page; a new module's settings page is a registration call
in that one aggregator, nothing here.

The active page is a plain, duck-typed controller object (see
office_standards_page.OfficeStandardsPage for the full example): build(),
validate(), apply(), reset_to_defaults(), export_to_file(path),
import_from_file(path). Footer actions that a page doesn't implement
(e.g. a future placeholder page with nothing to apply/export) are simply
skipped via hasattr(), not hard failures - not every page needs every
action.
"""

import os

import clr

clr.AddReference("PresentationFramework")

from pyrevit import forms
from System.Windows.Controls import Button, TextBlock

from bkbim.core.manifest import get_module_registry
from bkbim.core.settings_registry import get_settings_page_registry
from bkbim.ui.tokens import resolve_tokens_path
from bkbim.ui.views.confirmation_dialog import show_confirmation
from bkbim.ui.views.result_dialog import show_result
from bkbim.ui.views.settings import register_all_manifests, register_all_pages

_WORKSPACE_PRESETS = [
    u"Default", u"Architectural Documentation", u"Structural Documentation",
    u"Plumbing", u"HVAC", u"Electrical", u"BOQ", u"AI Productivity",
]


class SettingsWindow(forms.WPFWindow):
    def __init__(self):
        xaml_path = os.path.join(os.path.dirname(__file__), "SettingsWindow.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self._registry = get_settings_page_registry()
        register_all_pages(self._registry)
        register_all_manifests(get_module_registry())

        self._nav_buttons = {}    # page_id -> Button
        self._active_page = None  # currently built page controller instance
        self._active_page_id = None

        for preset in _WORKSPACE_PRESETS:
            self.WorkspacePresetCombo.Items.Add(preset)
        self.WorkspacePresetCombo.SelectedIndex = 0

        self._build_nav()
        pages = self._registry.all()
        if pages:
            self._show_page(pages[0].page_id)

        self.SearchBox.TextChanged += self._on_search_changed
        self.RestoreDefaultsButton.Click += self._on_restore_defaults
        self.ImportButton.Click += self._on_import
        self.ExportButton.Click += self._on_export
        self.CancelButton.Click += self._on_cancel
        self.ApplyButton.Click += self._on_apply
        self.OkButton.Click += self._on_ok

    # -- nav -----------------------------------------------------------

    def _build_nav(self, query=None):
        self.NavPanel.Children.Clear()
        self._nav_buttons = {}
        pages = self._registry.search(query) if query else self._registry.all()

        shown_categories = []
        for page in pages:
            if page.category not in shown_categories:
                shown_categories.append(page.category)
                header = TextBlock()
                header.Text = page.category.upper()
                header.Style = self.FindResource(u"NavCategoryHeader")
                self.NavPanel.Children.Add(header)

            button = Button()
            button.Content = page.title
            button.Style = self.FindResource(
                u"NavButtonActive" if page.page_id == self._active_page_id else u"NavButton")
            button.Click += self._make_nav_click_handler(page.page_id)
            self.NavPanel.Children.Add(button)
            self._nav_buttons[page.page_id] = button

    def _make_nav_click_handler(self, page_id):
        def handler(sender, args):
            self._show_page(page_id)
        return handler

    def _show_page(self, page_id):
        descriptor = self._registry.get(page_id)
        if descriptor is None:
            return

        self._active_page_id = page_id
        for pid, button in self._nav_buttons.items():
            button.Style = self.FindResource(u"NavButtonActive" if pid == page_id else u"NavButton")

        self.PageTitleText.Text = descriptor.title
        self.PageDescriptionText.Text = descriptor.description

        page = descriptor.page_factory()
        self._active_page = page
        self.ContentPanel.Children.Clear()
        self.ContentPanel.Children.Add(page.build())

    # -- search ----------------------------------------------------------

    def _on_search_changed(self, sender, args):
        query = self.SearchBox.Text
        self._build_nav(query)
        pages = self._registry.search(query) if query else self._registry.all()
        if pages and self._active_page_id not in [p.page_id for p in pages]:
            self._show_page(pages[0].page_id)

    # -- footer actions ----------------------------------------------------

    def _validate_active_page(self):
        """Returns True if the active page is valid (or has nothing to
        validate). Shows an alert and returns False otherwise."""
        page = self._active_page
        if page is None or not hasattr(page, "validate"):
            return True
        errors = page.validate()
        if errors:
            show_result(
                u"BK BIM Tools Settings",
                u"Cannot save - fix the following first:\n\n" + u"\n".join(errors))
            return False
        return True

    def _apply_active_page(self):
        page = self._active_page
        if page is None or not hasattr(page, "apply"):
            return True
        if not self._validate_active_page():
            return False
        try:
            page.apply()
        except Exception as e:
            show_result(
                u"BK BIM Tools Settings",
                u"Error saving settings:\n{0}".format(str(e)))
            return False
        return True

    def _on_apply(self, sender, args):
        self._apply_active_page()

    def _on_ok(self, sender, args):
        if self._apply_active_page():
            self.Close()

    def _on_cancel(self, sender, args):
        self.Close()

    def _on_restore_defaults(self, sender, args):
        page = self._active_page
        if page is None or not hasattr(page, "reset_to_defaults"):
            return
        result = show_confirmation(
            u"BK BIM Tools Settings",
            u"Reset this page's fields to their defaults? This does not save until "
            u"you click Apply or OK.",
            yes_text=u"Reset", no_text=u"Cancel")
        if result:
            page.reset_to_defaults()

    def _on_import(self, sender, args):
        page = self._active_page
        if page is None or not hasattr(page, "import_from_file"):
            show_result(u"BK BIM Tools Settings", u"This page doesn't support Import.")
            return
        path = forms.pick_file(file_ext="json", title=u"Import Settings")
        if not path:
            return
        try:
            page.import_from_file(path)
        except Exception as e:
            show_result(u"BK BIM Tools Settings", u"Import failed:\n{0}".format(str(e)))

    def _on_export(self, sender, args):
        page = self._active_page
        if page is None or not hasattr(page, "export_to_file"):
            show_result(u"BK BIM Tools Settings", u"This page doesn't support Export.")
            return
        path = forms.save_file(file_ext="json", default_name=self._active_page_id + u".json",
                               title=u"Export Settings")
        if not path:
            return
        try:
            page.export_to_file(path)
        except Exception as e:
            show_result(u"BK BIM Tools Settings", u"Export failed:\n{0}".format(str(e)))
