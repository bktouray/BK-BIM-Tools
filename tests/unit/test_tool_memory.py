# -*- coding: utf-8 -*-
import os

import pytest

import bkbim.core.tool_memory as tool_memory
from bkbim.core.settings import LAYER_PROJECT, LAYER_USER, get_settings
from bkbim.core.tool_memory import recall, remember


class _FakeDoc(object):
    def __init__(self, title):
        self.Title = title


@pytest.fixture(autouse=True)
def _clear_settings_layers():
    settings = get_settings()
    settings.set_layer(LAYER_PROJECT, {})
    settings.set_layer(LAYER_USER, {})
    yield
    settings.set_layer(LAYER_PROJECT, {})
    settings.set_layer(LAYER_USER, {})


def test_remember_and_recall_at_project_layer(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "bkbim.core.tool_memory.project_settings_path",
        lambda doc: os.path.join(str(tmp_path), "project.json"))
    doc = _FakeDoc(u"Test Project")

    remember(u"grid_dimension.style", u"1:100", doc=doc)
    assert recall(u"grid_dimension.style", doc=doc) == u"1:100"


def test_recall_missing_key_returns_default(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "bkbim.core.tool_memory.project_settings_path",
        lambda doc: os.path.join(str(tmp_path), "project.json"))
    doc = _FakeDoc(u"Test Project")

    assert recall(u"nonexistent.key", default=u"fallback", doc=doc) == u"fallback"


def test_remember_at_project_layer_without_doc_raises():
    with pytest.raises(ValueError):
        remember(u"key", u"value")


def test_recall_at_project_layer_without_doc_raises():
    with pytest.raises(ValueError):
        recall(u"key")


def test_remember_and_recall_at_user_layer(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "bkbim.core.tool_memory.user_settings_path",
        lambda: os.path.join(str(tmp_path), "user.json"))

    remember(u"mep.pipe_type", u"PVC-SCH40", layer=LAYER_USER)
    assert recall(u"mep.pipe_type", layer=LAYER_USER) == u"PVC-SCH40"


def test_remember_preserves_other_keys_in_same_layer(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "bkbim.core.tool_memory.project_settings_path",
        lambda doc: os.path.join(str(tmp_path), "project.json"))
    doc = _FakeDoc(u"Test Project")

    remember(u"tool_a.choice", u"A", doc=doc)
    remember(u"tool_b.choice", u"B", doc=doc)

    assert recall(u"tool_a.choice", doc=doc) == u"A"
    assert recall(u"tool_b.choice", doc=doc) == u"B"


def test_persists_across_settings_store_reloads(tmp_path, monkeypatch):
    path = os.path.join(str(tmp_path), "project.json")
    monkeypatch.setattr("bkbim.core.tool_memory.project_settings_path", lambda doc: path)
    doc = _FakeDoc(u"Test Project")

    remember(u"grid_dimension.offset_mm", 750.0, doc=doc)

    # Simulate a fresh process/session by clearing in-memory state - recall()
    # must reload from disk, not rely on in-memory state alone.
    get_settings().set_layer(LAYER_PROJECT, {})
    assert recall(u"grid_dimension.offset_mm", doc=doc) == 750.0


def test_invalid_layer_raises():
    with pytest.raises(ValueError):
        remember(u"key", u"value", layer=u"not-a-real-layer", doc=_FakeDoc(u"X"))


def test_recall_survives_a_corrupted_memory_file(tmp_path, monkeypatch):
    path = os.path.join(str(tmp_path), "project.json")
    with open(path, "w") as f:
        f.write(u"{not valid json")
    monkeypatch.setattr("bkbim.core.tool_memory.project_settings_path", lambda doc: path)
    doc = _FakeDoc(u"Test Project")

    assert recall(u"anything", default=u"fallback", doc=doc) == u"fallback"


def test_remember_does_not_raise_when_storage_raises_value_error():
    settings = get_settings()
    original_path = tool_memory.project_settings_path
    original_load = settings.load_layer_from_json
    original_save = settings.save_layer_to_json

    def _raise_value_error(layer, path):
        raise ValueError(u"simulated JSON encoding failure")

    try:
        tool_memory.project_settings_path = lambda doc: u"unused.json"
        settings.load_layer_from_json = lambda layer, path: None
        settings.save_layer_to_json = _raise_value_error
        remember(
            u"mep.water_supply.pipe_type_name",
            u"Valsir Pexal\u00ae Standard",
            doc=_FakeDoc(u"Test Project"))
    finally:
        tool_memory.project_settings_path = original_path
        settings.load_layer_from_json = original_load
        settings.save_layer_to_json = original_save
