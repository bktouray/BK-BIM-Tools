# -*- coding: utf-8 -*-
"""Detects which other walls genuinely cross a main wall's length span, so the
wall-run dimension can break there - matching the product owner's request
(2026-07-05, screenshot showing long dimension strings that should stop at each
intersecting partition, not run straight through).

A candidate wall "crosses" the main wall when it runs PERPENDICULAR to it, its own
extent overlaps the main wall's length span, and it physically touches the main
wall's thickness band - not merely a nearby parallel or unrelated wall.

Pure logic (ADR-0001) - reuses ElementInfo, no Revit types. This only decides WHICH
candidates qualify; the caller resolves each qualifying wall's real geometric
references via the existing, already-validated IReferenceProvider.faces_for()
(a crossing wall's own thickness-direction faces are exactly its faces with normal
along the main wall's length axis).
"""

# A partition crossing the main wall is often modeled as two SEPARATE wall
# elements meeting at the same point (one continuing on each side) - both
# independently register as "crossing" with near-identical spans (confirmed live
# 2026-07-05: two real walls differed only in the ~10th decimal place of their
# thickness-band coordinates). This tolerance treats such near-coincident spans as
# one physical crossing, not two.
_DEDUPE_TOLERANCE_FT = 0.01  # ~3mm


def find_crossing_walls(main_axis, main_length_lo, main_length_hi,
                         main_perp_lo, main_perp_hi, candidate_walls, tolerance_ft=0.0):
    """Returns list[(ElementInfo, break_lo, break_hi)] for every candidate that
    crosses the main wall, clipped to the main wall's own length span, with
    near-coincident duplicate crossings (see _DEDUPE_TOLERANCE_FT) collapsed to one.

    main_axis: "x" | "y" - the main wall's length direction.
    main_length_lo/hi: the main wall's own extent along main_axis.
    main_perp_lo/hi: the main wall's own extent along the perpendicular axis
                     (its thickness band).
    candidate_walls: list[ElementInfo] - other walls to test (caller excludes the
                     main wall itself).
    """
    crossing = []
    for wall_info in candidate_walls:
        candidate_axis = u"x" if wall_info.width_x >= wall_info.width_y else u"y"
        if candidate_axis == main_axis:
            continue  # parallel/collinear wall, not a perpendicular crossing

        if main_axis == u"x":
            cand_lo, cand_hi = wall_info.min_x, wall_info.max_x
            cand_perp_lo, cand_perp_hi = wall_info.min_y, wall_info.max_y
        else:
            cand_lo, cand_hi = wall_info.min_y, wall_info.max_y
            cand_perp_lo, cand_perp_hi = wall_info.min_x, wall_info.max_x

        crosses_length = cand_hi > main_length_lo + tolerance_ft and cand_lo < main_length_hi - tolerance_ft
        touches_perp = cand_perp_hi > main_perp_lo - tolerance_ft and cand_perp_lo < main_perp_hi + tolerance_ft
        if not (crosses_length and touches_perp):
            continue

        break_lo = max(main_length_lo, cand_lo)
        break_hi = min(main_length_hi, cand_hi)
        if break_hi - break_lo <= tolerance_ft:
            continue  # degenerate/zero-width overlap

        crossing.append((wall_info, break_lo, break_hi))

    return _dedupe_overlapping(crossing)


def _dedupe_overlapping(crossing):
    if not crossing:
        return []

    ordered = sorted(crossing, key=lambda c: c[1])
    merged = [ordered[0]]
    for wall_info, lo, hi in ordered[1:]:
        _, last_lo, last_hi = merged[-1]
        if lo <= last_hi + _DEDUPE_TOLERANCE_FT:
            continue  # coincides with the already-kept span - same physical crossing
        merged.append((wall_info, lo, hi))
    return merged
