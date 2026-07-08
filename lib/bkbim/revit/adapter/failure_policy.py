# -*- coding: utf-8 -*-
"""IFailuresPreprocessor scoped to elements created by THIS command (SAD Sec 5).

v5's `DimFailureSwallower` deleted ANY element referenced by an Error-severity
failure, not just the dimension it had just tried to create - a real risk of
silently deleting a pre-existing wall/grid/column if Revit's failing-element-id list
ever pointed at one instead of the malformed dimension. This version only ever
deletes ids explicitly registered via `register_created()`; every other error is
resolved the default way instead, and warnings are dismissed as before.
"""

import clr

clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")

from Autodesk.Revit.DB import ElementId, FailureProcessingResult, FailureSeverity, IFailuresPreprocessor
from System.Collections.Generic import List

from bkbim.core.logging import get_logger
from bkbim.domain.dimensioning.ports import IFailureTracker

_logger = get_logger(u"bkbim.revit.failure_policy")


class ScopedFailurePolicy(IFailuresPreprocessor, IFailureTracker):
    def __init__(self):
        self._created_ids = set()
        self.warnings = []
        self.errors = []

    def register_created(self, element_id):
        """Call this immediately after DimensionWriter.write() succeeds, so this
        policy is allowed to delete that element if it later turns out malformed.
        """
        self._created_ids.add(element_id)

    def PreprocessFailures(self, failures_accessor):
        for failure in failures_accessor.GetFailureMessages():
            try:
                severity = failure.GetSeverity()
                description = failure.GetDescriptionText()

                if severity == FailureSeverity.Error:
                    self.errors.append(description)
                    failing_ids = failure.GetFailingElementIds()
                    scoped_ids = [i for i in failing_ids if i in self._created_ids]
                    if scoped_ids:
                        failures_accessor.DeleteElements(List[ElementId](scoped_ids))
                    else:
                        failures_accessor.ResolveFailure(failure)
                elif severity == FailureSeverity.Warning:
                    self.warnings.append(description)
                    failures_accessor.DeleteWarning(failure)
            except Exception as e:
                _logger.warning(u"Failure-policy handling error: {0}", str(e))
                try:
                    failures_accessor.ResolveFailure(failure)
                except Exception:
                    pass
        return FailureProcessingResult.Continue
