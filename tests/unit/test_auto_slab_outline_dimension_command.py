# -*- coding: utf-8 -*-
"""Exercises auto_slab_outline_dimension_command against fakes - no Revit
involved, same pattern as the other app-command tests (SAD Sec 6).
"""
from bkbim.app.commands import auto_slab_outline_dimension_command
from bkbim.domain.models.outline_edge import OutlineEdge
from bkbim.domain.standards.standard import default_standard


def _rect_edges():
    return [
        OutlineEdge(ref=u"left", axis=u"x", coord=0.0, span_lo=0.0, span_hi=10.0, sign=-1),
        OutlineEdge(ref=u"top", axis=u"y", coord=10.0, span_lo=0.0, span_hi=10.0, sign=1),
        OutlineEdge(ref=u"right", axis=u"x", coord=10.0, span_lo=0.0, span_hi=10.0, sign=1),
        OutlineEdge(ref=u"bottom", axis=u"y", coord=0.0, span_lo=0.0, span_hi=10.0, sign=-1),
    ]


class _FakeReferenceProvider(object):
    def __init__(self, edges_by_slab, fail_on=None):
        self._edges_by_slab = edges_by_slab
        self._fail_on = fail_on or set()

    def outline_edges_for(self, slab):
        if slab in self._fail_on:
            raise RuntimeError("boom")
        return self._edges_by_slab.get(slab, [])


class _FakeDimension(object):
    def __init__(self, dim_id):
        self.Id = dim_id


class _FakeWriter(object):
    def __init__(self, always_fail=False):
        self._counter = 0
        self._always_fail = always_fail

    def write(self, plan):
        if self._always_fail:
            return None
        self._counter += 1
        return _FakeDimension(self._counter)


class _FakeFailureTracker(object):
    def __init__(self):
        self.registered = []

    def register_created(self, element_id):
        self.registered.append(element_id)


class _FakeExistingDimensionChecker(object):
    def __init__(self, always_exists=False, raise_error=False):
        self._always_exists = always_exists
        self._raise_error = raise_error

    def already_exists(self, plan):
        if self._raise_error:
            raise RuntimeError("boom")
        return self._always_exists


def _run(slabs, edges_by_slab, writer=None, checker=None, fail_on=None):
    provider = _FakeReferenceProvider(edges_by_slab, fail_on=fail_on)
    return auto_slab_outline_dimension_command.run(
        slabs, provider, checker or _FakeExistingDimensionChecker(),
        writer or _FakeWriter(), _FakeFailureTracker(), default_standard())


def test_no_slabs_fails_with_clear_message():
    result = _run([], {})
    assert result.success is False
    assert "No slabs" in result.message


def test_rectangular_slab_creates_four_dimensions():
    result = _run(["S1"], {"S1": _rect_edges()})
    assert result.success
    assert result.value["created"] == 4
    assert result.value["already_existing"] == 0
    assert result.value["skipped"] == 0


def test_slab_with_unresolved_outline_is_skipped_not_fatal():
    # Fewer than 4 edges (e.g. faces_for failed) - counted as skipped, not an error.
    result = _run(["S1"], {"S1": _rect_edges()[:2]})
    assert result.success is False
    assert "Nothing to dimension" in result.message


def test_one_bad_slab_does_not_block_the_others():
    result = _run(["S1", "S2"], {"S1": [], "S2": _rect_edges()})
    assert result.success
    assert result.value["created"] == 4
    assert result.value["skipped"] == 1  # S1 unresolved


def test_outline_edges_for_exception_counts_as_skipped():
    result = _run(["S1", "S2"], {"S2": _rect_edges()}, fail_on={"S1"})
    assert result.success
    assert result.value["created"] == 4
    assert result.value["skipped"] == 1


def test_already_existing_dimensions_are_not_recreated():
    result = _run(["S1"], {"S1": _rect_edges()}, checker=_FakeExistingDimensionChecker(always_exists=True))
    assert result.success
    assert result.value["created"] == 0
    assert result.value["already_existing"] == 4


def test_writer_refusal_counts_as_skipped():
    result = _run(["S1"], {"S1": _rect_edges()}, writer=_FakeWriter(always_fail=True))
    assert result.success
    assert result.value["created"] == 0
    assert result.value["skipped"] == 4
