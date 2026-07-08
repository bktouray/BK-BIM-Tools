# -*- coding: utf-8 -*-
"""Wall-run dimension planner: one or more continuous strings per wall, broken at
every hosted opening's jambs (door/window) and at every crossing wall - the
standard architectural convention for dimensioning walls with openings.

Crossing walls SPLIT the run into separate dimension strings rather than appearing
as a segment inside one continuous chain (product owner feedback 2026-07-05: don't
show the intersecting wall's own thickness - break there and resume after it). Each
resulting run still carries its own hosted openings as internal chain segments.

Validated live against a real project (2026-07-05): jamb references MUST come from
the WALL's own cut geometry (its reveal faces), not the door/window family's own
geometry - a real door's family geometry gave a frame extent (~1280mm) that did not
match its actual DOOR_WIDTH parameter (1200mm), while the wall's own reveal faces
matched the parametric width exactly. See
revit/adapter/reference_provider.py:wall_run_faces for the resolution technique;
this module only merges already-resolved AxisFaces into ordered chains.

`plan_wall_perpendicular_chain`/`plan_wall_overall` added 2026-07-07 for exterior
walls' 3-string perimeter dimensioning (product owner, sketch of the standard
French/European convention: innermost string = openings, middle string = every
perpendicular wall's own reference, outermost = the whole wall length). The
innermost string is `plan_wall_runs` above, unchanged. The middle string reuses
the SAME crossing-wall detection/reference data as the split-at-crossings
behavior, just merged into one continuous chain instead of used as a break point.
"""

from bkbim.domain.models.dimension_plan import DimensionPlan

# Any two break points closer than this are treated as the same physical point,
# not a genuine near-zero segment - confirmed live 2026-07-05: a crossing wall's
# own face can coincide almost exactly with the main wall's own end face (a T very
# close to a corner), which would otherwise produce a spurious ~0mm segment.
_COINCIDENT_TOLERANCE_FT = 0.01  # ~3mm


def plan_wall_runs(wall_faces, opening_faces_list, crossing_faces_list, measuring_axis, perp_pos):
    """Builds one DimensionPlan per contiguous run of the wall between crossing
    walls (or a single plan covering the whole wall if there are none).

    wall_faces: AxisFaces - the wall's own two end references and coordinates.
    opening_faces_list: list[AxisFaces] - one per hosted opening that was
                        confidently matched (callers omit unmatched openings).
                        Appears as an internal segment within whichever run it
                        falls inside.
    crossing_faces_list: list[AxisFaces] - one per perpendicular wall crossing
                        this one. SPLITS the run at that point - the crossing
                        wall's own thickness is never part of any chain.
    measuring_axis: "x" | "y" - the wall's length axis.
    perp_pos: perpendicular offset for the dimension line (already computed by the
              caller from the Standard profile).

    Returns list[DimensionPlan], one per run with at least 2 references; runs
    that collapse to nothing (e.g. two crossings back to back) are omitted.
    """
    if wall_faces is None:
        return []

    valid_openings = [f for f in opening_faces_list if f is not None]
    valid_crossings = sorted(
        (f for f in crossing_faces_list if f is not None), key=lambda f: f.coord_lo)

    plans = []
    run_start_coord = wall_faces.coord_lo
    run_start_ref = wall_faces.ref_lo

    for crossing in valid_crossings:
        if crossing.coord_lo > run_start_coord + _COINCIDENT_TOLERANCE_FT:
            run_openings = [
                o for o in valid_openings if run_start_coord < _center(o) < crossing.coord_lo
            ]
            plan = _build_plan(
                run_start_ref, run_start_coord, crossing.ref_lo, crossing.coord_lo,
                run_openings, measuring_axis, perp_pos)
            if plan is not None:
                plans.append(plan)

        if crossing.coord_hi > run_start_coord:
            run_start_coord = crossing.coord_hi
            run_start_ref = crossing.ref_hi

    final_openings = [
        o for o in valid_openings if run_start_coord < _center(o) < wall_faces.coord_hi
    ]
    plan = _build_plan(
        run_start_ref, run_start_coord, wall_faces.ref_hi, wall_faces.coord_hi,
        final_openings, measuring_axis, perp_pos)
    if plan is not None:
        plans.append(plan)

    return plans


