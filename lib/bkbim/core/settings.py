# -*- coding: utf-8 -*-
"""Centralized settings manager (SAD Sec 4.1).

Layered resolution: defaults -> office -> user -> project -> session (session wins).
Modules never persist their own settings; they read/write through get_settings().
JSON-backed for Phase 0 - the interface is stable if the backing store changes later
(e.g. cloud sync).
"""

import json
import os

LAYER_DEFAULTS = u"defaults"
LAYER_OFFICE = u"office"
LAYER_USER = u"user"
LAYER_PROJECT = u"project"
LAYER_SESSION = u"session"

_LAYER_ORDER = (LAYER_DEFAULTS, LAYER_OFFICE, LAYER_USER, LAYER_PROJECT, LAYER_SESSION)


try:
    _TEXT_TYPE = unicode
    _BINARY_TYPE = str
    _PYTHON2 = True
except NameError:
    _TEXT_TYPE = str
    _BINARY_TYPE = bytes
    _PYTHON2 = False


def _json_safe(value):
    """Normalizes byte strings before IronPython's JSON encoder sees them."""
    # IronPython 2 represents Revit's System.String as ``str``/``unicode``
    # simultaneously, but json's ensure_ascii encoder still treats non-ASCII
    # characters as ANSI bytes. UTF-8 encoding here makes json emit portable
    # ASCII ``\\uXXXX`` escapes instead of consulting the Windows code page.
    if _PYTHON2 and isinstance(value, (_TEXT_TYPE, _BINARY_TYPE)):
        try:
            return value.encode("utf-8")
        except Exception:
            try:
                return value.decode("utf-8").encode("utf-8")
            except Exception:
                return value.decode("latin-1").encode("utf-8")
    if isinstance(value, _TEXT_TYPE):
        return value
    if isinstance(value, _BINARY_TYPE):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.decode("latin-1")
    if isinstance(value, dict):
        return dict(
            (_json_safe(key), _json_safe(item))
            for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


class SettingsStore(object):
    """Holds one dict per layer; get() merges them in priority order (session wins)."""

    def __init__(self):
        self._layers = dict((layer, {}) for layer in _LAYER_ORDER)

    def set_layer(self, layer, values):
        if layer not in self._layers:
            raise ValueError(u"Unknown settings layer: {0}".format(layer))
        self._layers[layer] = dict(values or {})

    def load_layer_from_json(self, layer, path):
        if not os.path.isfile(path):
            return
        with open(path, "r") as f:
            self.set_layer(layer, json.load(f))

    def save_layer_to_json(self, layer, path):
        with open(path, "w") as f:
            json.dump(
                _json_safe(self._layers.get(layer, {})),
                f, indent=2, sort_keys=True)

    def get(self, key, default=None):
        value = default
        for layer in _LAYER_ORDER:
            layer_values = self._layers.get(layer, {})
            if key in layer_values:
                value = layer_values[key]
        return value

    def set(self, key, value, layer=LAYER_SESSION):
        self._layers.setdefault(layer, {})[key] = value


_store = SettingsStore()


def get_settings():
    """Returns the process-wide SettingsStore singleton."""
    return _store
