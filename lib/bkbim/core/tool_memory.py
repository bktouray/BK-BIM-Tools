# -*- coding: utf-8 -*-
"""Reusable RememberLastChoice service (Settings platform design Sec 2.7) -
generalizes what revit/adapter/mark_flow.py already does by hand for Auto
Mark's prefixes (load a layer from its well-known JSON path, read/set a
key, save back), so future tools need almost no code to persist a choice.

remember()/recall() default to the PROJECT layer (per-document - a chosen
dimension style/offset/type-filter is a project-specific habit). Callers
needing a genuinely personal, cross-project preference (like General's
theme) should keep using core.settings/settings_paths directly at
LAYER_USER, same as general_page.py already does - this module is
specifically for the common "remember what I picked last time" case, at
whichever of those two layers actually fits the data (LAYER_PROJECT is the
default since that's every dimension tool's actual need; MEP's pipe-type
choice below also uses LAYER_PROJECT for the same reason - a project's
loaded PipeTypes are project-specific).

LAYER_PROJECT needs a doc to compute its path from
(settings_paths.project_settings_path(doc)); LAYER_USER doesn't. Auto
Mark's own prefix file is left untouched (Sec 2.7) - this module is for
NEW consumers only.
"""

from bkbim.core.settings import LAYER_PROJECT, LAYER_USER, get_settings
from bkbim.core.settings_paths import project_settings_path, user_settings_path


def _path_for_layer(layer, doc):
    if layer == LAYER_PROJECT:
        if doc is None:
            raise ValueError(u"remember()/recall() at LAYER_PROJECT need doc=... to compute a path")
        return project_settings_path(doc)
    if layer == LAYER_USER:
        return user_settings_path()
    raise ValueError(u"tool_memory only supports LAYER_PROJECT or LAYER_USER, got: {0}".format(layer))


def remember(key, value, layer=LAYER_PROJECT, doc=None):
    """Persists one key immediately - never blocks the caller's real work on
    failure (matches mark_flow.py's own "remembering is a nicety" stance)."""
    try:
        settings = get_settings()
        path = _path_for_layer(layer, doc)
        settings.load_layer_from_json(layer, path)
        settings.set(key, value, layer=layer)
        settings.save_layer_to_json(layer, path)
    except ValueError:
        raise  # a programming error (missing doc, bad layer) - never swallow
    except Exception:
        pass


def recall(key, default=None, layer=LAYER_PROJECT, doc=None):
    """Reloads the layer's file fresh before reading - a remembered value
    must survive a new Revit session, not just live in memory. A missing
    doc/bad layer is a programming error and raises; a corrupted memory
    file fails open (returns default) rather than crashing the caller's
    real work - same "never let a broken memory mechanism block the tool"
    stance as IExistingDimensionChecker's own fail-open rule."""
    settings = get_settings()
    path = _path_for_layer(layer, doc)  # ValueError here IS a real bug - let it raise
    try:
        settings.load_layer_from_json(layer, path)
    except Exception:
        return default
    value = settings.get(key)
    return default if value is None else value
