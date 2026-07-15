# -*- coding: utf-8 -*-
"""Opens the Settings window (Settings platform design Sec 2.3). No
Transaction needed - Settings never touches the Revit model, only
SettingsStore-backed JSON files on disk.
"""

from bkbim.ui.shell.settings_window import SettingsWindow


def run_settings_flow():
    window = SettingsWindow()
    window.ShowDialog()
