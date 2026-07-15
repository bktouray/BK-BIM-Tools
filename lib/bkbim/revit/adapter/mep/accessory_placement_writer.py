# -*- coding: utf-8 -*-
"""Phase 4 (MEP_Routing_Playbook.md Sec 17): places real accessory family
instances (currently: one isolation valve at a RoutingGraph's OriginNode).
A completely separate system from routing - the routing graph never depends
on this; this depends on the routing graph (and on Phase 2/3 geometry
already existing).

Live-verified 2026-07-10 against the real project: `doc.Create.NewFamilyInstance`
(the (XYZ, FamilySymbol, StructuralType) overload - there is no direct
Connector-based overload for this in the API, confirmed via reflection) at
the trunk's own origin point, then `Connector.ConnectTo` joining the valve's
own connector to the trunk's first pipe - worked first try.

Known simplification, disclosed: the valve is placed AT the origin point and
connected to the trunk's start - it does not model splitting an already-
continuous incoming supply pipe (there isn't one in this engine's scope; the
origin IS where the trunk begins). Only ONE of the valve's two connectors is
joined (to the trunk); the other (the "upstream"/incoming-supply side) is
left unconnected - modelling the incoming main itself is out of scope here,
same as MEP_Routing_Playbook.md's existing valve-placement Decision Log
entry already states.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import XYZ
from Autodesk.Revit.DB.Structure import StructuralType

from bkbim.core.logging import get_logger
from bkbim.core.result import Result
from bkbim.domain.geometry.units import mm_to_ft

_logger = get_logger(u"bkbim.revit.adapter.mep.accessory_placement_writer")
_JOIN_TOLERANCE_FT = 5.0 / 304.8


def _mm_to_xyz(point_mm):
    return XYZ(mm_to_ft(point_mm[0]), mm_to_ft(point_mm[1]), mm_to_ft(point_mm[2]))


def _connector_near(pipe, xyz, tolerance_ft=_JOIN_TOLERANCE_FT):
    if pipe is None:
        return None
    try:
        for c in pipe.ConnectorManager.Connectors:
            if c.Origin.DistanceTo(xyz) < tolerance_ft:
                return c
    except Exception:
        pass
    return None


class AccessoryPlacementWriter(object):
    def __init__(self, doc):
        self._doc = doc

    def place_origin_valve(self, routing_graph, valve_symbol, trunk_pipes):
        """valve_symbol: a real Revit FamilySymbol (Pipe Accessory category) -
        an open input the caller must resolve, same class of requirement as
        PipeType (MEP_Routing_Playbook.md Sec 9/§19). Activated automatically
        if not already active.
        trunk_pipes: list[Pipe] from PipeGeometryWriter, in trunk order - the
        valve joins to trunk_pipes[0]'s connector at the origin point.

        :rtype: Result wrapping {"valve": FamilyInstance or None}
        """
        if not trunk_pipes:
            return Result.fail(u"No trunk pipes to attach a valve to.")

        try:
            if not valve_symbol.IsActive:
                valve_symbol.Activate()
                self._doc.Regenerate()

            origin_xyz = _mm_to_xyz(routing_graph.origin.position)
            trunk_connector = _connector_near(trunk_pipes[0], origin_xyz)
            if trunk_connector is None:
                return Result.fail(u"Could not find the trunk's origin connector to attach the valve to.")

            valve_instance = self._doc.Create.NewFamilyInstance(
                origin_xyz, valve_symbol, StructuralType.NonStructural)
            self._doc.Regenerate()

            mep_model = getattr(valve_instance, u"MEPModel", None)
            if mep_model is None:
                return Result.fail(u"Placed valve has no MEPModel - cannot connect it.")

            valve_connectors = list(mep_model.ConnectorManager.Connectors)
            if not valve_connectors:
                return Result.fail(u"Placed valve has no connectors.")

            closest = min(valve_connectors, key=lambda vc: vc.Origin.DistanceTo(trunk_connector.Origin))
            trunk_connector.ConnectTo(closest)
            self._doc.Regenerate()

            return Result.ok(value={"valve": valve_instance})
        except Exception as e:
            _logger.warning(u"Valve placement failed: {0}", str(e))
            return Result.fail(u"Valve placement failed: {0}".format(str(e)))
