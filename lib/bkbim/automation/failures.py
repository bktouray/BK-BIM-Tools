# -*- coding: utf-8 -*-
"""Failure handling so automation tools never stall on a modal warning.

Attach to a transaction before committing:

    from bkbim.automation.failures import swallow_warnings
    t.Start()
    swallow_warnings(t)
    ... do work ...
    t.Commit()
"""

from pyrevit import DB


class _SwallowWarnings(DB.IFailuresPreprocessor):
    """Delete all *warnings* automatically; let real errors surface."""

    def PreprocessFailures(self, failures_accessor):
        failures_accessor.DeleteAllWarnings()
        return DB.FailureProcessingResult.Continue


def swallow_warnings(transaction):
    opts = transaction.GetFailureHandlingOptions()
    opts.SetFailuresPreprocessor(_SwallowWarnings())
    opts.SetClearAfterRollback(True)
    transaction.SetFailureHandlingOptions(opts)
    return transaction
