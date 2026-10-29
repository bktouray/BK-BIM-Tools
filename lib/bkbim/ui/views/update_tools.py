# -*- coding: utf-8 -*-
"""Explicit install action; startup checks never change extension source files."""
from pyrevit import forms
from bkbim.core.updater import GitUpdater, extension_root
from bkbim.ui.views.result_dialog import show_result


def run():
    updater = GitUpdater(extension_root())
    with forms.ProgressBar(title="Updating BK BIM Tools..."):
        result = updater.install()
    show_result("Update BK BIM Tools", result.message)
