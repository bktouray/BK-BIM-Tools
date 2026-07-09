# -*- coding: utf-8 -*-
"""Auto Tag: tags every element in `elements` that doesn't already have a tag
of the chosen category in the target view. Mirrors the "skip already placed"
convention the dimensioning tools use, so re-running is safe.

Zero Autodesk.Revit imports (ADR-0001) - unit-testable with fakes, same
pattern as the other app commands. Transaction ownership stays with the
caller (lib/bkbim/revit/adapter/tag_flow.py), per SAD Sec 4.4.
"""

from bkbim.core.logging import get_logger
from bkbim.core.result import Result

_logger = get_logger(u"bkbim.app.auto_tag")


def run(elements, already_tagged_checker, writer):
    """elements: opaque list of Revit elements (already filtered to the
    chosen category + tag type by the adapter, see tag_type_reader.py).
    already_tagged_checker: port with is_tagged(element) -> bool.
    writer: port with write(element) -> opaque tag handle, or None if refused.

    :rtype: bkbim.core.result.Result wrapping
        {"tagged": int, "already_tagged": int, "failed": int}
    """
    if not elements:
        return Result.fail(u"No untagged elements found in this view.")

    tagged = 0
    already_tagged = 0
    failed = 0

    for element in elements:
        try:
            if already_tagged_checker.is_tagged(element):
                already_tagged += 1
                continue
        except Exception as e:
            _logger.warning(u"is_tagged check failed: {0}", str(e))

        try:
            tag = writer.write(element)
        except Exception as e:
            _logger.warning(u"Tag write failed: {0}", str(e))
            tag = None

        if tag is None:
            failed += 1
        else:
            tagged += 1

    _logger.info(u"Auto Tag: {0} tagged, {1} already tagged, {2} failed",
                 tagged, already_tagged, failed)

    if tagged == 0 and failed == 0:
        return Result.fail(u"Nothing to tag - every element already has a tag.")

    return Result.ok(
        value={"tagged": tagged, "already_tagged": already_tagged, "failed": failed},
        message=u"{0} tag(s) placed ({1} already tagged{2}).".format(
            tagged, already_tagged,
            u", {0} failed".format(failed) if failed else u""),
    )
