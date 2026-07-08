# -*- coding: utf-8 -*-
"""Minimal service locator (SAD Sec 4.1).

Modules ask for services (settings, logger, adapters like IElementReader) instead of
constructing them directly, so an implementation can be swapped - e.g. a real
ILicenseService replacing the Phase-1 no-op - without touching call sites.
"""

# Well-known service keys. Add one constant per registered service; keeps resolve()
# call sites free of magic strings.
SERVICE_ELEMENT_READER = u"element_reader"


class ServiceContainer(object):
    """Name -> instance/factory registry."""

    def __init__(self):
        self._instances = {}
        self._factories = {}

    def register_instance(self, key, instance):
        self._instances[key] = instance

    def register_factory(self, key, factory):
        """factory: zero-arg callable producing a new instance each time it's resolved."""
        self._factories[key] = factory

    def resolve(self, key):
        if key in self._instances:
            return self._instances[key]
        if key in self._factories:
            return self._factories[key]()
        raise KeyError(u"No service registered for '{0}'".format(key))

    def has(self, key):
        return key in self._instances or key in self._factories


_container = ServiceContainer()


def get_container():
    """Returns the process-wide ServiceContainer singleton."""
    return _container
