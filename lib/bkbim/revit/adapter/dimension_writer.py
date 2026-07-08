# -*- coding: utf-8 -*-
"""Turns a DimensionPlan into a real Revit Dimension (SAD Sec 4.3).

Does NOT own the transaction - the caller (app command, Stage 6) wraps calls to this
in a Transaction, per SAD Sec 4.4 (app owns the transaction boundary, not the
adapter). This lets one command batch many plans into a single transaction/failure
policy, matching how ScopedFailurePolicy (failure_policy.py) is meant to be used.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import Line, ReferenceArray, XYZ

from bkbim.core.logging import get_logger
from bkbim.domain.dimensioning.ports import IDimensionWriter
from bkbim.domain.models.dimension_plan import DimensionPlan

_logger = get_logger(u"bkbim.revit.dimension_writer")

# The 2 EXTRA strings an exterior wall gets on top of its normal wall-run
# string (product owner, 2026-07-08: "select a specific dimension style
# for exterior walls if i choose it") - kept separate from the main style
# so they can visually stand out from ordinary wall-run dimensioning.
_EXTERIOR_PERIMETER_KINDS = (DimensionPlan.KIND_WALL_PERPENDICULAR_CHAIN, DimensionPlan.KIND_WALL_OVERALL)


def _line_for_plan(plan):
    if plan.axis == u"x":
        p0 = XYZ(plan.line_coord_lo, plan.perp_pos, 0)
        p1 = XYZ(plan.line_coord_hi, plan.perp_pos, 0)
    else:
        p0 = XYZ(plan.perp_pos, plan.line_coord_lo, 0)
        p1 = XYZ(plan.perp_pos, plan.line_coord_hi, 0)
    return Line.CreateBound(p0, p1)


class DimensionWriter(IDimensionWriter):
    def __init__(self, doc, view, dimension_type=None, exterior_perimeter_dimension_type=None):
        """dimension_type: an Autodesk.Revit.DB.DimensionType, or None to use
        whatever the document's default active type is (matches prior behavior).
        Lets the user pick a specific dimension style from the options UI.

        exterior_perimeter_dimension_type: an Autodesk.Revit.DB.DimensionType
        used instead of `dimension_type`, but ONLY for the 2 extra strings an
        exterior wall gets (the perpendicular-wall chain and the overall
        string) - every other plan, including an exterior wall's own normal
        wall-run string, keeps using `dimension_type`. None (the default)
        means "same as the main style," i.e. no override.
        """
        self._doc = doc
        self._view = view
        self._dimension_type = dimension_type
        self._exterior_perimeter_dimension_type = exterior_perimeter_dimension_type

    def write(self, plan):
        """Creates a real Dimension from `plan`.

        Returns the Dimension, or None if Revit refused to create it (e.g.
        degenerate/duplicate references) - this is a routine, expected outcome the
        caller counts as "skipped," not an exception to propagate.
        """
        if plan is None or len(plan.refs) < 2:
            return None

        ref_array = ReferenceArray()
        for ref in plan.refs:
            ref_array.Append(ref)

        dimension_type = self._dimension_type
        if plan.kind in _EXTERIOR_PERIMETER_KINDS and self._exterior_perimeter_dimension_type is not None:
            dimension_type = self._exterior_perimeter_dimension_type

        try:
            # _line_for_plan() itself can throw (e.g. Revit's "Curve length is
            # too small for Revit's tolerance" for a near-zero-length span, a
            # real case hit live by a degenerate slab axis extent) - this must
            # be caught here too, not just around NewDimension, otherwise one
            # bad plan crashes the entire run instead of just being skipped.
            line = _line_for_plan(plan)
            if dimension_type is not None:
                return self._doc.Create.NewDimension(
                    self._view, line, ref_array, dimension_type)
            return self._doc.Create.NewDimension(self._view, line, ref_array)
        except Exception as e:
            _logger.warning(u"NewDimension failed for {0} plan: {1}", plan.kind, str(e))
            return None
