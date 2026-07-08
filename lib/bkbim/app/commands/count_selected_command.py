# -*- coding: utf-8 -*-
"""Walking-skeleton command (Phase 0): count the current Revit selection.

Template for every future app-layer command: resolve dependencies via DI, call the
domain port, wrap the outcome in a Result, never let a raw exception escape (SAD
Sec 4.4 / Sec 5 error strategy). Both the ribbon pushbutton and the MCP tool call
this function - never each other - so they share one code path.
"""

from bkbim.core import di
from bkbim.core.errors import BKBimError
from bkbim.core.logging import get_logger
from bkbim.core.result import Result

_logger = get_logger(u"bkbim.app.count_selected")


def run():
    """Executes the Count Selected Elements use-case.

    :rtype: bkbim.core.result.Result
    """
    container = di.get_container()
    if not container.has(di.SERVICE_ELEMENT_READER):
        return Result.fail(u"No element reader registered - is the extension wired up?")

    reader = container.resolve(di.SERVICE_ELEMENT_READER)

    try:
        summary = reader.count_selected()
    except BKBimError as e:
        _logger.error(u"Count selected failed: {0}", str(e))
        return Result.fail(str(e))
    except Exception as e:
        _logger.error(u"Count selected failed unexpectedly: {0}", str(e))
        return Result.fail(u"Unexpected error: {0}".format(str(e)))

    _logger.info(u"Counted {0} selected elements", summary.count)
    return Result.ok(value=summary, message=u"{0} element(s) selected".format(summary.count))
