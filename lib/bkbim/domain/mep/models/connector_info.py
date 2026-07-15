# -*- coding: utf-8 -*-
"""One MEP connector on a fixture or pipe end. Pure domain data (ADR-0001) -
position/direction are plain (x, y, z) tuples in the same unit space the
adapter already uses elsewhere (mm), never a Revit XYZ.

FLOW_IN/FLOW_OUT/FLOW_BIDIRECTIONAL mirror Revit's own Connector.Direction
enum - kept as a separate field from `direction` (which is the connector's
geometric orientation vector, not its flow direction) after a real family-
authoring bug was found live 2026-07-10: a Roca shower column family had both
its water-supply connectors classified with system_classification=SANITARY
AND flow_direction=FLOW_IN - i.e. the family mislabels its own connectors'
system, but Revit still correctly records them as inlets. Checking
flow_direction in FixtureInfo.primary_connector() is what catches this kind
of mislabeling instead of trusting system_classification alone.
"""


class ConnectorInfo(object):
    FLOW_IN = u"In"
    FLOW_OUT = u"Out"
    FLOW_BIDIRECTIONAL = u"Bidirectional"

    def __init__(self, position, direction, diameter_mm, system_classification,
                 is_primary=True, flow_direction=FLOW_BIDIRECTIONAL, ref=None):
        self.position = position
        self.direction = direction
        self.diameter_mm = diameter_mm
        self.system_classification = system_classification
        # A fixture can expose more than one connector of the same system
        # classification (e.g. an overflow) - is_primary marks the one this
        # slice actually routes; secondary connectors are read but ignored.
        self.is_primary = is_primary
        self.flow_direction = flow_direction
        # Opaque handle to the real Revit Connector (ADR-0001: domain code
        # never calls methods on it) - lets RevitPipeWriter join the new
        # pipe's start connector directly to this one via Connector.ConnectTo,
        # instead of re-deriving "which connector was this" from an ElementId.
        self.ref = ref

    def __repr__(self):
        return u"<ConnectorInfo {0} dn{1} at {2}>".format(
            self.system_classification, self.diameter_mm, self.position)
