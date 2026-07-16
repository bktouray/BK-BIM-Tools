# -*- coding: utf-8 -*-
"""Reads Plumbing Fixtures + their connectors doc-wide (MEP_SAD.md Sec 3/6).

Live-verified 2026-07-10 against the product owner's real "Toilet Test File"
project: ConnectorManager reads (position, direction, domain, PipeSystemType,
diameter) all came back correctly for real Roca/hansgrohe/Valsir families.
`str(connector.PipeSystemType)` and `str(connector.Direction)` match this
suite's own SANITARY/VENT and FLOW_IN/FLOW_OUT/FLOW_BIDIRECTIONAL constants
character-for-character, so no translation dict is needed - the domain
constants were deliberately named to match Revit's own enum string form.

Real family bug found during that same live check: a Roca shower column
family (`Sanitary_Showers_Roca_5A9A6Exx0-...`) has both its own water-supply
connectors labelled PipeSystemType=Sanitary with Direction=In - this reader
does not correct or filter that here; it reads what the family says.
`FixtureInfo.primary_connector()` is where the flow_direction check actually
guards against picking an inlet as a drain outlet (see connector_info.py).

Level resolution uses the containing Room's LevelId first. Hosted plumbing
families commonly report FamilyInstance.LevelId = InvalidElementId even when
they are unambiguously inside a room on a real level.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import BuiltInCategory, FamilyInstance, FilteredElementCollector

from bkbim.domain.geometry.units import ft_to_mm
from bkbim.domain.mep.models.connector_info import ConnectorInfo
from bkbim.domain.mep.models.fixture_info import FixtureInfo
from bkbim.revit.adapter.element_naming import type_name as _type_name


def _position_mm(xyz):
    return (ft_to_mm(xyz.X), ft_to_mm(xyz.Y), ft_to_mm(xyz.Z))


def _direction_vector(connector):
    try:
        basis_z = connector.CoordinateSystem.BasisZ
        return (basis_z.X, basis_z.Y, basis_z.Z)
    except Exception:
        return (0.0, 0.0, 0.0)


def _read_connectors(mep_model):
    connectors = []
    try:
        connector_set = mep_model.ConnectorManager.Connectors
    except Exception:
        return connectors

    for c in connector_set:
        try:
            if str(c.Domain) != u"DomainPiping":
                continue
        except Exception:
            continue
        try:
            connectors.append(ConnectorInfo(
                position=_position_mm(c.Origin),
                direction=_direction_vector(c),
                diameter_mm=ft_to_mm(c.Radius * 2.0),
                system_classification=str(c.PipeSystemType),
                flow_direction=str(c.Direction),
                ref=c))
        except Exception:
            continue
    return connectors


def _room_ref(doc, location):
    try:
        point = location.Point
    except Exception:
        return None
    try:
        return doc.GetRoomAtPoint(point)
    except Exception:
        return None


def _level_ref(element, room):
    if room is not None:
        try:
            return room.LevelId
        except Exception:
            pass
    return getattr(element, u"LevelId", None)


def _family_name(symbol, fallback=u"Unnamed Family"):
    try:
        name = symbol.Family.Name
        if name:
            return name
    except Exception:
        pass
    return fallback


class RevitFixtureReader(object):
    def __init__(self, doc):
        self._doc = doc

    def read_fixtures(self, rooms=None):
        """rooms: optional list of RoomInfo (as returned by
        RevitRoomReader.read_rooms()) to filter to - None means every
        Plumbing Fixture in the document. Doc-wide by default, same
        convention as mark_type_reader.py, not view-scoped (MEP_SAD.md's
        "active view" UI scoping, if added later, filters the result of this
        call rather than changing it).

        :rtype: list[bkbim.domain.mep.models.fixture_info.FixtureInfo]
        """
        room_ids = None
        if rooms is not None:
            room_ids = [r.ref for r in rooms]

        elements = (FilteredElementCollector(self._doc)
                    .OfCategory(BuiltInCategory.OST_PlumbingFixtures)
                    .WhereElementIsNotElementType().ToElements())

        fixtures = []
        for elem in elements:
            if not isinstance(elem, FamilyInstance):
                continue

            mep_model = getattr(elem, u"MEPModel", None)
            connectors = _read_connectors(mep_model) if mep_model is not None else []

            room = _room_ref(self._doc, getattr(elem, u"Location", None))
            room_id = room.Id if room is not None else None
            if room_ids is not None:
                if room_id is None or room_id not in room_ids:
                    continue

            fixtures.append(FixtureInfo(
                ref=elem.Id,
                family_name=_family_name(elem.Symbol),
                type_name=_type_name(elem.Symbol),
                connectors=connectors,
                room_ref=room_id,
                level_ref=_level_ref(elem, room)))

        return fixtures
