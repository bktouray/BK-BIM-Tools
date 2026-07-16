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

    def matching_connectors(self, system_classification, allowed_flow_directions=None):
        """Returns primary connectors matching the requested system and flow.

        ``allowed_flow_directions`` is explicit because the same fixture is
        viewed from opposite roles by the two real MEP consumers:

        - Sanitary Drainage needs an outlet/bidirectional connector.
        - Water Supply needs an inlet/bidirectional connector.

        Keeping the role at the call site prevents the old bug where the
        Sanitary-specific "never use an inlet as a drain outlet" rule also
        rejected valid Domestic Cold/Hot Water inlet connectors.
        """
        from bkbim.domain.mep.models.connector_info import ConnectorInfo

        if allowed_flow_directions is None:
            allowed_flow_directions = (
                ConnectorInfo.FLOW_OUT, ConnectorInfo.FLOW_BIDIRECTIONAL)

        allowed = set(allowed_flow_directions)
        return [
            c for c in self.connectors
            if (c.system_classification == system_classification and c.is_primary
                and c.flow_direction in allowed)
        ]

    def primary_connector(self, system_classification, allowed_flow_directions=None):
        matches = self.matching_connectors(
            system_classification, allowed_flow_directions=allowed_flow_directions)
        return matches[0] if matches else None

    def __repr__(self):
        return u"<FixtureInfo {0}:{1} ({2} connectors)>".format(
            self.family_name, self.type_name, len(self.connectors))