def _center(axis_faces):
    return (axis_faces.coord_lo + axis_faces.coord_hi) / 2.0


def _build_plan(start_ref, start_coord, end_ref, end_coord, openings, measuring_axis, perp_pos):
    points = [(start_coord, start_ref), (end_coord, end_ref)]
    for opening in openings:
        points.append((opening.coord_lo, opening.ref_lo))
        points.append((opening.coord_hi, opening.ref_hi))

    points.sort(key=lambda p: p[0])
    points = _dedupe_coincident_points(points)
    if len(points) < 2:
        return None

    refs = [p[1] for p in points]
    return DimensionPlan(
        kind=DimensionPlan.KIND_WALL_RUN,
        refs=refs,
        axis=measuring_axis,
        line_coord_lo=points[0][0],
        line_coord_hi=points[-1][0],
        perp_pos=perp_pos,
    )


def _dedupe_coincident_points(sorted_points):
    if not sorted_points:
        return sorted_points

    deduped = [sorted_points[0]]
    for coord, ref in sorted_points[1:]:
        last_coord, _ = deduped[-1]
        if coord - last_coord <= _COINCIDENT_TOLERANCE_FT:
            continue  # same physical point as the one already kept
        deduped.append((coord, ref))
    return deduped


def plan_wall_perpendicular_chain(wall_faces, crossing_faces_list, measuring_axis, perp_pos):
    """Middle string of an exterior wall's 3-string perimeter dimensioning
    (2026-07-07, product owner: "the middle string to take the start and end
    point of the wall and every wall attached to that wall perpendicularly
    to get a reference"): wall-end -> each perpendicular wall's own faces
    -> ... -> wall-end - ONE continuous chain, unlike plan_wall_runs, which
    SPLITS the run at every crossing instead. Reuses the exact same
    crossing-wall detection/reference data plan_wall_runs already gets
    (crossing_faces_list) - just merges it into the chain instead of using
    it as a break point.

    wall_faces: AxisFaces - the wall's own two end references and coordinates.
    crossing_faces_list: list[AxisFaces] - one per perpendicular wall
                        touching/crossing this one (see crossing_wall_detector).
    measuring_axis: "x" | "y" - the wall's length axis.
    perp_pos: perpendicular offset for the dimension line.

    Returns a single DimensionPlan, or None if there aren't at least 2 points.
    """
    if wall_faces is None:
        return None

    points = [(wall_faces.coord_lo, wall_faces.ref_lo), (wall_faces.coord_hi, wall_faces.ref_hi)]
    for crossing in crossing_faces_list:
        if crossing is None:
            continue
        points.append((crossing.coord_lo, crossing.ref_lo))
        points.append((crossing.coord_hi, crossing.ref_hi))

    points.sort(key=lambda p: p[0])
    points = _dedupe_coincident_points(points)
    if len(points) < 2:
        return None

    refs = [p[1] for p in points]
    return DimensionPlan(
        kind=DimensionPlan.KIND_WALL_PERPENDICULAR_CHAIN,
        refs=refs,
        axis=measuring_axis,
        line_coord_lo=points[0][0],
        line_coord_hi=points[-1][0],
        perp_pos=perp_pos,
    )


def plan_wall_overall(wall_faces, measuring_axis, perp_pos):
    """Outermost string of an exterior wall's 3-string perimeter dimensioning
    (2026-07-07, product owner: "the third string to go above them all
    taking the whole wall length"): the wall's own two end faces, no
    intermediate refs at all.
    """
    if wall_faces is None:
        return None

    return DimensionPlan(
        kind=DimensionPlan.KIND_WALL_OVERALL,
        refs=[wall_faces.ref_lo, wall_faces.ref_hi],
        axis=measuring_axis,
        line_coord_lo=wall_faces.coord_lo,
        line_coord_hi=wall_faces.coord_hi,
        perp_pos=perp_pos,
    )
