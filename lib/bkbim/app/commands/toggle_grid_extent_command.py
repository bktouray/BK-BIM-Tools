# -*- coding: utf-8 -*-
"""Toggles every grid in the current view between 2D (ViewSpecific - extent
only affects this view) and 3D (Model - extent shared across every view),
per product owner (2026-07-07): "create a utility that'll automatically
change all 3D grids to 2D grids and versi versa." A plain flip, not a
one-way conversion - each end is toggled independently based on its OWN
current state, so a grid with mismatched ends (one already 2D, one 3D) still
flips predictably instead of being silently normalized.

Zero Autodesk.Revit imports (ADR-0001) - unit-testable with fakes, same
pattern as the other app commands.
"""

from bkbim.core.logging import get_logger
from bkbim.core.result import Result
from bkbim.domain.models.grid_extent import toggle_extent

_logger = get_logger(u"bkbim.app.toggle_grid_extent")


def run(grids, writer):
    """Toggles the datum extent of every grid in `grids`.

    :param grids: list[bkbim.domain.models.grid_extent.GridExtentInfo]
    :param writer: bkbim.domain.grids.ports.IGridExtentWriter
    :rtype: bkbim.core.result.Result wrapping {"toggled": int, "failed": int}
    """
    if not grids:
        return Result.fail(u"No grids found in this view.")

    toggled = 0
    failed = 0
    for grid in grids:
        try:
            writer.set_extent(
                grid.ref, toggle_extent(grid.end0_extent), toggle_extent(grid.end1_extent))
            toggled += 1
        except Exception as e:
            _logger.warning(u"Failed to toggle a grid's extent: {0}", str(e))
            failed += 1

    _logger.info(u"Toggle Grid Extent: {0} toggled, {1} failed", toggled, failed)
    if failed:
        message = u"{0} grid(s) toggled between 2D/3D, {1} failed".format(toggled, failed)
    else:
        message = u"{0} grid(s) toggled between 2D/3D".format(toggled)
    return Result.ok(value={"toggled": toggled, "failed": failed}, message=message)
