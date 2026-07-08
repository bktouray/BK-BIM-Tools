# -*- coding: utf-8 -*-
import json
import os

import pytest

from bkbim.core.settings import (
    LAYER_DEFAULTS,
    LAYER_OFFICE,
    LAYER_PROJECT,
    LAYER_SESSION,
    LAYER_USER,
    SettingsStore,
)


def test_layer_priority_session_wins_over_defaults():
    store = SettingsStore()
    store.set_layer(LAYER_DEFAULTS, {"offset_mm": 800})
    store.set_layer(LAYER_SESSION, {"offset_mm": 1200})

    assert store.get("offset_mm") == 1200


def test_layer_priority_full_chain():
    store = SettingsStore()
    store.set_layer(LAYER_DEFAULTS, {"a": "defaults"})
    store.set_layer(LAYER_OFFICE, {"a": "office"})
    store.set_layer(LAYER_USER, {"a": "user"})
    store.set_layer(LAYER_PROJECT, {"a": "project"})

    assert store.get("a") == "project"


def test_missing_key_returns_default():
    store = SettingsStore()
    assert store.get("missing", default=u"fallback") == u"fallback"


def test_set_unknown_layer_raises():
    store = SettingsStore()
    with pytest.raises(ValueError):
        store.set_layer("not-a-layer", {})


def test_json_roundtrip(tmp_path):
    path = os.path.join(str(tmp_path), "user.json")
    store = SettingsStore()
    store.set_layer(LAYER_USER, {"theme": "dark"})
    store.save_layer_to_json(LAYER_USER, path)

    with open(path, "r") as f:
        assert json.load(f) == {"theme": "dark"}

    store2 = SettingsStore()
    store2.load_layer_from_json(LAYER_USER, path)
    assert store2.get("theme") == "dark"


def test_load_layer_from_missing_file_is_noop(tmp_path):
    path = os.path.join(str(tmp_path), "does-not-exist.json")
    store = SettingsStore()
    store.load_layer_from_json(LAYER_USER, path)
    assert store.get("theme") is None
