# -*- coding: utf-8 -*-
"""Auto Grid Dimension: dimensions every grid in the selection with two strings per
side (sequential + overall), on all sides - matches the convention confirmed against
real reference drawings (product owner's GROUND.pdf / str.pdf, 2026-07-05).

Skips any plan that already has a matching dimension in the view (product owner
feedback 2026-07-05: re-running this command should be safe to use as an "update" -
only add what's missing, never create overlapping duplicates).

Zero Autodesk.Revit imports (ADR-0001) - unit-testable with fakes, same pattern as
auto_dimension_command.py. Transaction ownership stays with the caller (pushbutton
entry point), per SAD Sec 4.4.
"""

from bkbim.core.logging import get_logger
from bkbim.core.result import Result
from bkbim.domain.dimensioning.grid_chain_planner import compute_bounding_span, plan_grid_chains

_logger = get_logger(u"bkbim.app.auto_grid_dimension")


def run(selected_elements, selection_reader, existing_dimension_checker, writer, failure_tracker, standard):
    """Dimensions the grids in `selected_elements` (a pre-picked list of Revit
    elements/grids) against the extent of whatever else was selected alongside them.
    A string that already has a matching dimension in the view is skipped, not
    duplicated.

    :rtype: bkbim.core.result.Result wrapping
        {"created": int, "skipped": int, "already_existing": int}
    """
    try:
        elements, grids = selection_reader.read(selected_elements)
    except Exception as e:
        _logger.error(u"Failed to read selection: {0}", str(e))
        return Result.fail(u"Could not read the selection: {0}".format(str(e)))

    if not grids:
        return Result.fail(u"No grids found in the selection.")

    x_span, y_span = compute_bounding_span(elements, grids)
    plans = plan_grid_chains(grids, x_span, y_span, standard)

    if not plans:
        return Result.fail(u"Need at least 2 grids of the same orientation to dimension.")

    created = 0
    skipped = 0
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

    _logger.info(u"Auto Grid Dimension: {0} created, {1} already existing, {2} skipped",
                 created, already_existing, skipped)
    return Result.ok(
        value={"created": created, "skipped": skipped, "already_existing": already_existing},
        message=u"{0} grid dimension(s) created ({1} already existed, {2} skipped)".format(
            created, already_existing, skipped),
    )
