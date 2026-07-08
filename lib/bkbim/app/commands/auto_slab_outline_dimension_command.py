# -*- coding: utf-8 -*-
"""Auto Dimension for Slab Outlines - "All edges of the slab" mode, true
perimeter tracing (2026-07-07). Reads each slab's REAL boundary edges (not
its bounding box), then dimensions every one of them via
`slab_outline_planner.plan_slab_outline_dimensions`.

Skips any plan that already has a matching dimension in the view (same
"safe to re-run as an update" convention as the other dimensioning tools).

Zero Autodesk.Revit imports (ADR-0001) - unit-testable with fakes, same
pattern as the other app commands. Transaction ownership stays with the
caller (pushbutton entry point), per SAD Sec 4.4.
"""

from bkbim.core.logging import get_logger
from bkbim.core.result import Result
from bkbim.domain.dimensioning.slab_outline_planner import plan_slab_outline_dimensions

_logger = get_logger(u"bkbim.app.auto_slab_outline_dimension")


def run(slabs, reference_provider, existing_dimension_checker, writer, failure_tracker, standard):
    """Dimensions every real boundary edge of every slab in `slabs`.

    :rtype: bkbim.core.result.Result wrapping
        {"created": int, "skipped": int, "already_existing": int}
    """
    if not slabs:
        return Result.fail(u"No slabs found in this view.")

    unresolved = 0
    all_edges = []
    for slab in slabs:
        try:
            edges = reference_provider.outline_edges_for(slab)
        except Exception as e:
            _logger.warning(u"outline_edges_for failed for a slab: {0}", str(e))
            edges = []
        if len(edges) < 4:
            unresolved += 1
            continue
        all_edges.append(edges)

    plans = plan_slab_outline_dimensions(all_edges, standard)
    if not plans:
        return Result.fail(u"Nothing to dimension - no resolvable slab outline edges.")

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

    _logger.info(u"Auto Slab Outline Dimension: {0} created, {1} already existing, {2} skipped",
                 created, already_existing, skipped)
    return Result.ok(
        value={"created": created, "skipped": skipped, "already_existing": already_existing},
        message=u"{0} dimension(s) created ({1} already existed, {2} skipped)".format(
            created, already_existing, skipped),
    )
