# -*- coding: utf-8 -*-
"""A plumbing fixture as read by IFixtureReader. Pure domain data (ADR-0001) -
`ref`/`room_ref`/`level_ref` are opaque handles the Revit adapter attaches and
later reads back, same convention as ElementInfo.ref elsewhere in this suite.
"""


class FixtureInfo(object):
    def __init__(self, ref, family_name, type_name, connectors,
                 room_ref=None, level_ref=None, fixture_type_key=None):
        self.ref = ref
        self.family_name = family_name
        self.type_name = type_name
        self.connectors = connectors
        self.room_ref = room_ref
        self.level_ref = level_ref
        # Key into Standard.mep_discharge_units_by_fixture_type - a family
        # mapping concern (MEP_SAD.md Sec 8: Family Mapping persistence is
        # explicitly deferred), so this starts as a plain caller-supplied
        # string, not looked up automatically yet.
        self.fixture_type_key = fixture_type_key

    def primary_connector(self, system_classification):
        """Requires flow_direction != FLOW_IN, not just a matching
        system_classification label - a real family (Roca shower column,
        found live 2026-07-10) labels its water-supply connectors as
        SANITARY while correctly recording them as inlets. An inlet can
        never be a drain outlet regardless of what the family calls it.
        """
        from bkbim.domain.mep.models.connector_info import ConnectorInfo
        for c in self.connectors:
            if (c.system_classification == system_classification and c.is_primary
                    and c.flow_direction != ConnectorInfo.FLOW_IN):
                return c
        return None

    def __repr__(self):
        return u"<FixtureInfo {0}:{1} ({2} connectors)>".format(
            self.family_name, self.type_name, len(self.connectors))
