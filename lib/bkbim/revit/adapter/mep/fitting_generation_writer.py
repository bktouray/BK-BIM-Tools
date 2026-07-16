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

from Autodesk.Revit.DB import BuiltInCategory, XYZ
from Autodesk.Revit.DB.Plumbing import PlumbingUtils

from bkbim.core.logging import get_logger
from bkbim.core.result import Result

_logger = get_logger(u"bkbim.revit.adapter.mep.fitting_generation_writer")
_MATCH_TOLERANCE_MM = 5.0
_MATCH_TOLERANCE_FT = _MATCH_TOLERANCE_MM / 304.8


def _connector_near(pipe, point_mm, tolerance_mm=_MATCH_TOLERANCE_MM):
    if pipe is None:
        return None
    try:
        connectors = pipe.ConnectorManager.Connectors
    except Exception:
        return None
    for c in connectors:
        try:
            o = c.Origin
            if (abs(o.X * 304.8 - point_mm[0]) < tolerance_mm and
                    abs(o.Y * 304.8 - point_mm[1]) < tolerance_mm and
                    abs(o.Z * 304.8 - point_mm[2]) < tolerance_mm):
                return c
        except Exception:
            continue
    return None


def _connectors_compatible(connector_a, connector_b, tolerance_ft=_MATCH_TOLERANCE_FT):
    if connector_a is None or connector_b is None:
        return False
    try:
        if str(connector_a.Domain) != str(connector_b.Domain):
            return False
        if connector_a.Origin.DistanceTo(connector_b.Origin) > tolerance_ft:
            return False
        diameter_a = connector_a.Radius * 2.0
        diameter_b = connector_b.Radius * 2.0
        return abs(diameter_a - diameter_b) <= (1.0 / 304.8)
    except Exception:
        return False


def _connected_to(connector_a, connector_b, tolerance_ft=_MATCH_TOLERANCE_FT):
    """True only when connector_a's references include connector_b.

    Revit can auto-connect a Pipe.Create endpoint that lands exactly on an
    existing connector. In that case both connectors are already connected,
    and trying ConnectTo again is an error rather than useful work.
    """
    if connector_a is None or connector_b is None:
        return False
    try:
        for referenced in connector_a.AllRefs:
            try:
                if (referenced.Owner.Id == connector_b.Owner.Id and
                        referenced.Origin.DistanceTo(connector_b.Origin) <= tolerance_ft):
                    return True
            except Exception:
                continue
    except Exception:
        return False
    return False


def _is_pipe_connector(connector):
    """True when a source is an open Pipe endpoint, not a valve outlet."""
    try:
        category = connector.Owner.Category
        return category.BuiltInCategory == BuiltInCategory.OST_PipeCurves
    except Exception:
        return False


def _coincident_connectors(pipe_a, pipe_b):
    try:
        for conn_a in pipe_a.ConnectorManager.Connectors:
            for conn_b in pipe_b.ConnectorManager.Connectors:
                if conn_a.Origin.DistanceTo(conn_b.Origin) < _MATCH_TOLERANCE_FT:
                    return conn_a, conn_b
    except Exception:
        pass
    return None, None


def _connector_origin_matches_point(connector, point_mm, tolerance_mm=_MATCH_TOLERANCE_MM):
    try:
        origin = connector.Origin
        return (
            abs(origin.X * 304.8 - point_mm[0]) < tolerance_mm and
            abs(origin.Y * 304.8 - point_mm[1]) < tolerance_mm and
            abs(origin.Z * 304.8 - point_mm[2]) < tolerance_mm)
    except Exception:
        return False


def _points_close_mm(point_a, point_b, tolerance_mm=_MATCH_TOLERANCE_MM):
    return (
        abs(point_a[0] - point_b[0]) < tolerance_mm and
        abs(point_a[1] - point_b[1]) < tolerance_mm and
        abs(point_a[2] - point_b[2]) < tolerance_mm)


def _mm_to_xyz(point_mm):
    return XYZ(point_mm[0] / 304.8, point_mm[1] / 304.8, point_mm[2] / 304.8)


