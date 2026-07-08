# -*- coding: utf-8 -*-
"""Auto Dimension for Structural Elements (columns, footings) in plan, 2026-07-06.
Two modes, per product owner (corrected same day after first live use):

- "grid_and_column": EACH column gets its own independent dimension per axis
  (length + width) - near face -> grid -> far face, stopping there, never
  chained into the next column. Plus a separate overall string per row, further
  out (first column's outer face -> last column's outer face).
- "continuous_no_grid": column edge -> column edge -> ... across a row, no grid
  references at all - the grid is still used to group/order the row, it just
  never appears in the output dimension. Unaffected by the correction above.

Skips any plan that already has a matching dimension in the view (same
"safe to re-run as an update" convention as the other three dimensioning tools).

Zero Autodesk.Revit imports (ADR-0001) - unit-testable with fakes, same pattern as
the other app commands. Transaction ownership stays with the caller (pushbutton
entry point), per SAD Sec 4.4.
"""

from bkbim.core.logging import get_logger
from bkbim.core.result import Result
from bkbim.domain.dimensioning.column_grid_planner import plan_structural_dimensions

_logger = get_logger(u"bkbim.app.auto_structural_dimension")


def run(detected_elements, selection_reader, reference_provider, existing_dimension_checker,
        writer, failure_tracker, mode, standard):
    """Dimensions the columns/footings in `detected_elements` (grids + structural
    elements auto-detected from the current view) against the grids also present.

    :rtype: bkbim.core.result.Result wrapping
        {"created": int, "skipped": int, "already_existing": int}
    """
    try:
        elements, grids = selection_reader.read(detected_elements)
    except Exception as e:
        _logger.error(u"Failed to read detected elements: {0}", str(e))
        return Result.fail(u"Could not read the detected elements: {0}".format(str(e)))

    if not elements:
        return Result.fail(u"No columns or footings found in this view.")
    if not grids:
        return Result.fail(u"No grids found in this view.")

    unresolved = 0
    columns = []
    for element in elements:
        try:
            faces_x = reference_provider.faces_for(element.ref, u"x")
        except Exception as e:
            _logger.warning(u"faces_for failed for a {0} on axis x: {1}", element.category, str(e))
            faces_x = None
        try:
            faces_y = reference_provider.faces_for(element.ref, u"y")
        except Exception as e:
            _logger.warning(u"faces_for failed for a {0} on axis y: {1}", element.category, str(e))
            faces_y = None

        if faces_x is None and faces_y is None:
            unresolved += 1
            continue

        columns.append({
            u"axis_faces_x": faces_x, u"axis_faces_y": faces_y,
            u"center_x": element.center_x, u"center_y": element.center_y,
            u"min_x": element.min_x, u"max_x": element.max_x,
            u"min_y": element.min_y, u"max_y": element.max_y,
        })

    plans = plan_structural_dimensions(columns, grids, mode, standard)
    if not plans:
        return Result.fail(u"Nothing to dimension - no resolvable column/footing faces.")

    created = 0
    skipped = unresolved
    already_existing = 0

    for plan in plans:
        try:
            if existing_dimension_checker.already_exists(plan):
                already_existing += 1
                continue
        except Exception as e:
            _logger.warning(u"already_exists check failed: {0}", str(e))

        dim = writer.write(plan)
        if dim is None:
            skipped += 1
            continue
        failure_tracker.register_created(dim.Id)
        created += 1

    _logger.info(u"Auto Structural Dimension: {0} created, {1} already existing, {2} skipped",
                 created, already_existing, skipped)
    return Result.ok(
        value={"created": created, "skipped": skipped, "already_existing": already_existing},
        message=u"{0} dimension(s) created ({1} already existed, {2} skipped)".format(
            created, already_existing, skipped),
    )
