# -*- coding: utf-8 -*-
"""Shared master filter use case, callable from the ribbon or automation."""
from bkbim.core.result import Result
from bkbim.domain.filtering.rules import filter_records


def run(records, criteria, rules, mode, value_reader):
    try:
        rows = filter_records(records, criteria, rules, mode, value_reader)
        return Result.ok(rows, u"{0} matching element(s).".format(len(rows)))
    except Exception as exc:
        return Result.fail(u"Could not filter elements: {0}".format(exc))
