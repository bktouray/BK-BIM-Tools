# -*- coding: utf-8 -*-
"""Named profile of dimensioning offsets/tolerances.

Replaces the AutoDims v5 script's module-level constants (OFFSET_1_MM, ZERO_TOL_MM,
...) with per-Standard fields, so BS/ISO/AIA/custom profiles are data, not code
(PHASE_1_PLAN Sec 3). Default values below are a reasonable starting point carried
over as plain numbers - not verified against any published standard - flag for
review before Phase 3 (Standards + Presets GA).
"""


class Standard(object):
    def __init__(self, name,
                 offset_first_mm=300.0,
                 wall_perimeter_gap_mm=700.0,
                 grid_chain_offset_mm=300.0,
                 grid_chain_gap_mm=700.0,
                 structural_chain_offset_mm=300.0,
                 structural_chain_gap_mm=700.0,
                 zero_tolerance_mm=5.0,
                 intersect_tolerance_mm=50.0,
                 max_snap_distance_mm=10000.0,
                 collision_shift_mm=300.0,
                 collision_max_passes=3,
                 default_side=-1):
        self.name = name
        self.offset_first_mm = offset_first_mm
        # Spacing between each of an exterior wall's 3 perimeter dimension
        # strings (2026-07-07) - was the long-unused "offset_second_mm"
        # reserved field, finally given a real purpose. Applied twice: once
        # between String 1 (openings) and String 2 (perpendicular walls),
        # again between String 2 and String 3 (overall). Default lowered
        # from the original 1400mm same day - product owner tried it live
        # and found that "wayyy too much gap"; also now user-adjustable per
        # run via the options window, not just this code-level default.
        self.wall_perimeter_gap_mm = wall_perimeter_gap_mm
        self.grid_chain_offset_mm = grid_chain_offset_mm
        self.grid_chain_gap_mm = grid_chain_gap_mm
        # Auto Dimension for Structural Elements (2026-07-06): kept independent
        # of grid_chain_offset/gap so tuning Grid Dimensions' spacing never
        # silently changes column/footing dimension spacing, and vice versa.
        self.structural_chain_offset_mm = structural_chain_offset_mm
        self.structural_chain_gap_mm = structural_chain_gap_mm
        self.zero_tolerance_mm = zero_tolerance_mm
        self.intersect_tolerance_mm = intersect_tolerance_mm
        self.max_snap_distance_mm = max_snap_distance_mm
        self.collision_shift_mm = collision_shift_mm
        self.collision_max_passes = collision_max_passes
        # Phase 1 Stage 3 keeps side-picking deliberately non-clever: every
        # dimension goes on this fixed side (-1 = below/left, +1 = above/right).
        # v5's per-element side-picking heuristic is not carried over; revisit only
        # if simple fixed-side placement proves wrong in practice.
        self.default_side = default_side

    def __repr__(self):
        return u"<Standard {0}>".format(self.name)


def default_standard():
    """Un-validated placeholder profile - review before Phase 3 Standards GA."""
    return Standard(name=u"Default")
