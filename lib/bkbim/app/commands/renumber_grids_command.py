# -*- coding: utf-8 -*-
"""Renumbers every straight grid in the model.

Zero Autodesk.Revit imports (ADR-0001) - unit-testable with fakes, same
pattern as the other app commands.
"""

from bkbim.core.logging import get_logger
from bkbim.core.result import Result
from bkbim.domain.models.grid_position import plan_renumber

_logger = get_logger(u"bkbim.app.renumber_grids")


def run(grids, writer, scheme=None):
    """Renumbers `grids` per the plan from `plan_renumber`.

    Revit enforces unique grid names at all times, so applying final names
    directly can collide with another grid's CURRENT name mid-loop (e.g.
    swapping "1" and "3"). Every grid is first staged through a unique
    temporary name, then final names are applied once no collision is
    possible - a grid that fails to stage is skipped entirely (never gets a
    final name), so it's never left stuck on a temporary name.

    :param grids: list[bkbim.domain.models.grid_position.GridPositionInfo]
    :param writer: bkbim.domain.grids.ports.IGridRenumberWriter
    :param scheme: optional bkbim.domain.models.grid_position.SCHEME_* value
    :rtype: bkbim.core.result.Result wrapping {"renamed": int, "failed": int}
    """
    if not grids:
        return Result.fail(u"No grids found in this project.")

    plan = plan_renumber(grids, scheme=scheme)
    if not plan:
        return Result.fail(
            u"No vertical or horizontal grids found to renumber "
            u"(only angled/curved grids present).")

    failed = 0
    staged = []
    for i, (grid_ref, new_name) in enumerate(plan):
        temp_name = u"__renumber_tmp_{0}__".format(i)
        try:
            writer.set_name(grid_ref, temp_name)
            staged.append((grid_ref, new_name))
        except Exception as e:
            _logger.warning(u"Failed to stage a grid for renumbering: {0}", str(e))
            failed += 1

    renamed = 0
    for grid_ref, new_name in staged:
        try:
            writer.set_name(grid_ref, new_name)
            renamed += 1
        except Exception as e:
            _logger.warning(u"Failed to apply a grid's final name: {0}", str(e))
            failed += 1

    _logger.info(u"Renumber Grids: {0} renamed, {1} failed", renamed, failed)
    if failed:
        message = u"{0} grid(s) renumbered, {1} failed".format(renamed, failed)
    else:
        message = u"{0} grid(s) renumbered".format(renamed)
    return Result.ok(value={"renamed": renamed, "failed": failed}, message=message)
