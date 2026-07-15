# -*- coding: utf-8 -*-
"""Fitting selection for sanitary drainage (MEP_SAD.md Sec 6).

Unlike the sizing/slope tables in this package, the ONE rule this module
encodes is not a placeholder needing verification: a branch joining a sanitary
drainage run must always enter through a sweep/oblique fitting (45 degree wye)
rather than a square (90 degree) tee, to avoid creating a flow obstruction/
blockage point. This is a well-established plumbing principle independent of
which sizing standard is in use, not something specific to BS EN 12056-2.

What IS still unverified: which fitting angles/families are actually available
in the product owner's Revit fitting catalogue - that needs the Piping-API
creation spike (MEP_SAD.md Sec 6) before RevitPipeWriter can trust this
module's output against real family symbols.
"""
from bkbim.domain.mep.models.routing_plan import FittingPlan

_STRAIGHT_TOLERANCE_DEG = 2.0


def select_fitting(at_point, diameter_before_mm, diameter_after_mm,
                    direction_change_deg=0.0, is_branch_junction=False):
    """Returns a FittingPlan, or None if the joint needs no fitting at all
    (straight run, same diameter, no branch).
    """
    if is_branch_junction:
        return FittingPlan(
            kind=FittingPlan.KIND_WYE_45,
            at_point=at_point,
            diameter_mm=max(diameter_before_mm, diameter_after_mm),
            angle_deg=45.0)

    if diameter_before_mm != diameter_after_mm:
        return FittingPlan(
            kind=FittingPlan.KIND_REDUCER,
            at_point=at_point,
            diameter_mm=max(diameter_before_mm, diameter_after_mm))

    if abs(direction_change_deg) > _STRAIGHT_TOLERANCE_DEG:
        return FittingPlan(
            kind=FittingPlan.KIND_ELBOW,
            at_point=at_point,
            diameter_mm=diameter_after_mm,
            angle_deg=direction_change_deg)

    return None
