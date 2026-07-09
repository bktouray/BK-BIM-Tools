# -*- coding: utf-8 -*-
"""Exercises auto_tag_command against fakes - no Revit involved, same
pattern as the other app-command tests (SAD Sec 6).
"""
from bkbim.app.commands import auto_tag_command


class _FakeChecker(object):
    def __init__(self, tagged=None, error_on=None):
        self._tagged = tagged or set()
        self._error_on = error_on or set()

    def is_tagged(self, element):
        if element in self._error_on:
            raise RuntimeError("boom")
        return element in self._tagged


class _FakeWriter(object):
    def __init__(self, fail_on=None):
        self.calls = []
        self._fail_on = fail_on or set()

    def write(self, element):
        self.calls.append(element)
        if element in self._fail_on:
            return None
        return u"TAG:" + element


def test_no_elements_fails_with_a_clear_message():
    result = auto_tag_command.run([], _FakeChecker(), _FakeWriter())
    assert not result.success
    assert "No untagged elements" in result.message


def test_tags_every_element_not_already_tagged():
    writer = _FakeWriter()
    result = auto_tag_command.run(["E1", "E2"], _FakeChecker(), writer)

    assert result.success
    assert writer.calls == ["E1", "E2"]
    assert result.value["tagged"] == 2
    assert result.value["already_tagged"] == 0
    assert result.value["failed"] == 0


def test_skips_already_tagged_elements_without_writing():
    writer = _FakeWriter()
    checker = _FakeChecker(tagged={"E1"})
    result = auto_tag_command.run(["E1", "E2"], checker, writer)

    assert result.success
    assert writer.calls == ["E2"]
    assert result.value["tagged"] == 1
    assert result.value["already_tagged"] == 1


def test_a_refused_write_is_counted_as_failed_but_does_not_stop_the_others():
    writer = _FakeWriter(fail_on={"E1"})
    result = auto_tag_command.run(["E1", "E2"], _FakeChecker(), writer)

    assert result.success
    assert result.value["tagged"] == 1
    assert result.value["failed"] == 1
    assert writer.calls == ["E1", "E2"]


def test_a_checker_error_is_treated_as_not_tagged_rather_than_stopping_the_run():
    writer = _FakeWriter()
    checker = _FakeChecker(error_on={"E1"})
    result = auto_tag_command.run(["E1", "E2"], checker, writer)

    assert result.success
    assert writer.calls == ["E1", "E2"]
    assert result.value["tagged"] == 2


def test_everything_already_tagged_fails_with_a_clear_message():
    writer = _FakeWriter()
    checker = _FakeChecker(tagged={"E1", "E2"})
    result = auto_tag_command.run(["E1", "E2"], checker, writer)

    assert not result.success
    assert writer.calls == []
    assert "every element already has a tag" in result.message
