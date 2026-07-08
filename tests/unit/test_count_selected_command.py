# -*- coding: utf-8 -*-
"""Proves the app layer works against a fake IElementReader with no Revit involved -
the payoff of keeping `app` and `domain` pure (SAD Sec 6).
"""
from bkbim.app.commands import count_selected_command
from bkbim.core import di
from bkbim.core.di import ServiceContainer
from bkbim.domain.models.selection_summary import SelectionSummary
from bkbim.domain.ports import IElementReader


class _FakeElementReader(IElementReader):
    def __init__(self, count=0, raise_on_count=False):
        self._count = count
        self._raise_on_count = raise_on_count

    def count_selected(self):
        if self._raise_on_count:
            raise RuntimeError(u"boom")
        return SelectionSummary(count=self._count)


def _fresh_container(monkeypatch):
    container = ServiceContainer()
    monkeypatch.setattr(di, "get_container", lambda: container)
    return container


def test_run_returns_ok_result_with_summary(monkeypatch):
    container = _fresh_container(monkeypatch)
    container.register_instance(di.SERVICE_ELEMENT_READER, _FakeElementReader(count=3))

    result = count_selected_command.run()

    assert result.success is True
    assert result.value.count == 3
    assert "3" in result.message


def test_run_fails_gracefully_when_reader_not_registered(monkeypatch):
    _fresh_container(monkeypatch)

    result = count_selected_command.run()

    assert result.success is False
    assert "registered" in result.message


def test_run_wraps_reader_exceptions_as_failure(monkeypatch):
    container = _fresh_container(monkeypatch)
    container.register_instance(
        di.SERVICE_ELEMENT_READER, _FakeElementReader(count=0, raise_on_count=True)
    )

    result = count_selected_command.run()

    assert result.success is False
    assert result.value is None
