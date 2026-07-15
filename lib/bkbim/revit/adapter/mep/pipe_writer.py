# -*- coding: utf-8 -*-
"""Executes a RoutingPlan as real Pipe elements (MEP_SAD.md Sec 6). No
Transaction handling here - same convention as every other writer in this
codebase (SAD Sec 4.4): the caller (sanitary_drainage_flow.py) owns the
Transaction, this class just creates pipes and reports what happened.

Live-verified 2026-07-10 against the product owner's real "Toilet Test File"
project, rolled back per [[revit-live-testing-safety]]: `Pipe.Create` with a
real Sanitary PipingSystemType + a real PVC PipeType succeeded, the diameter
parameter was mutable after creation, and `Connector.ConnectTo` correctly
joined the new pipe's start connector to a WC's real Sanitary connector.

Also live-verified 2026-07-10 (Water Supply pivot, ADR-0004 update): creating
TWO pipes that share an endpoint and joining them with
`doc.Create.NewElbowFitting(connA, connB)` - the shape `plan_elbow_route`'s
multi-segment `RoutingPlan.fittings` needs. Only `FittingPlan.KIND_ELBOW` is
handled; branch fittings (wye/tee) were never produced by any planner yet
(branch merging is still deferred) and aren't wired here.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import BuiltInParameter
from Autodesk.Revit.DB import XYZ
from Autodesk.Revit.DB.Plumbing import Pipe

from bkbim.core.logging import get_logger
from bkbim.core.result import Result
from bkbim.domain.geometry.units import mm_to_ft
from bkbim.domain.mep.models.routing_plan import FittingPlan

_logger = get_logger(u"bkbim.revit.adapter.mep.pipe_writer")
_JOIN_TOLERANCE_MM = 5.0


def _mm_to_xyz(point_mm):
    return XYZ(mm_to_ft(point_mm[0]), mm_to_ft(point_mm[1]), mm_to_ft(point_mm[2]))


def _points_match_mm(a, b, tolerance_mm=_JOIN_TOLERANCE_MM):
    return (abs(a[0] - b[0]) < tolerance_mm and
            abs(a[1] - b[1]) < tolerance_mm and
            abs(a[2] - b[2]) < tolerance_mm)


def _closest_connector(pipe, target_point_mm):
    try:
        connectors = pipe.ConnectorManager.Connectors
    except Exception:
        return None
    for c in connectors:
        try:
            o = c.Origin
            point_mm = (o.X * 304.8, o.Y * 304.8, o.Z * 304.8)
            if _points_match_mm(point_mm, target_point_mm):
                return c
        except Exception:
            continue
    return None


class RevitPipeWriter(object):
    def __init__(self, doc, system_type_id, pipe_type_id, level_id):
        self._doc = doc
        self._system_type_id = system_type_id
        self._pipe_type_id = pipe_type_id
        self._level_id = level_id

    def write(self, routing_plan):
        """:rtype: bkbim.core.result.Result wrapping
        {"created": int, "failed": int, "fittings_created": int, "fittings_failed": int}
        """
        created = 0
        failed = 0
        pipes = []  # list of (pipe, start_point_mm, end_point_mm)
        for segment in routing_plan.segments:
            try:
                start = _mm_to_xyz(segment.start_point)
                end = _mm_to_xyz(segment.end_point)
                pipe = Pipe.Create(self._doc, self._system_type_id, self._pipe_type_id,
                                    self._level_id, start, end)
                self._doc.Regenerate()

                diam_param = pipe.get_Parameter(BuiltInParameter.RBS_PIPE_DIAMETER_PARAM)
                if diam_param is not None and not diam_param.IsReadOnly:
                    diam_param.Set(mm_to_ft(segment.diameter_mm))

                if segment.source_connector_ref is not None:
                    pipe_start_conn = _closest_connector(pipe, segment.start_point)
                    if pipe_start_conn is not None:
                        segment.source_connector_ref.ConnectTo(pipe_start_conn)
                    else:
                        _logger.warning(u"Pipe created but no matching start connector to join at {0}",
                                         segment.start_point)

                if segment.target_connector_ref is not None:
                    pipe_end_conn = _closest_connector(pipe, segment.end_point)
                    if pipe_end_conn is not None:
                        segment.target_connector_ref.ConnectTo(pipe_end_conn)
                    else:
                        _logger.warning(u"Pipe created but no matching end connector to join at {0}",
                                         segment.end_point)

                pipes.append((pipe, segment.start_point, segment.end_point))
                created += 1
            except Exception as e:
                _logger.warning(u"Pipe creation failed: {0}", str(e))
                failed += 1

        fittings_created, fittings_failed = self._create_fittings(routing_plan.fittings, pipes)

        if created == 0:
            return Result.fail(u"No pipes could be created ({0} failed).".format(failed))
        return Result.ok(value={
            "created": created, "failed": failed,
            "fittings_created": fittings_created, "fittings_failed": fittings_failed})

    def _create_fittings(self, fitting_plans, pipes):
        """Only KIND_ELBOW is handled - joins the two pipes that share the
        fitting's at_point via doc.Create.NewElbowFitting. Branch fittings
        (wye/tee) aren't produced by any planner yet (branch merging is
        still deferred), so there's nothing else to handle here.
        """
        created = 0
        failed = 0
        for fitting_plan in fitting_plans:
            if fitting_plan.kind != FittingPlan.KIND_ELBOW:
                continue
            try:
                pipe_a = None
                pipe_b = None
                for pipe, start_mm, end_mm in pipes:
                    if _points_match_mm(end_mm, fitting_plan.at_point):
                        pipe_a = pipe
                    elif _points_match_mm(start_mm, fitting_plan.at_point):
                        pipe_b = pipe

                if pipe_a is None or pipe_b is None:
                    _logger.warning(u"Elbow fitting skipped - couldn't find both pipes at {0}",
                                     fitting_plan.at_point)
                    failed += 1
                    continue

                conn_a = _closest_connector(pipe_a, fitting_plan.at_point)
                conn_b = _closest_connector(pipe_b, fitting_plan.at_point)
                if conn_a is None or conn_b is None:
                    _logger.warning(u"Elbow fitting skipped - couldn't resolve connectors at {0}",
                                     fitting_plan.at_point)
                    failed += 1
                    continue

                self._doc.Create.NewElbowFitting(conn_a, conn_b)
                self._doc.Regenerate()
                created += 1
            except Exception as e:
                _logger.warning(u"Elbow fitting creation failed: {0}", str(e))
                failed += 1
        return created, failed
