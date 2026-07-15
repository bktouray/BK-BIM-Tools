# -*- coding: utf-8 -*-
"""Runs the full Auto Mark flow: pick category -> read every placed family
type doc-wide -> review window (per-family prefix, sorted type/instance
preview) -> one Transaction writing the instance Mark parameter.

Doc-wide, not view-scoped (unlike the dimensioning flows) - Mark numbering
has to account for every placed instance in the model, not just whatever's
visible in the current view, so there's no "pick view(s)" step here at all.

Remembered prefixes are the first real consumer of core/settings.py
(previously wired but unused by any command) - persisted at the USER layer
to a fixed JSON file, same os.getenv("APPDATA")+"pyRevit" base directory
convention as lib/bkd_walllegend.py's config, but its own file and, unlike
that per-document config, deliberately NOT scoped to the current document:
a family's prefix (e.g. "Single-Flush" -> "D") is a user habit that should
carry across projects, not something to re-type every time.
"""

import os

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import Transaction

from bkbim.app.commands import auto_mark_command
from bkbim.core.settings import LAYER_USER, get_settings
from bkbim.domain.marking.mark_planner import MODE_SIZE_ONLY
from bkbim.revit.adapter.mark_type_reader import (
    CATEGORIES, DIMENSION_A_LABEL, DIMENSION_B_LABEL, category_supports_reinforcement, read_family_groups,
)
from bkbim.revit.adapter.mark_writer import RevitMarkWriter
from bkbim.ui.views.auto_mark_options import show_auto_mark_options
from bkbim.ui.views.category_picker import show_category_picker

_TRANSACTION_LABEL = u"Auto Mark"
_SETTINGS_KEY = u"auto_mark.prefixes"
_SETTINGS_KEY_MODE = u"auto_mark.mode"


def _settings_path():
    base = os.path.join(os.getenv(u"APPDATA", u""), u"pyRevit")
    try:
        if base and not os.path.isdir(base):
            os.makedirs(base)
    except Exception:
        pass
    return os.path.join(base, u"bkbim_auto_mark_prefixes.json")


def _load_remembered_prefixes():
    settings = get_settings()
    settings.load_layer_from_json(LAYER_USER, _settings_path())
    return settings.get(_SETTINGS_KEY) or {}


def _remember_prefixes(prefixes):
    settings = get_settings()
    remembered = dict(settings.get(_SETTINGS_KEY) or {})
    remembered.update(prefixes)
    settings.set(_SETTINGS_KEY, remembered, layer=LAYER_USER)
    try:
        settings.save_layer_to_json(LAYER_USER, _settings_path())
    except Exception:
        pass  # remembering a prefix is a nicety - never block the actual mark write on it


def _load_remembered_mode(category):
    settings = get_settings()
    settings.load_layer_from_json(LAYER_USER, _settings_path())
    modes = settings.get(_SETTINGS_KEY_MODE) or {}
    return modes.get(category, MODE_SIZE_ONLY)


def _remember_mode(category, mode):
    settings = get_settings()
    modes = dict(settings.get(_SETTINGS_KEY_MODE) or {})
    modes[category] = mode
    settings.set(_SETTINGS_KEY_MODE, modes, layer=LAYER_USER)
    try:
        settings.save_layer_to_json(LAYER_USER, _settings_path())
    except Exception:
        pass


def choose_category():
    """Shows the branded category picker. Returns one of
    mark_type_reader.CATEGORIES, or None if the user cancelled.
    """
    return show_category_picker(
        u"Auto Mark",
        u"Pick which category to mark.",
        CATEGORIES)


def run_auto_mark_flow(doc, category, title):
    """Runs the whole flow for one category. Returns (result, message):
    result is None (and message is None) if the user cancelled at either
    step, or if there was nothing to read for this category.
    """
    family_groups = read_family_groups(doc, category)
    if not family_groups:
        return None, u"No {0} found in the model.".format(category.lower())

    default_prefixes = _load_remembered_prefixes()
    supports_reinforcement = category_supports_reinforcement(category)
    default_mode = _load_remembered_mode(category) if supports_reinforcement else MODE_SIZE_ONLY

    options = show_auto_mark_options(
        category, DIMENSION_A_LABEL[category], DIMENSION_B_LABEL[category],
        family_groups, default_prefixes,
        supports_reinforcement=supports_reinforcement, default_mode=default_mode)
    if options is None:
        return None, None

    t = Transaction(doc, _TRANSACTION_LABEL)
    t.Start()
    try:
        result = auto_mark_command.run(family_groups, options.prefixes, RevitMarkWriter(doc), mode=options.mode)
    except Exception as e:
        t.RollBack()
        return None, u"Error:\n{0}".format(str(e))

    if result.success:
        t.Commit()
        _remember_prefixes(options.prefixes)
        if supports_reinforcement:
            _remember_mode(category, options.mode)
    else:
        t.RollBack()

    return result, result.message
