# -*- coding: utf-8 -*-
"""Foot <-> millimetre conversion. Revit's internal length unit is decimal feet.

Kept deliberately minimal (mm/ft only) - add another unit system when a second one
is actually needed (ADR-0002: no speculative abstraction).
"""

MM_PER_FOOT = 304.8


def mm_to_ft(mm):
    return mm / MM_PER_FOOT


def ft_to_mm(ft):
    return ft * MM_PER_FOOT
