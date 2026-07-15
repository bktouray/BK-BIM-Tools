# -*- coding: utf-8 -*-
"""Output of the routing engine (MEP_SAD.md Sec 5): a plan, never an effect
(same "emit a plan, apply once" discipline as DimensionPlan). RevitPipeWriter
turns this into real Pipe/fitting elements inside one transaction; nothing in
this module ever touches the Revit API.
"""


class PipeSegmentPlan(object):
    def __init__(self, start_point, end_point, diameter_mm, material,
                 slope_percent=None, source_fixture_ref=None,
                 source_connector_ref=None, target_connector_ref=None):
        self.start_point = start_point
        self.end_point = end_point
        self.diameter_mm = diameter_mm
        self.material = material
        # None for a run with no gravity requirement (vertical stack drop, or
        # a future pressure-fed system) - see SlopeStrategy in path_planner.py.
        self.slope_percent = slope_percent
        self.source_fixture_ref = source_fixture_ref
        # The real Connector this segment STARTS from (opaque, ADR-0001) -
        # lets RevitPipeWriter call Connector.ConnectTo directly instead of
        # re-deriving which connector this was from source_fixture_ref alone.
        # Right for Sanitary Drainage (the fixture's own drain outlet is the
        # start of the route, flowing away to the stack).
        self.source_connector_ref = source_connector_ref
        # The real Connector this segment ENDS at - the mirror image, needed
        # once Water Supply routing was added (2026-07-10): supply flows FROM
        # a main TO the fixture, so the fixture's real connector is the
        # TARGET end of the route, not the start. Caught by actually trying
        # to wire a real Water Supply command - source_connector_ref alone
        # would have silently joined the wrong end.
        self.target_connector_ref = target_connector_ref

    def __repr__(self):
        return u"<PipeSegmentPlan dn{0} {1}->{2}>".format(
            self.diameter_mm, self.start_point, self.end_point)


class FittingPlan(object):
    KIND_ELBOW = u"Elbow"
    KIND_WYE_45 = u"Wye45"
    KIND_TEE_SANITARY = u"TeeSanitary"
    KIND_REDUCER = u"Reducer"
    KIND_COUPLING = u"Coupling"

    def __init__(self, kind, at_point, diameter_mm, angle_deg=None):
        self.kind = kind
        self.at_point = at_point
        self.diameter_mm = diameter_mm
        self.angle_deg = angle_deg

    def __repr__(self):
        return u"<FittingPlan {0} dn{1} at {2}>".format(
            self.kind, self.diameter_mm, self.at_point)


class RoutingPlan(object):
    def __init__(self, segments=None, fittings=None, warnings=None):
        self.segments = segments or []
        self.fittings = fittings or []
        self.warnings = warnings or []

    def __repr__(self):
        return u"<RoutingPlan {0} segment(s), {1} fitting(s), {2} warning(s)>".format(
            len(self.segments), len(self.fittings), len(self.warnings))