class FittingGenerationWriter(object):
    def __init__(self, doc):
        self._doc = doc

    def write(self, routing_graph, trunk_pipes, branch_pipes,
              source_connector=None, feed_pipes=None, source_pipe=None,
              source_point=None):
        """trunk_pipes: list[Pipe] from PipeGeometryWriter, in trunk order.
        branch_pipes: dict {target_ref: [Pipe, ...]} from PipeGeometryWriter
        - target_ref is the real Connector for the routing target (opaque to
        the domain graph, ADR-0001, but a real Connector here).

        source_connector: optional existing Cold Water source connector. If
        supplied, it must connect to the first trunk pipe at graph.origin.
        feed_pipes: optional upstream pipes from incoming main/valve routing
        points to the trunk origin. They are joined here after all geometry
        exists, matching the graph -> pipes -> fittings ordering.

        :rtype: Result wrapping {"elbows_created": int, "tees_created": int,
        "connections_made": int, "fixture_connections_made": int,
        "source_connections_made": int, "failed": int}
        """
        elbows = 0
        tees = 0
        connections = 0
        fixture_connections = 0
        source_connections = 0
        failed = 0
        diagnostics = []
        feed_pipes = feed_pipes or []
        feed_endpoint_is_first_junction = (
            bool(feed_pipes) and bool(routing_graph.junctions) and
            _points_close_mm(
                routing_graph.origin.position,
                routing_graph.junctions[0][0].position))

        # 0. Connect the explicit source only after Phase 2 has created every
        # route pipe. This preserves graph -> geometry -> connections ordering.
        if source_pipe is not None and source_point is not None and feed_pipes:
            source_result = self._connect_existing_source_pipe(
                source_pipe, source_point, feed_pipes[0])
            if source_result == u"tee":
                tees += 1
                source_connections += 1
            elif source_result == u"elbow":
                elbows += 1
                source_connections += 1
            elif source_result == u"union" or source_result == u"connected":
                connections += 1
                source_connections += 1
            else:
                _logger.warning(
                    u"Existing source pipe tie-in failed at {0}", source_point)
                diagnostics.append(
                    u"Existing source pipe tie-in failed at {0}.".format(
                        source_point))
                failed += 1

        if source_connector is not None:
            source_pipe_connector = (
                _connector_near(trunk_pipes[0], routing_graph.origin.position)
                if trunk_pipes else None)
            if self._connect_source(source_connector, source_pipe_connector):
                source_connections += 1
            else:
                _logger.warning(
                    u"Cold Water source connection failed at {0}",
                    routing_graph.origin.position)
                diagnostics.append(
                    u"Source connection failed at {0}.".format(
                        routing_graph.origin.position))
                failed += 1

        # 0b. Join the generated upstream feed route to itself and then to
        # the generated trunk. This models water-main -> valve point -> trunk
        # as geometry first; real valve-family placement remains a later pass.
        for i in range(len(feed_pipes) - 1):
            fitting_kind = self._join_two_pipes(feed_pipes[i], feed_pipes[i + 1])
            if fitting_kind == u"elbow":
                elbows += 1
                source_connections += 1
            elif fitting_kind == u"union" or fitting_kind == u"connected":
                connections += 1
                source_connections += 1
            else:
                diagnostics.append(
                    u"Feed pipe fitting failed between feed segment {0} and {1}.".format(
                        i + 1, i + 2))
                failed += 1

        if feed_pipes and trunk_pipes and not feed_endpoint_is_first_junction:
            fitting_kind = self._join_two_pipes(feed_pipes[-1], trunk_pipes[0])
            if fitting_kind == u"elbow":
                elbows += 1
                source_connections += 1
            elif fitting_kind == u"union" or fitting_kind == u"connected":
                connections += 1
                source_connections += 1
            else:
                _logger.warning(
                    u"Cold Water feed-to-trunk connection failed at {0}",
                    routing_graph.origin.position)
                diagnostics.append(
                    u"Feed-to-trunk connection failed at {0}. The feed endpoint "
                    u"must coincide with the trunk origin.".format(
                        routing_graph.origin.position))
                failed += 1

        # 0c. Join trunk corner breaks that are NOT fixture junctions. A
        # multi-wall corridor creates adjacent trunk pipes at wall corners;
        # fixture junctions are intentionally left for the Tee/final-elbow
        # logic below.
        junction_points = [junction.position for junction, _branch in routing_graph.junctions]
        for i in range(len(trunk_pipes) - 1):
            conn_a, conn_b = _coincident_connectors(trunk_pipes[i], trunk_pipes[i + 1])
            if conn_a is None or conn_b is None:
                continue
            if any(_connector_origin_matches_point(conn_a, point) for point in junction_points):
                continue
            fitting_kind = self._join_two_pipes(trunk_pipes[i], trunk_pipes[i + 1])
            if fitting_kind == u"elbow":
                elbows += 1
            elif fitting_kind == u"union" or fitting_kind == u"connected":
                connections += 1
            else:
                _logger.warning(u"Trunk corner fitting failed")
                diagnostics.append(
                    u"Trunk corner fitting failed between trunk segment {0} and {1}.".format(
                        i + 1, i + 2))
                failed += 1

        # 1. Join each non-zero branch back to its real fixture connector.
        # Phase 2 intentionally creates geometry only; this is the first
        # point where a fixture connector is allowed to be touched.
        for _junction, branch in routing_graph.junctions:
            pipes = branch_pipes.get(branch.target_ref, [])
            if not pipes:
                continue
            if not branch.segments:
                failed += 1
                continue
            fixture_point = branch.segments[0].start_point
            pipe_connector = _connector_near(
                pipes[0], fixture_point, tolerance_mm=10.1)
            if self._connect_direct(branch.target_ref, pipe_connector):
                fixture_connections += 1
            else:
                _logger.warning(
                    u"Fixture connection failed for target at {0}", fixture_point)
                diagnostics.append(
                    u"Fixture connection failed for target at {0}.".format(
                        fixture_point))
                failed += 1

        # 2. Elbows within each branch's own path (where it turns from
        # horizontal to vertical, if it has both segments as real pipes).
        for _junction, branch in routing_graph.junctions:
            pipes = branch_pipes.get(branch.target_ref, [])
            for i in range(len(pipes) - 1):
                if self._join_two_pipes_with_elbow(pipes[i], pipes[i + 1]):
                    elbows += 1
                else:
                    diagnostics.append(
                        u"Branch elbow failed between branch segment {0} and {1}.".format(
                            i + 1, i + 2))
                    failed += 1

        # 3. Junction fittings: Tee for every interior junction (trunk
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

            trunk_connectors = []
            for pipe in trunk_pipes:
                connector = _connector_near(pipe, junction.position)
                if connector is not None:
                    trunk_connectors.append(connector)
            if (i == 0 and feed_endpoint_is_first_junction and feed_pipes):
                feed_connector = _connector_near(feed_pipes[-1], junction.position)
                if feed_connector is not None:
                    trunk_connectors.insert(0, feed_connector)

            expected_trunk_connectors = 1 if is_last else 2
            if (branch_connector is None or
                    len(trunk_connectors) != expected_trunk_connectors):
                _logger.warning(u"Junction fitting skipped at {0} - missing connector(s)",
                                 junction.position)
                diagnostics.append(
                    u"Junction fitting skipped at {0} - missing connector(s).".format(
                        junction.position))
                failed += 1
                continue

            try:
                if not is_last:
                    self._doc.Create.NewTeeFitting(
                        trunk_connectors[0], trunk_connectors[1], branch_connector)
                    self._doc.Regenerate()
                    tees += 1
                elif branch_pipe_list:
                    self._doc.Create.NewElbowFitting(
                        trunk_connectors[0], branch_connector)
                    self._doc.Regenerate()
                    elbows += 1
                else:
                    if self._connect_direct(trunk_connectors[0], branch_connector):
                        connections += 1
                    else:
                        raise ValueError(
                            u"Direct trunk-to-fixture connector compatibility check failed")
            except Exception as e:
                _logger.warning(u"Junction fitting failed at {0}: {1}", junction.position, str(e))
                diagnostics.append(
                    u"Junction fitting failed at {0}: {1}".format(
                        junction.position, str(e)))
                failed += 1

        value = {
            "elbows_created": elbows, "tees_created": tees,
            "connections_made": connections,
            "fixture_connections_made": fixture_connections,
            "source_connections_made": source_connections,
            "failed": failed,
        }
        if failed:
            return Result.fail(
                u"Fitting/connection generation failed in {0} place(s); "
                u"the complete route must be rolled back.".format(failed),
                diagnostics=diagnostics)
        return Result.ok(value=value)

    def _connect_direct(self, connector_a, connector_b):
        if not _connectors_compatible(connector_a, connector_b):
            return False
        try:
            if connector_a.IsConnected or connector_b.IsConnected:
                return (
                    connector_a.IsConnected and connector_b.IsConnected and
                    _connected_to(connector_a, connector_b) and
                    _connected_to(connector_b, connector_a))
            connector_a.ConnectTo(connector_b)
            self._doc.Regenerate()
            return (
                connector_a.IsConnected and connector_b.IsConnected and
                _connected_to(connector_a, connector_b) and
                _connected_to(connector_b, connector_a))
        except Exception as e:
            _logger.warning(u"Direct connector join failed: {0}", str(e))
            return False

    def _connect_source(self, source_connector, trunk_connector):
        """Connects the generated trunk to the selected existing source.

        A pipe accessory outlet (the intended post-valve case) uses the same
        direct connector join as a fixture inlet. Two pipe endpoints are a
        distinct Revit case: `ConnectTo` rejects them, while
        `NewUnionFitting` creates the required pipe-to-pipe join (or lets
        Revit resolve an already-coincident union). Both outcomes are checked
        through the actual connector relationship, never just the API return.
        """
        if not _is_pipe_connector(source_connector):
            return self._connect_direct(source_connector, trunk_connector)
        if not _connectors_compatible(source_connector, trunk_connector):
            return False
        # Pipe.Create can occasionally resolve a coincident open endpoint
        # itself. The picker guaranteed the source was open before geometry,
        # so both endpoints now being connected is a valid completed join.
        if source_connector.IsConnected or trunk_connector.IsConnected:
            return source_connector.IsConnected and trunk_connector.IsConnected
        try:
            self._doc.Create.NewUnionFitting(source_connector, trunk_connector)
            self._doc.Regenerate()
            # A successful pipe union can introduce a logical connector whose
            # Origin is intentionally unavailable. Therefore `AllRefs` cannot
            # prove a direct physical peer as it can for fixture/valve joins.
            # Both endpoints were explicitly unconnected before this call, so
            # both now being connected is the authoritative Revit result.
            return source_connector.IsConnected and trunk_connector.IsConnected
        except Exception as e:
            _logger.warning(u"Pipe source union failed: {0}", str(e))
            return False

    def _connect_existing_source_pipe(self, source_pipe, source_point, feed_pipe):
        feed_connector = _connector_near(feed_pipe, source_point, tolerance_mm=10.1)
        if feed_connector is None:
            return None

        source_endpoint = _connector_near(source_pipe, source_point, tolerance_mm=10.1)
        if source_endpoint is not None:
            return self._join_two_pipes(source_pipe, feed_pipe)

        try:
            new_pipe_id = PlumbingUtils.BreakCurve(
                self._doc, source_pipe.Id, _mm_to_xyz(source_point))
            self._doc.Regenerate()
            split_pipe = self._doc.GetElement(new_pipe_id)
        except Exception as e:
            _logger.warning(u"Existing source pipe split failed: {0}", str(e))
            return None

        source_connector_a = _connector_near(
            source_pipe, source_point, tolerance_mm=10.1)
        source_connector_b = _connector_near(
            split_pipe, source_point, tolerance_mm=10.1)
        if (source_connector_a is None or source_connector_b is None or
                feed_connector is None):
            return None

        try:
            self._doc.Create.NewTeeFitting(
                source_connector_a, source_connector_b, feed_connector)
            self._doc.Regenerate()
            return u"tee"
        except Exception as e:
            _logger.warning(u"Existing source pipe tee failed: {0}", str(e))
            return None

    def _join_two_pipes_with_elbow(self, pipe_a, pipe_b):
        return self._join_two_pipes(pipe_a, pipe_b) == u"elbow"

    def _join_two_pipes(self, pipe_a, pipe_b):
        conn_a, conn_b = _coincident_connectors(pipe_a, pipe_b)
        if conn_a is None or conn_b is None:
            return None
        try:
            if conn_a.IsConnected and conn_b.IsConnected:
                return u"connected"
        except Exception:
            pass
        try:
            self._doc.Create.NewElbowFitting(conn_a, conn_b)
            self._doc.Regenerate()
            return u"elbow"
        except Exception:
            pass
        try:
            self._doc.Create.NewUnionFitting(conn_a, conn_b)
            self._doc.Regenerate()
            return u"union" if (conn_a.IsConnected and conn_b.IsConnected) else None
        except Exception as e:
            _logger.warning(u"Pipe-to-pipe fitting failed: {0}", str(e))
            return None
