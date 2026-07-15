# -*- coding: utf-8 -*-
import pytest

from bkbim.core.manifest import ModuleManifest, ModuleRegistry


def _make_manifest(module_id="office_standards"):
    return ModuleManifest(
        module_id=module_id,
        name="Office Standards",
        version="0.1.0",
        description="Dimensioning + MEP standard values",
        category="Office Standards",
    )


def test_register_and_get():
    registry = ModuleRegistry()
    manifest = _make_manifest()
    registry.register(manifest)

    assert registry.get("office_standards") is manifest


def test_get_missing_returns_none():
    registry = ModuleRegistry()
    assert registry.get("does-not-exist") is None


def test_duplicate_module_id_raises():
    registry = ModuleRegistry()
    registry.register(_make_manifest())
    with pytest.raises(ValueError):
        registry.register(_make_manifest())


def test_all_preserves_registration_order():
    registry = ModuleRegistry()
    registry.register(_make_manifest("b"))
    registry.register(_make_manifest("a"))

    assert [m.module_id for m in registry.all()] == ["b", "a"]


def test_reserved_fields_default_to_none_or_empty():
    manifest = _make_manifest()
    assert manifest.ribbon_panel is None
    assert manifest.license_requirement is None
    assert manifest.update_channel is None
    assert manifest.commands == []
    assert manifest.dependencies == []
    assert manifest.feature_flags == {}
