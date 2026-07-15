# -*- coding: utf-8 -*-
"""Ports: interfaces the domain declares and the Revit MEP adapter implements
(SAD Sec 2 dependency-inversion seam - same pattern as domain/ports.py and
domain/references/ports.py). No implementation here needs a Revit model to
exist; the real adapters (revit/adapter/mep/*) are what needs one, and those
need the two live-testing spikes flagged in MEP_SAD.md Sec 3/6 before they're
trusted.
"""


class IRoomReader(object):
    """Reads native Rooms + MEP Spaces from the active document.

    Implemented by bkbim.revit.adapter.mep.room_reader.RevitRoomReader.
    """

    def read_rooms(self):
        """:rtype: list[bkbim.domain.models... room summary, TBD at adapter build time]"""
        raise NotImplementedError


class IFixtureReader(object):
    """Reads Plumbing Fixtures + their connectors from the active document.

    Implemented by bkbim.revit.adapter.mep.fixture_reader.RevitFixtureReader.
    Needs the ConnectorManager live-testing spike (MEP_SAD.md Sec 3) before
    being trusted against real fixture families.
    """

    def read_fixtures(self, room_refs=None):
        """:rtype: list[bkbim.domain.mep.models.fixture_info.FixtureInfo]"""
        raise NotImplementedError


class IExistingSystemReader(object):
    """Finds a user-designated stack/riser connection point to route to.

    Slice 1 deliberately does not auto-discover stacks (MEP_SAD.md Sec 5) -
    the target point is picked/placed by the user, this port just resolves it
    into a plain point the domain can route to.
    """

    def resolve_target_point(self, target_ref):
        """:rtype: tuple(float, float, float)"""
        raise NotImplementedError


class IPipeWriter(object):
    """Executes a RoutingPlan as real Pipe + fitting elements, inside one
    transaction it does not own (same convention as IDimensionWriter).

    Implemented by bkbim.revit.adapter.mep.pipe_writer.RevitPipeWriter. Needs
    the Piping-API creation spike (MEP_SAD.md Sec 6) before being trusted.
    """

    def write(self, routing_plan):
        """:rtype: bkbim.core.result.Result"""
        raise NotImplementedError
