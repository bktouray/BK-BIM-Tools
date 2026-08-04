# -*- coding: utf-8 -*-
"""Auto Dimension for Walls and Openings: one or more continuous strings per wall,
broken at every hosted door/window's jambs (internal segments) AND split into
separate dimensions at every perpendicular wall that crosses it (PHASE_1_PLAN
follow-up, validated live 2026-07-05 against real doors/windows; crossing-wall
splitting added same day per product owner feedback - a crossing wall's own
thickness must never appear as a segment, the run should stop before it and
resume after).

Exterior walls get 2 MORE strings further out (2026-07-07, product owner sketch
of the standard French/European perimeter-dimensioning convention): a middle
"perpendicular wall" chain (`plan_wall_perpendicular_chain` - every perpendicular
wall's own reference, wall-end to wall-end, one continuous chain unlike the
split-at-crossings string above) and an outermost "overall" string
(`plan_wall_overall` - just the wall's own two end faces). "Exterior" isn't
detected automatically - this project's walls don't carry a reliable
Exterior/Interior tag (confirmed live) - it's whatever the caller flagged via
`wall_context["is_exterior"]` (the user's current selection, resolved upstream
in `wall_context_builder.py`).

Exterior walls also each get their OWN outward side, not the Standard's single
fixed `default_side` (2026-07-07 follow-up: "I always want it to go towards the
exterior of the building" - a fixed global side is wrong for a wall on the
opposite side of the building from whatever that fixed side happens to favor).
`_outward_side` compares each exterior wall's own centerpoint to the centroid of
the WHOLE exterior-wall selection - the side further from that centroid is
"outward." Non-exterior walls are unaffected, still using `default_side`.

Skips any plan that already has a matching dimension in the view (product owner
feedback 2026-07-05: re-running this command should be safe to use as an "update" -
only add what's missing, never create overlapping duplicates).

Zero Autodesk.Revit imports (ADR-0001) - unit-testable with fakes, same pattern as
the other app commands. Transaction ownership stays with the caller (pushbutton
entry point), per SAD Sec 4.4.
"""

from bkbim.core.logging import get_logger
from bkbim.core.result import Result
from bkbim.domain.dimensioning.crossing_wall_detector import find_crossing_walls
from bkbim.domain.dimensioning.wall_run_planner import plan_wall_overall, plan_wall_perpendicular_chain, plan_wall_runs
from bkbim.domain.geometry.units import mm_to_ft

_logger = get_logger(u"bkbim.app.auto_wall_opening_dimension")

_MIN_PERIMETER_GAP_MM = 300.0


def _exterior_centroid(walls_with_context):
    exterior = [c for c in walls_with_context if c.get(u"is_exterior")]
    if not exterior:
        return None, None
    centroid_x = sum(c[u"center_x"] for c in exterior) / float(len(exterior))
    centroid_y = sum(c[u"center_y"] for c in exterior) / float(len(exterior))
    return centroid_x, centroid_y


def _outward_side(length_axis, wall_center_x, wall_center_y, centroid_x, centroid_y, fallback_side):
    """Which side (-1 | +1, matching Standard.default_side's convention) of
    THIS wall points away from the exterior-wall group's overall centroid.
    Falls back to `fallback_side` if there's no usable centroid (e.g. this
    is the only exterior wall, sitting exactly at its own centroid).
    """
    if centroid_x is None or centroid_y is None:
        return fallback_side
    wall_perp_center = wall_center_y if length_axis == u"x" else wall_center_x
    centroid_perp = centroid_y if length_axis == u"x" else centroid_x
    if wall_perp_center == centroid_perp:
        return fallback_side
    return -1 if wall_perp_center < centroid_perp else 1


