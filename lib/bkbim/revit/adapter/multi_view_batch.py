# -*- coding: utf-8 -*-
"""Shared batch-execution helper for multi-view dimensioning flows (grids,
walls, structural/slab) - extracted 2026-07-08 once a 3rd flow needed the
exact same "TransactionGroup if more than one view, plain single view
otherwise, combine per-view (name, message) results into one alert" shape
(ADR-0002: shared helper once a 2nd/3rd consumer exists - already applied
this session for structural_dimension_flow.py and wall_dimension_flow.py).
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import TransactionGroup
from bkbim.ui.views.result_dialog import show_result


def run_across_views(doc, target_views, transaction_label, per_view_fn):
    """per_view_fn(view) -> (view_name, message); each call owns its own
    child Transaction and rollback-on-failure. Wraps a >1-view batch in one
    TransactionGroup so it undoes as a single step, but one view's failure
    doesn't roll back the others. A single view skips the group entirely -
    zero behavior change for the common case.
    """
    if len(target_views) > 1:
        tg = TransactionGroup(doc, transaction_label)
        tg.Start()
        results = [per_view_fn(v) for v in target_views]
        tg.Assimilate()
        return results
    return [per_view_fn(target_views[0])]


def alert_batch_results(results, title):
    """Shows one combined alert for a multi-view batch (each line prefixed
    with its view's name), or the single result exactly as-is (no prefix)
    when there was only one view - matches each flow's original single-view
    alert text unchanged.
    """
    if len(results) > 1:
        show_result(
            title,
            u"\n\n".join(u"{0}: {1}".format(name, msg) for name, msg in results))
    else:
        _, msg = results[0]
        show_result(title, msg)
