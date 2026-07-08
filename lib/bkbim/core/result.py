# -*- coding: utf-8 -*-
"""Result envelope crossing every layer boundary (SAD Sec 4.1 / Sec 5 error strategy).

Domain raises typed errors; app catches them and returns a Result instead of letting
exceptions cross into the UI or MCP layers.
"""


class Result(object):
    """Outcome of a command: success flag, value, user-facing message, diagnostics."""

    def __init__(self, success, value=None, message=u"", diagnostics=None):
        self.success = success
        self.value = value
        self.message = message
        self.diagnostics = diagnostics or []

    @classmethod
    def ok(cls, value=None, message=u""):
        return cls(True, value=value, message=message)

    @classmethod
    def fail(cls, message, diagnostics=None):
        return cls(False, value=None, message=message, diagnostics=diagnostics)

    def __repr__(self):
        status = u"OK" if self.success else u"FAIL"
        return u"<Result {0}: {1}>".format(status, self.message)
