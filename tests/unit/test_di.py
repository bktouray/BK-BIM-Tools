# -*- coding: utf-8 -*-
import pytest

from bkbim.core.di import ServiceContainer


def test_register_instance_resolves_same_object():
    container = ServiceContainer()
    sentinel = object()
    container.register_instance("thing", sentinel)

    assert container.resolve("thing") is sentinel


def test_register_factory_invoked_each_resolve():
    container = ServiceContainer()
    calls = []

    def factory():
        calls.append(1)
        return object()

    container.register_factory("thing", factory)
    a = container.resolve("thing")
    b = container.resolve("thing")

    assert a is not b
    assert len(calls) == 2


def test_resolve_unregistered_key_raises():
    container = ServiceContainer()
    with pytest.raises(KeyError):
        container.resolve("missing")


def test_has_reflects_registration():
    container = ServiceContainer()
    assert container.has("thing") is False
    container.register_instance("thing", object())
    assert container.has("thing") is True
