# -*- coding: utf-8 -*-
"""Minimum/maximum gravity slope checks for a sanitary run (MEP_SAD.md Sec 5).
Pure logic - path_planner calls this to turn an implied slope into a
pass/fail + warning, never to auto-correct elevations.
"""


def min_slope_percent_for_dn(dn_mm, standard):
    """Smallest DN-band whose max_dn_mm >= dn_mm; None if dn_mm exceeds every
    band (an oversized run this table doesn't cover - flag it, don't guess).
    """
    for max_dn_mm, min_slope in sorted(standard.mep_min_slope_table_percent, key=lambda t: t[0]):
        if dn_mm <= max_dn_mm:
            return min_slope
    return None


def check_slope(slope_percent, dn_mm, standard):
    """Returns a list of warning strings (empty = OK). slope_percent may be
    negative (falling away from the fixture, as drainage always should) or
    positive depending on the caller's sign convention - callers pass the
    magnitude; direction correctness is the path planner's job, not this
    function's.
    """
    warnings = []
    min_slope = min_slope_percent_for_dn(dn_mm, standard)
    if min_slope is None:
        warnings.append(
            u"No minimum-slope data for DN{0}mm - verify manually.".format(dn_mm))
    elif slope_percent < min_slope:
        warnings.append(
            u"Slope {0:.2f}% is below the DN{1}mm minimum of {2:.2f}%.".format(
                float(slope_percent), dn_mm, float(min_slope)))
    if standard.mep_max_slope_percent is not None and slope_percent > standard.mep_max_slope_percent:
        warnings.append(
            u"Slope {0:.2f}% exceeds the configured maximum of {1:.2f}%.".format(
                float(slope_percent), float(standard.mep_max_slope_percent)))
    return warnings
