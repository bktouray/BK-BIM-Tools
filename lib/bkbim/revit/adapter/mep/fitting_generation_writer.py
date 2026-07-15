# -*- coding: utf-8 -*-
"""Phase 3 (MEP_Routing_Playbook.md Sec 16): a separate pass, run only after
every pipe from Phase 2 already exists. Places Tees at interior junctions,
Elbows at the trunk's final junction and within each branch's own turns.
Never influences routing decisions - the path is already fixed by the time
this runs.

Live-verified 2026-07-10: `doc.Create.NewTeeFitting` joining 3 real
connectors (two trunk pipes + one branch pipe) at a real junction point,
using the project's real Valsir Pexal connectors - worked first try, rolled
back.

Handles the "branch has zero real pipes" edge case (a target essentially
already at the trunk, e.g. the real WC tested this session whose rough-in
was too short for Revit's own minimum pipe length, Phase 2 skipped it
entirely) - falls back to `branch.target_ref` (the target's own real
Connector, opaque to the domain graph but real here) and either an Elbow or
a direct `ConnectTo`, never assumes every branch has at least one pipe.
"""

import clr

clr.AddReference("RevitAPI")

from bkbim.core.logging import get_logger
from bkbim.core.result import Result

_logger = get_logger(u"bkbim.revit.adapter.mep.fitting_generation_writer")
_MATCH_TOLERANCE_MM = 5.0
_MATCH_TOLERANCE_FT = _MATCH_TOLERANCE_MM / 304.8


def _connector_near(pipe, point_mm):
    if pipe is None:
        return None
    try:
        connectors = pipe.ConnectorManager.Connectors
    except Exception:
        return None
    for c in connectors:
        try:
            o = c.Origin
            if (abs(o.X * 304.8 - point_mm[0]) < _MATCH_TOLERANCE_MM and
                    abs(o.Y * 304.8 - point_mm[1]) < _MATCH_TOLERANCE_MM and
                    abs(o.Z * 304.8 - point_mm[2]) < _MATCH_TOLERANCE_MM):
                return c
        except Exception:
            continue
    return None


class FittingGenerationWriter(object):
    def __init__(self, doc):
        self._doc = doc

    def write(self, routing_graph, trunk_pipes, branch_pipes):
        """trunk_pipes: list[Pipe] from PipeGeometryWriter, in trunk order.
        branch_pipes: dict {target_ref: [Pipe, ...]} from PipeGeometryWriter
        - target_ref is the real Connector for the routing target (opaque to
        the domain graph, ADR-0001, but a real Connector here).

        :rtype: Result wrapping {"elbows_created": int, "tees_created": int,
        "connections_made": int, "failed": int}
        """
        elbows = 0
        tees = 0
        connections = 0
        failed = 0

        # 1. Elbows within each branch's own path (where it turns from
        # horizontal to vertical, if it has both segments as real pipes).
        for _junction, branch in routing_graph.junctions:
            pipes = branch_pipes.get(branch.target_ref, [])
            for i in range(len(pipes) - 1):
                if self._join_two_pipes_with_elbow(pipes[i], pipes[i + 1]):
                    elbows += 1
                else:
                    failed += 1

        # 2. Junction fittings: Tee for every interior junction (trunk
        # continues past it), Elbow/direct-connect for the last one (nothing
        # continues past it - MEP_Routing_Playbook.md Sec 8).
        num_junctions = len(routing_graph.junctions)
        for i, (junction, branch) in enumerate(routing_graph.junctions):
            is_last = (i == num_junctions - 1)
            branch_pipe_list = branch_pipes.get(branch.target_ref, [])

            if branch_pipe_list:
                branch_connector = _connector_near(branch_pipe_list[-1], junction.position)
            else:
                # Branch had zero real pipes (target essentially already at
                # the trunk) - fall back to the target's own real connector.
                branch_connector = branch.target_ref

            trunk_in_pipe = trunk_pipes[i] if i < len(trunk_pipes) else None
            trunk_in_connector = _connector_near(trunk_in_pipe, junction.position)

            trunk_out_connector = None
            if not is_last and (i + 1) < len(trunk_pipes):
                trunk_out_connector = _connector_near(trunk_pipes[i + 1], junction.position)

            if branch_connector is None or trunk_in_connector is None:
                _logger.warning(u"Junction fitting skipped at {0} - missing connector(s)",
                                 junction.position)
                failed += 1
                continue

            try:
                if trunk_out_connector is not None:
                    self._doc.Create.NewTeeFitting(trunk_in_connector, trunk_out_connector,
                                                    branch_connector)
                    self._doc.Regenerate()
                    tees += 1
                elif branch_pipe_list:
                    self._doc.Create.NewElbowFitting(trunk_in_connector, branch_connector)
                    self._doc.Regenerate()
                    elbows += 1
                else:
                    trunk_in_connector.ConnectTo(branch_connector)
                    self._doc.Regenerate()
                    connections += 1
            except Exception as e:
                _logger.warning(u"Junction fitting failed at {0}: {1}", junction.position, str(e))
                failed += 1

        return Result.ok(value={
            "elbows_created": elbows, "tees_created": tees,
            "connections_made": connections, "failed": failed})

    def _join_two_pipes_with_elbow(self, pipe_a, pipe_b):
        try:
            for conn_a in pipe_a.ConnectorManager.Connectors:
                for conn_b in pipe_b.ConnectorManager.Connectors:
                    if conn_a.Origin.DistanceTo(conn_b.Origin) < _MATCH_TOLERANCE_FT:
                        self._doc.Create.NewElbowFitting(conn_a, conn_b)
                        self._doc.Regenerate()
                        return True
        except Exception as e:
            _logger.warning(u"Branch-internal elbow failed: {0}", str(e))
        return False
