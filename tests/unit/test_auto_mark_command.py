# -*- coding: utf-8 -*-
"""Exercises auto_mark_command against a fake writer - no Revit involved,
same convention as the dimensioning commands' tests. mark_planner.py already
has its own thorough sort/numbering coverage (test_mark_planner.py); this
file focuses on the command's own responsibilities: aggregating counts,
tolerating per-instance write failures, and failing cleanly when nothing
would be marked.
"""
from bkbim.app.commands import auto_mark_command
from bkbim.domain.models.mark_family_group import MarkFamilyGroup
from bkbim.domain.models.mark_type_group import MarkTypeGroup


class _FakeWriter(object):
    def __init__(self, fail_refs=None, raise_on=None):
        self._fail_refs = fail_refs or set()
        self._raise_on = raise_on or set()
        self.written = []

    def write(self, ref, mark_value):
        if ref in self._raise_on:
            raise RuntimeError("boom")
        if ref in self._fail_refs:
            return False
        self.written.append((ref, mark_value))
        return True


def _group():
    t = MarkTypeGroup("900x2100", 900, 2100, ["a", "b"])
    return MarkFamilyGroup("Single-Flush", [t])


def test_marks_every_instance_and_reports_counts():
    writer = _FakeWriter()

    result = auto_mark_command.run([_group()], {"Single-Flush": "D"}, writer)

    assert result.success
    assert result.value == {"marked": 2, "failed": 0, "families": 1}
    # both instances share the same type, so they share the same mark
    # (product owner: "if the family name and type is the same, they
    # should have the same mark").
    assert writer.written == [("a", "D1"), ("b", "D1")]


def test_failed_writes_are_counted_not_fatal():
    writer = _FakeWriter(fail_refs={"a"})

    result = auto_mark_command.run([_group()], {"Single-Flush": "D"}, writer)

    assert result.success
    assert result.value == {"marked": 1, "failed": 1, "families": 1}


def test_writer_exception_counts_as_a_failure_not_a_crash():
    writer = _FakeWriter(raise_on={"a"})

    result = auto_mark_command.run([_group()], {"Single-Flush": "D"}, writer)

    assert result.success
    assert result.value == {"marked": 1, "failed": 1, "families": 1}


def test_fails_cleanly_when_no_family_has_a_prefix():
    writer = _FakeWriter()

    result = auto_mark_command.run([_group()], {}, writer)

    assert not result.success
    assert writer.written == []


def test_fails_cleanly_when_every_write_fails():
    writer = _FakeWriter(fail_refs={"a", "b"})

    result = auto_mark_command.run([_group()], {"Single-Flush": "D"}, writer)

    assert not result.success
