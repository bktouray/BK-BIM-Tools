# -*- coding: utf-8 -*-
"""Generic routing engine shape (MEP_SAD.md Sec 5) - only Sanitary calls it
today, but RoutingRequest/SlopeStrategy are deliberately discipline-agnostic
per the platform brief's "never design separate routing engines per
discipline" instruction: a future pressure-fed system just omits the
SlopeStrategy.

Slice 1 scope is deliberately minimal: a single direct segment from a
fixture's connector to a user-designated target point (a stack/riser
connection - never auto-discovered, see IExistingSystemReader). No obstacle
avoidance, no automatic branch merging, no multi-level routing - see
MEP_SAD.md Sec 8 for the full non-goals list. If a direct connection proves
insufficient in real testing, THAT failure is the signal to build
pathfinding, not an assumption made here.
"""
import math

from bkbim.domain.mep.models.routing_plan import FittingPlan, PipeSegmentPlan, RoutingPlan
from bkbim.domain.mep.sanitary import slope_rules


class SlopeStrategy(object):
    """Presence/absence is the discipline-agnostic switch: Sanitary always
    supplies one; a future pressure-fed discipline (Cold Water) would not.
    """
    def __init__(self, standard):
        self.standard = standard


class RoutingStyle(object):
    """Water-supply routing conventions (product owner, 2026-07-10, after
    reviewing a reference tool's "launch mode" wall/floor/mixed choice):
    horizontal run through the ceiling void then drop vertically through the
    wall to the fixture; horizontal run under the floor then rise vertically
    through the wall; or both the horizontal and vertical legs run inside the
    wall's own cavity (no ceiling/floor void involved at all). All three are
    geometrically the SAME two-segment elbow shape (horizontal leg + vertical
    leg) - they only differ in which Z elevation the horizontal leg runs at,
    so one function (`plan_elbow_route`) implements all three; the named
    constants are just where the caller supplies that Z from.
    """
    CEILING_DROP = u"CeilingDrop"
    FLOOR_RISE = u"FloorRise"
    IN_WALL = u"InWall"


class RoutingRequest(object):
    def __init__(self, fixture, start_point, target_point, diameter_mm,
                 material, slope_strategy=None, start_connector_ref=None,
                 target_connector_ref=None):
        self.fixture = fixture
        self.start_point = start_point
        self.target_point = target_point
        self.diameter_mm = diameter_mm
        self.material = material
        self.slope_strategy = slope_strategy
        # The real Connector `start_point` was read from (opaque, ADR-0001) -
        # carried through to the resulting PipeSegmentPlan so RevitPipeWriter
        # can join the new pipe straight back to it. Right for Sanitary
        # Drainage (fixture's drain outlet IS the start).
        self.start_connector_ref = start_connector_ref
        # The mirror image for Water Supply (2026-07-10): the fixture's real
        # connector is at `target_point`, not `start_point` - supply flows
        # FROM a main TO the fixture. Carried through onto whichever segment
        # actually ends at target_point.
        self.target_connector_ref = target_connector_ref


def _horizontal_distance(p1, p2):
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)


def _implied_slope_percent(start_point, end_point):
    """Positive = falling from start to end (correct drainage direction).
    None means the connection is vertical (no horizontal run to grade).
    """
    rise = start_point[2] - end_point[2]
    run = _horizontal_distance(start_point, end_point)
    if run == 0:
        return None
    return (rise / run) * 100.0


def plan_direct_route(request):
    """The one real routing function in slice 1: a straight segment from the
    fixture's connector to the target point. Slope is validated against the
    Standard when a SlopeStrategy is present - never auto-corrected; a bad
    slope becomes a warning on the returned plan, not a silently-adjusted
    elevation.
    """
    warnings = []
    slope_percent = _implied_slope_percent(request.start_point, request.target_point)

    if request.slope_strategy is not None:
        if slope_percent is None:
            warnings.append(u"Vertical connection - no gravity slope to check.")
        elif slope_percent < 0:
            warnings.append(
                u"Run falls the wrong way (rises {0:.2f}% from the fixture) - "
                u"target point must be lower than the fixture connector.".format(
                    float(-slope_percent)))
        else:
            warnings.extend(slope_rules.check_slope(
                slope_percent, request.diameter_mm, request.slope_strategy.standard))

    segment = PipeSegmentPlan(
        start_point=request.start_point,
        end_point=request.target_point,
        diameter_mm=request.diameter_mm,
        material=request.material,
        slope_percent=slope_percent,
        source_fixture_ref=request.fixture.ref if request.fixture else None,
        source_connector_ref=request.start_connector_ref,
        target_connector_ref=request.target_connector_ref)

    return RoutingPlan(segments=[segment], fittings=[], warnings=warnings)


def plan_elbow_route(request, horizontal_z_mm):
    """Two-segment water-supply route: a horizontal leg from the start point
    to a point directly above/below the target (at horizontal_z_mm), then a
    vertical leg from there to the target's actual elevation. Builds every
    RoutingStyle (MEP_SAD.md / product owner request 2026-07-10) - only the
    caller-supplied horizontal_z_mm differs between them (ceiling void, floor
    void, or a height within the wall cavity).

    No slope validation - water supply is pressure-fed, not gravity (same
    "presence/absence of SlopeStrategy is the discipline-agnostic switch"
    rule already documented on SlopeStrategy above; this function simply
    never checks one).

    NOT yet live-tested for multi-segment pipe creation with a real elbow
    fitting inserted at the joint (MEP_SAD.md's "spike before trusting"
    discipline) - only single-segment plan_direct_route has been verified
    against a real Revit model so far.
    """
    start = request.start_point
    target = request.target_point
    elbow_point = (target[0], target[1], horizontal_z_mm)

    horizontal_segment = PipeSegmentPlan(
        start_point=start, end_point=elbow_point, diameter_mm=request.diameter_mm,
        material=request.material, slope_percent=None,
        source_fixture_ref=request.fixture.ref if request.fixture else None,
        source_connector_ref=request.start_connector_ref)

    vertical_segment = PipeSegmentPlan(
        start_point=elbow_point, end_point=target, diameter_mm=request.diameter_mm,
        material=request.material, slope_percent=None,
        target_connector_ref=request.target_connector_ref)

    fitting = FittingPlan(kind=FittingPlan.KIND_ELBOW, at_point=elbow_point,
                           diameter_mm=request.diameter_mm, angle_deg=90.0)

    return RoutingPlan(segments=[horizontal_segment, vertical_segment],
                        fittings=[fitting], warnings=[])
