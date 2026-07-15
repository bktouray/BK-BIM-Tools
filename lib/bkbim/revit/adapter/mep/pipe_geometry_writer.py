# -*- coding: utf-8 -*-
"""Phase 2 (MEP_Routing_Playbook.md Sec 15): converts a RoutingGraph into
real Pipe elements ONLY. No fittings, no connector joining, no accessories,
no tags - those are Phase 3/4's job. The goal at this stage is purely to
verify the routing graph produces the expected trunk-and-branch layout in
real geometry before any joining logic runs.

No Transaction handling here - same convention as every other writer in
this codebase (SAD Sec 4.4): the caller owns the Transaction.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import BuiltInParameter, XYZ
from Autodesk.Revit.DB.Plumbing import Pipe

from bkbim.core.logging import get_logger
from bkbim.core.result import Result
from bkbim.domain.geometry.units import mm_to_ft

_logger = get_logger(u"bkbim.revit.adapter.mep.pipe_geometry_writer")

# Revit's own minimum pipe curve length is a few mm - real bug caught live
# 2026-07-24: a WC's real rough-in offset (0.094mm) and a floating-point-
# rounding near-zero segment both threw from Pipe.Create instead of being
# recognised as "these two points are already coincident, no pipe needed
# here." A generous margin over Revit's actual minimum avoids relying on
# exact float equality (which real geometry will essentially never hit) to
# catch this - skipped for being too short is a normal outcome, not a
# failure.
_MIN_PIPE_LENGTH_MM = 10.0


def _mm_to_xyz(point_mm):
    return XYZ(mm_to_ft(point_mm[0]), mm_to_ft(point_mm[1]), mm_to_ft(point_mm[2]))


def _length_mm(a, b):
    return ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 + (b[2] - a[2]) ** 2) ** 0.5


class PipeGeometryWriter(object):
    def __init__(self, doc, system_type_id, pipe_type_id, level_id):
        self._doc = doc
        self._system_type_id = system_type_id
        self._pipe_type_id = pipe_type_id
        self._level_id = level_id

    def write(self, routing_graph, trunk_diameter_mm):
        """trunk_diameter_mm: sizing hasn't been decided yet
        (MEP_Routing_Playbook.md Sec 10) - the caller supplies a single
        diameter for the whole trunk; branch segments use their own
        diameter, already carried on each RouteSegment.

        :rtype: Result wrapping {"trunk_pipes": [...], "branch_pipes":
        {target_ref: [...]}, "failed": int, "skipped": int} - trunk_pipes/
        branch_pipes hold real Pipe elements, not opaque refs, since Phase 3
        (fittings) needs to find real connectors on them next. `skipped`
        counts segments too short to need a real pipe (already coincident
        points) - a normal outcome, not a failure; `failed` counts genuine
        Pipe.Create errors for any other reason.
        """
        failed = 0
        skipped = 0

        trunk_pipes = []
        trunk_points = routing_graph.trunk_points
        for i in range(len(trunk_points) - 1):
            pipe, was_skipped = self._create_pipe(trunk_points[i], trunk_points[i + 1], trunk_diameter_mm)
            if was_skipped:
                skipped += 1
            elif pipe is None:
                failed += 1
            else:
                trunk_pipes.append(pipe)

        branch_pipes = {}
        for _junction, branch in routing_graph.junctions:
            pipes_for_branch = []
            for segment in branch.segments:
                pipe, was_skipped = self._create_pipe(
                    segment.start_point, segment.end_point, segment.diameter_mm)
                if was_skipped:
                    skipped += 1
                elif pipe is None:
                    failed += 1
                else:
                    pipes_for_branch.append(pipe)
            branch_pipes[branch.target_ref] = pipes_for_branch

        if not trunk_pipes and not any(branch_pipes.values()):
            return Result.fail(u"No pipes could be created ({0} failed, {1} skipped).".format(
                failed, skipped))

        return Result.ok(value={
            "trunk_pipes": trunk_pipes, "branch_pipes": branch_pipes,
            "failed": failed, "skipped": skipped})

    def _create_pipe(self, start_mm, end_mm, diameter_mm):
        """Returns (pipe_or_None, was_skipped) - was_skipped is True when the
        two points are too close together for Revit to accept a real pipe
        (a normal outcome, e.g. a fixture whose rough-in already sits
        essentially at the corridor), distinct from a genuine failure.
        """
        if _length_mm(start_mm, end_mm) < _MIN_PIPE_LENGTH_MM:
            return None, True
        try:
            start = _mm_to_xyz(start_mm)
            end = _mm_to_xyz(end_mm)
            pipe = Pipe.Create(self._doc, self._system_type_id, self._pipe_type_id,
                                self._level_id, start, end)
            self._doc.Regenerate()

            diam_param = pipe.get_Parameter(BuiltInParameter.RBS_PIPE_DIAMETER_PARAM)
            if diam_param is not None and not diam_param.IsReadOnly:
                diam_param.Set(mm_to_ft(diameter_mm))

            return pipe, False
        except Exception as e:
            _logger.warning(u"Pipe creation failed at {0}->{1}: {2}", start_mm, end_mm, str(e))
            return None, False