def run(walls_with_context, reference_provider, wall_run_reader, existing_dimension_checker,
        writer, failure_tracker, standard):
    """Dimensions each wall described in `walls_with_context`. A wall with one or
    more crossing walls produces multiple separate dimensions (one per contiguous
    run), not one continuous chain spanning the crossings. A wall flagged
    `is_exterior` ALSO gets a middle "perpendicular wall" chain and an outermost
    "overall" string, further out, all placed on whichever side actually faces
    away from the rest of the exterior-wall selection. A run that already has a
    matching dimension in the view is skipped, not duplicated.

    walls_with_context: list of dicts, one per wall, already resolved by the
        caller (no Revit types here): {
            "wall_ref": opaque handle,
            "length_axis": "x" | "y",
            "perp_lo": float, "perp_hi": float - the wall's extent along the axis
                PERPENDICULAR to length_axis, used to place the dimension line,
            "opening_locations": [float, ...] - each hosted opening's coordinate
                along length_axis (e.g. bounding-box center),
            "candidate_walls": list[ElementInfo] - other walls to test for a
                perpendicular crossing (caller excludes the wall itself).
            "is_exterior": bool - whether this wall gets the 2 extra strings.
            "center_x"/"center_y": float - this wall's own overall centerpoint,
                used (only for exterior walls) to work out which side is outward.
        }
    reference_provider: IReferenceProvider - resolves a crossing wall's own
        thickness-direction faces via the already-validated faces_for().
    wall_run_reader: IWallRunReader - resolves the main wall's own end faces +
        matched opening jamb faces.
    existing_dimension_checker: IExistingDimensionChecker - detects a run that's
        already dimensioned, so it can be skipped instead of duplicated.

    :rtype: bkbim.core.result.Result wrapping
        {"created": int, "skipped": int, "already_existing": int}
    """
    if not walls_with_context:
        return Result.fail(u"No walls found to dimension.")

    offset_ft = mm_to_ft(standard.offset_first_mm)
    gap_mm = max(float(standard.wall_perimeter_gap_mm or 0.0), _MIN_PERIMETER_GAP_MM)
    gap_ft = mm_to_ft(gap_mm)
    centroid_x, centroid_y = _exterior_centroid(walls_with_context)

    created = 0
    skipped = 0
    already_existing = 0

    for wall_context in walls_with_context:
        length_axis = wall_context["length_axis"]
        try:
            wall_faces, opening_faces_list = wall_run_reader.wall_run_faces(
                wall_context["wall_ref"], length_axis, wall_context["opening_locations"])
        except Exception as e:
            _logger.warning(u"wall_run_faces failed: {0}", str(e))
            skipped += 1
            continue

        if wall_faces is None:
            skipped += 1
            continue

        perp_lo = wall_context["perp_lo"]
        perp_hi = wall_context["perp_hi"]
        is_exterior = wall_context.get("is_exterior")
        side = (_outward_side(length_axis, wall_context["center_x"], wall_context["center_y"],
                               centroid_x, centroid_y, standard.default_side)
                if is_exterior else standard.default_side)

        crossing = find_crossing_walls(
            length_axis, wall_faces.coord_lo, wall_faces.coord_hi,
            perp_lo, perp_hi, wall_context.get("candidate_walls", []))

        crossing_faces_list = []
        for crossing_wall_info, break_lo, break_hi in crossing:
            try:
                crossing_faces = reference_provider.faces_for(crossing_wall_info.ref, length_axis)
            except Exception as e:
                _logger.warning(u"faces_for failed for a crossing wall: {0}", str(e))
                crossing_faces = None
            if crossing_faces is not None:
                crossing_faces_list.append(crossing_faces)

        perp_pos = (perp_lo - offset_ft) if side < 0 else (perp_hi + offset_ft)

        plans = plan_wall_runs(wall_faces, opening_faces_list, crossing_faces_list, length_axis, perp_pos)

        if is_exterior:
            perp_pos_middle = (perp_lo - offset_ft - gap_ft) if side < 0 else (perp_hi + offset_ft + gap_ft)
            perp_pos_outer = (perp_lo - offset_ft - 2 * gap_ft) if side < 0 else (perp_hi + offset_ft + 2 * gap_ft)
            middle_plan = plan_wall_perpendicular_chain(wall_faces, crossing_faces_list, length_axis, perp_pos_middle)
            if middle_plan is not None:
                plans.append(middle_plan)
            outer_plan = plan_wall_overall(wall_faces, length_axis, perp_pos_outer)
            if outer_plan is not None:
                plans.append(outer_plan)

        if not plans:
            skipped += 1
            continue

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

    _logger.info(u"Auto Wall/Opening Dimension: {0} created, {1} already existing, {2} skipped",
                 created, already_existing, skipped)
    return Result.ok(
        value={"created": created, "skipped": skipped, "already_existing": already_existing},
        message=u"{0} dimension(s) created ({1} already existed, {2} skipped)".format(
            created, already_existing, skipped),
    )
