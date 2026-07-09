# -*- coding: utf-8 -*-
"""Auto Mark: assigns the instance Mark parameter across every placed
element of one category, largest type first per family, per-family prefix
(e.g. D1, D2... for "Single-Flush" doors, SD1, SD2... for "Sliding-Door").

Zero Autodesk.Revit imports (ADR-0001) - unit-testable with fakes, same
pattern as the other app commands. Transaction ownership stays with the
caller (lib/bkbim/revit/adapter/mark_flow.py), per SAD Sec 4.4.
"""

from bkbim.core.logging import get_logger
from bkbim.core.result import Result
from bkbim.domain.marking.mark_planner import plan_marks

_logger = get_logger(u"bkbim.app.auto_mark")


def run(family_groups, prefixes, writer):
    """family_groups: list of MarkFamilyGroup, as read by mark_type_reader.
    prefixes: dict {family_name: prefix string}; a family with no/blank
    prefix is skipped (see mark_planner.plan_marks).
    writer: port with write(ref, mark_value) -> bool (see mark_writer.py).

    :rtype: bkbim.core.result.Result wrapping
        {"marked": int, "failed": int, "families": int}
    """
    assignments = plan_marks(family_groups, prefixes)
    if not assignments:
        return Result.fail(u"Nothing to mark - assign a prefix to at least one family.")

    marked = 0
    failed = 0
    for ref, mark_value in assignments:
        try:
            ok = writer.write(ref, mark_value)
        except Exception as e:
            _logger.warning(u"Mark write failed: {0}", str(e))
            ok = False
        if ok:
            marked += 1
        else:
            failed += 1

    marked_families = len(set(
        family_group.family_name for family_group in family_groups
        if prefixes.get(family_group.family_name)))

    _logger.info(u"Auto Mark: {0} marked, {1} failed, across {2} families",
                 marked, failed, marked_families)

    if marked == 0:
        return Result.fail(u"No marks could be written - {0} failed.".format(failed))

    return Result.ok(
        value={"marked": marked, "failed": failed, "families": marked_families},
        message=u"{0} instance(s) marked across {1} family/families.{2}".format(
            marked, marked_families,
            u" ({0} failed)".format(failed) if failed else u""),
    )
