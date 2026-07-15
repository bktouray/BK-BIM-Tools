# -*- coding: utf-8 -*-
import pytest

from bkbim.core.settings_registry import SettingsPageDescriptor, SettingsPageRegistry


def _page(page_id="office_standards", category="Office Standards", title="Office Standards",
          description="Dimension offsets, MEP tables", keywords=None):
    return SettingsPageDescriptor(
        page_id=page_id,
        category=category,
        title=title,
        description=description,
        page_factory=lambda: None,
        keywords=keywords or ["dimension", "offset", "mep"],
    )


def test_register_and_get():
    registry = SettingsPageRegistry()
    page = _page()
    registry.register(page)

    assert registry.get("office_standards") is page


def test_duplicate_page_id_raises():
    registry = SettingsPageRegistry()
    registry.register(_page())
    with pytest.raises(ValueError):
        registry.register(_page())


def test_all_preserves_registration_order():
    registry = SettingsPageRegistry()
    registry.register(_page("b", title="B"))
    registry.register(_page("a", title="A"))

    assert [p.page_id for p in registry.all()] == ["b", "a"]


def test_by_category_filters():
    registry = SettingsPageRegistry()
    registry.register(_page("office_standards", category="Office Standards"))
    registry.register(_page("general", category="General", title="General"))

    assert [p.page_id for p in registry.by_category("Office Standards")] == ["office_standards"]


def test_categories_are_distinct_in_first_registered_order():
    registry = SettingsPageRegistry()
    registry.register(_page("a", category="General", title="A"))
    registry.register(_page("b", category="Office Standards", title="B"))
    registry.register(_page("c", category="General", title="C"))

    assert registry.categories() == ["General", "Office Standards"]


def test_search_matches_title_description_and_keywords():
    registry = SettingsPageRegistry()
    registry.register(_page())

    assert len(registry.search("dimension")) == 1
    assert len(registry.search("DIMENSION")) == 1  # case-insensitive
    assert len(registry.search("offsets")) == 1  # matches description substring
    assert len(registry.search("nonexistent")) == 0


def test_search_empty_query_returns_everything():
    registry = SettingsPageRegistry()
    registry.register(_page("a", title="A"))
    registry.register(_page("b", title="B"))

    assert len(registry.search("")) == 2
    assert len(registry.search(None)) == 2


def test_default_visible_is_always_true():
    page = _page()
    assert page.visible() is True
