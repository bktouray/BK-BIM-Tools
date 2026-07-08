# -*- coding: utf-8 -*-
from bkbim.core.result import Result


def test_ok_defaults():
    r = Result.ok(value=42)
    assert r.success is True
    assert r.value == 42
    assert r.message == u""
    assert r.diagnostics == []


def test_fail_carries_message_and_diagnostics():
    r = Result.fail(u"boom", diagnostics=[u"detail 1", u"detail 2"])
    assert r.success is False
    assert r.value is None
    assert r.message == u"boom"
    assert r.diagnostics == [u"detail 1", u"detail 2"]


def test_repr_reflects_status():
    assert "OK" in repr(Result.ok())
    assert "FAIL" in repr(Result.fail(u"x"))
