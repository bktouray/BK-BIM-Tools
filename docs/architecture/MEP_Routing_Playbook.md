# BK BIM Tools — MEP Routing Playbook

- **Status:** Living document — required to stay in sync with the routing
  engine's code and tests. Started 2026-07-10.
- **Related:** [MEP_SAD.md](MEP_SAD.md) (overall MEP platform architecture),
  [ADR-0004](../ADR/0004-mep-vertical-slice-sanitary-first.md) (vertical-slice
  strategy this engine is built under).

## Current implementation status (2026-07-16)

The active pushbuttons are **Route Water Supply**, **Route Cold Water**, and
**Route Hot Water**. Route Water Supply is a combined start window over the
same Cold/Hot flows; the separate buttons remain available for direct
single-system runs.
Their intentionally narrow contract is: one selected room, selected fixtures
with exactly one unconnected Domestic Cold Water or Domestic Hot Water inlet,
one or more confirmed straight walls, a picked incoming water-main point/height
or existing main-pipe tie-in, and a picked valve routing point/height.
The valve is a routing break/position in this slice; no valve family is
placed yet. The user chooses the trunk routing mode: in the ceiling, through
the floor, or in the walls. That mode sets the trunk elevation; the same
routing graph then makes fixture branches drop, rise, or connect in-wall
based on the real fixture connector elevations. The upstream water-main/valve
feed follows the selected wall network in the current stable slice. Direct
open-space feed routing is deferred until real valve accessory placement is
built and validated. Two fixtures may not share the same projected tap because
cross/manifold routing is outside this slice.

Manual ribbon validation confirmed that the Cold Water route produces the
intended trunk-and-branch layout for selected fixtures on one wall. This
validates the active slice's first geometry scope. The current slice now
supports multiple connected straight walls; curved walls, branching wall
paths, disconnected wall selections, and multi-room distribution remain
deferred.

Route Hot Water reuses the same workflow with `DomesticHotWater` connector
classification and `Domestic Hot Water` Revit piping system type. Its
wall-derived trunk/corridor is offset from the Cold Water wall reference by
`Standard.mep_hot_cold_spacing_mm` (default 50 mm), with a signed per-run
override so the user can flip sides when the model calls for it. Pure-domain
tests cover Hot Water routing graph generation, but manual Revit validation
is still required before Hot Water is called live-verified.

That manual validation predates the picked incoming-main/valve routing
workflow. End-to-end manual ribbon validation of the new upstream feed and
three trunk modes is still required before they are described as
live-verified.

The implemented pipeline is the required three-stage flow:

1. `routing_graph.py` builds the pure graph.
2. `pipe_geometry_writer.py` creates all feed, trunk and branch pipes.
3. `fitting_generation_writer.py` connects fixture inlets and then creates
   feed fittings, branch elbows, trunk tees, and the final elbow.

All required creation/connection failures fail the result so
`water_supply_flow.py` rolls back the complete route. A rolled-back MCP test
in the real **Toilet Test File** created 6 pipes for two fixtures, then
created 1 tee and 3 elbows, connected both fixture inlets, and restored the
document to 0 pipes and disconnected fixture connectors after rollback.

Automatic valve placement in this pushbutton, curved/branching wall corridors,
sizing, collision avoidance, route preview, crossover bends, and multi-room
distribution remain deferred.

This is the engineering specification for the routing engine: not just what
it does, but why it behaves the way it does. A new developer should be able
to understand the routing engine by reading this document before reading any
code. Whenever the routing engine changes, this document changes with it —
code, tests, this playbook, and MEP_SAD.md (if the architecture itself
shifts) are updated together, not sequentially.

---

## 1. Vision and Design Philosophy

The Routing Graph is currently proven by the Water Supply slice. Its naming
allows another pipe-flow consumer to reuse it, but reuse is decided only when
that real second consumer is built. It is not a promise that every future MEP
discipline, especially non-pipe systems, must fit this shape.

That ambition is deliberately built **inside-out, one proven layer at a
time** — not speculatively all at once. [ADR-0002](../ADR/0002-vertical-slice-first.md)'s
rule still governs this engine specifically: nothing graduates to a shared,
generalized shape until a second real consumer actually needs it. The
routing graph's class *names* are generic (`RoutingGraph`, `RouteSegment`,
`JunctionNode`, ...) because the shape is a reasonable bet for any pipe-flow-
with-connectors discipline — that is a naming choice, not a proof. The shape
is proven only for what has actually been built and tested against it.
Genuinely different physical systems (Cable Trays, Conduits, Ductwork) are
explicitly **not** proven by this engine yet, regardless of what the class
names suggest.

**If a generated layout looks wrong or unrealistic to a plumber, the
algorithm is wrong** — this is the standing acceptance bar for this engine,
not "does it compile" or "does it produce *a* path." Optimize for
professional constructability, clean appearance, and minimal fittings. Never
optimize for shortest total pipe length.

## 2. Routing Principles

1. **The trunk's path comes from the routing corridor (wall geometry), never
   from the routing targets.** Targets (fixtures, etc.) tap into wherever the
   corridor already runs — they never determine or bend the corridor's own
   shape. This is the single most important correction this engine's design
   went through (see the Decision Log, 2026-07-10 entries) and the rule most
   worth re-reading before touching corridor logic.
2. **The main never terminates at an intermediate target.** It continues,
   uninterrupted, through the whole corridor to the furthest target; every
   intermediate target taps off via a Junction/Tee without breaking trunk
   continuity.
3. **Every trunk, feed and fixture-branch segment follows the selected wall
   corridor or a controlled perpendicular/vertical transition.** No diagonal
   fixture branches, ever. The experimental open-space direct-feed path is
   deferred because it requires a real valve accessory/connector workflow,
   not a fake tee at a visual valve drop.
4. **A target's order along the trunk is its distance *along the corridor*,
   not straight-line distance from the origin.** These differ the moment the
   corridor isn't a single straight segment — always use
   `RoutingCorridor.project(...).distance_along` for ordering, never a raw
   3D distance calculation.
5. **Warn, don't silently block or silently guess.** A branch that's too
   long, a slope that's out of range, a fixture with no matching connector —
   all of these become entries in a plan's `warnings` list, never a crash
   and never a silently-invented workaround.
6. **Three-stage separation is mandatory, not incidental:** (1) build the
   abstract routing graph with zero Revit geometry, (2) convert the graph to
   real pipes, (3) place fittings as a separate pass over the *completed*
   pipe geometry. See §14–16.

## 3. Water Supply Routing Rules

- Each current Water Supply pushbutton builds one `RoutingGraph`: Domestic
  Cold Water for Route Cold Water, or Domestic Hot Water for Route Hot Water.
- Origin = the selected valve routing point projected onto the confirmed
  wall at the chosen trunk elevation. The incoming main and valve point are
  modeled as upstream feed pipes before the trunk, but the valve itself is
  not a placed family instance yet.
- Incoming/source can be either a clicked point at a user-entered elevation
  or a selected existing main pipe. For an existing pipe, the clicked tie-in
  point is projected onto the real pipe curve. The fitting pass then attempts
  an endpoint elbow/union when the tie-in is near a pipe end, or a mid-pipe
  split + tee when the tie-in is on the pipe run. Reducers are not supported
  yet, so the selected pipe diameter is used as the source diameter
  constraint when readable.
- Feed route mode: the current stable slice uses `Follow selected walls`.
  It projects the valve/origin onto the wall network and lets the upstream
  feed bridge to that projected trunk start. The attempted
  `Direct through ceiling/floor` path is deferred until a real valve family
  placement/accessory pass supplies proper connectors at the valve drop.
- Hot/cold coordination: Cold Water uses the selected wall/corridor reference
  directly. Hot Water applies a lateral offset to that corridor and an equal
  positive vertical offset using `Standard.mep_hot_cold_spacing_mm` (50 mm
  office default). A signed per-run lateral override is allowed so negative
  values can flip the side; the vertical separation uses the absolute value.
  Zero/effectively-zero offsets are rejected because they would generate
  overlapping hot/cold pipes at the same elevation. This is a practical
  anti-clash rule, not a full collision engine. As of the Water Supply
  closeout pass, the combined Hot+Cold pushbutton also compares generated
  hot/cold pipe centerline segments and rolls back the grouped operation
  when obvious overlap/crossing/riser clashes are found.
- Ceiling/main-above-valve feed shape: when the incoming/source elevation and
  post-valve trunk elevation are both above the selected valve height, the
  upstream feed must not drop to the valve point and rise back up on the same
  vertical line. It drops before the valve, runs a 200 mm horizontal segment
  centered on the valve point at valve height, then rises after the valve and
  turns directly toward the fixture corridor. The valve-piece axis follows the
  selected wall/corridor, but the incoming main decides the drop side and the
  post-valve rise is forced to the opposite side. This leaves a real horizontal
  segment where the valve family will later be inserted and avoids a stacked
  180-degree pipe condition without adding a redundant wall-side jog.
- Trunk routing mode controls the corridor Z:
  in-ceiling uses `ceiling height above level + offset above ceiling`;
  through-floor uses `level/FFL - offset below floor`; in-wall uses a direct
  trunk elevation above level.
- Corridor = the confirmed straight wall location lines, at the selected
  trunk elevation. Selected walls may intersect without being manually split,
  but the fixture-serving route must still resolve to one non-branching path.
- The trunk starts at the projected origin and follows the wall continuously
  to the furthest selected fixture projection. Fixtures never bend or chain
  the trunk.
- For the supported same-wall case, each branch runs horizontally from the
  fixture inlet to the wall projection at the inlet elevation, then
  vertically to the trunk elevation. The first turn gets an elbow; interior
  taps get tees and the final tap gets an elbow.
- `Standard.mep_wall_penetration_mm` is a validation reference, not a forced
  segment length. `Standard.mep_max_branch_length_mm` is an optional warning
  threshold.
- Branches use their fixture connector diameter. The trunk diameter is an
  explicit user input because no approved sizing engine exists.

## 4. Sanitary / DWV Routing Rules

Sanitary Drainage shipped a direct point-to-point spike, then **paused**
2026-07-10 in favor of Water Supply (ADR-0004 update). DWV work resumed after
the Water Supply closeout with the same vertical-slice discipline: first build
the pure collector graph, then Revit geometry, then fittings.

- The legacy pushbutton path still uses `plan_direct_route` (a single straight
  segment per fixture, slope-validated against `Standard.mep_*`
  EN 12056-2-shaped fields). That is now treated as prototype behavior, not
  the target DWV engine.
- The new DWV slice starts in
  `lib/bkbim/domain/mep/sanitary/dwv_collector_graph.py`, pure domain only.
  Its first topology is the product owner's bathroom practice: the WC/toilet
  drain is the primary DN110-ish backbone to the selected stack/riser point.
  Floor drains, sinks, shower pans and similar secondary fixtures branch into
  that WC drain, rather than each routing directly to the stack and rather
  than forcing the collector to follow a wall corridor.
- Toilet/WC routing rule: start at the WC sanitary outlet, drop vertically to
  a user-configured below-slab elevation, then turn 90 degrees and run sloped
  to the main sanitary stack. The current Stage 2 slice creates the vertical
  drop pipe and the sloped backbone pipe; the physical elbow is deferred to
  the fitting pass.
- The earlier wall-derived DWV collector remains useful as a reference/future
  mode, but it is **not** the default bathroom routing assumption. Pipes do
  not usually run in walls for this workflow except sink rough-ins/stubs.
- DWV flow direction is upstream-to-downstream, ending at the stack. This is
  intentionally the inverse of Water Supply's valve-to-furthest-fixture trunk
  story. The collector Z is computed from the downstream stack elevation and a
  positive slope percentage, so every collector point falls toward the stack.
- The first slice supports fixtures on one side of the selected stack point.
  Fixtures on both sides require a two-way collector/manifold and are rejected
  before Revit geometry exists.
- DWV branch junctions plan a 45-degree wye intent, never a Water Supply tee.
  Actual Revit wye placement remains a later fitting-pass spike because office
  fitting catalogue behavior still needs live validation.
- `dwv_routing_plan_from_graph()` converts the collector graph into a
  pipe-only `RoutingPlan`: collector segments first, then fixture branch
  segments, with no fittings in the plan. The Revit adapter
  `dwv_collector_flow.py` can create those pipes in one transaction, but this
  pipe-only DWV adapter still requires manual/MCP validation before it is
  called live-verified.
- Sizing: BS EN 12056-2 shape (`Qww = K·√ΣDU`), with placeholder table values
  flagged as needing verification against the real standard — see
  MEP_SAD.md §4 and `domain/standards/standard.py`'s `mep_*` field comments.
- Fitting rule that is NOT a placeholder: a sanitary branch junction always
  gets a 45° wye, never a square tee (`domain/mep/sanitary/fitting_rules.py`)
  — a real plumbing constraint independent of which standard is in force,
  unlike Water Supply's plain Tee (pressurized systems have no equivalent
  sweep-entry requirement).

## 5. Future Routing Rules (Vent, Storm, Fire Protection, Medical Gas, etc.)

Not designed yet. Each gets its own vertical slice when its turn comes
(ADR-0002/0004), reusing `RoutingGraph`/`RoutingCorridor` where the shape
actually fits and extending — never forcing — where it doesn't. This section
stays a placeholder until one of these disciplines is actually being built;
filling it in ahead of that would be exactly the speculative-generalization
mistake ADR-0002 exists to prevent.

## 6. Corridor Selection Strategy

The corridor is **not** computed automatically from building geometry. It
comes from wall(s) the user has already confirmed via the existing wall-
detection/confirmation UI (`nearby_wall_finder.py` / `wall_confirmation_prompt.py`,
live-verified 2026-07-10). This is a deliberate scope line, not a missing
feature: genuine automatic corridor selection that reasons about which walls
form a sensible run and avoids doors/openings on its own is a much harder,
higher-risk pathfinding problem. This project's own history (the
`wall_run_planner` coincident-point bugs, the collision-avoidance neighbor-
only bug) is that geometry heuristics like this need real usage before they
can be trusted — keeping a human's wall choice in the loop avoids inventing
one blind. Fully automatic corridor selection is a real future capability,
not attempted yet.

**Multi-wall corridors:** a corridor may span more than one confirmed wall
(a connected sequence, e.g. two walls meeting at a corner) — `RoutingCorridor`
now receives an ordered, connected path from the Revit adapter. The adapter
inserts virtual nodes where selected wall centerlines intersect and rejects
disconnected, branching, looped, or curved selections for this slice.

## 7. Branch Generation Rules

See Water Supply Routing Rules (§3) for the concrete shape. General rules
that apply regardless of discipline:

- A branch is always exactly: perpendicular stub → parallel run → tap point.
  Two segments, one implied elbow at the turn, one Tee (or, for the trunk's
  final target, one Elbow instead) at the tap point.
- **Maximum branch length warning:** `Standard.mep_max_branch_length_mm` (not
  yet given a real value) — exceeding it produces a warning, never blocks
  the branch from being planned. Long branches are a real constructability
  concern (pressure loss, unsupported run length) worth flagging, not a hard
  engineering limit this engine enforces by refusing to route.
- **Door/window/structural-element avoidance:** scoped honestly to
  *validation*, not automatic rerouting. Check whether a branch's wall-entry
  point or the trunk's own path overlaps a door/window opening or a
  structural element's extents, and warn if so. Actually nudging the tap
  point or rerouting around an obstruction automatically is a real future
  capability — not built, and not silently faked as "avoidance" in the
  meantime.

## 8. Junction and Tee Rules

- A `JunctionNode` never breaks trunk continuity — the trunk pipe
  conceptually continues straight through it; the branch is what splits off,
  not the trunk.
- Every target except the one furthest along the corridor gets a Junction +
  Tee. The furthest gets an `EndNode` + a plain Elbow instead — nothing
  continues past it, so there's nothing for a Tee to preserve continuity
  for.
- Tee fitting creation (`NewTeeFitting`) is live-verified in the real test
  document, including the current two-fixture Cold Water flow (rolled back).

## 9. Fitting Placement Strategy

See Phase 3 (§16). Fittings are placed in a **separate pass, after every
pipe in the graph already exists** — not interleaved per-segment the way the
very first `RevitPipeWriter` implementation did it (create pipe, immediately
try to join/fit before the next pipe exists). This ordering avoids acting on
half-built pipe state and is easier to test/debug independently: a fitting
bug can be isolated from a pipe-geometry bug by construction, not by
inspection.

The current writer calls Revit's `NewElbowFitting` and `NewTeeFitting`
directly from graph junctions; it does not introduce a second fitting-plan
model. Reducers, couplings, and gap repair are not supported by this slice.

## 10. Pipe Sizing Philosophy

**Not built for Water Supply.** A fixture-unit-based sizing method (BS 8558 /
BS EN 806-3 or otherwise) has not been decided with the product owner —
this engine does not guess one (ADR-0004's own rule, applied to itself).
Each branch uses its routing target's connector diameter. The trunk uses an
explicit diameter entered by the user. Sanitary Drainage's sizing (BS EN
12056-2 shape) is unrelated and unaffected — see §4.

## 11. Collision Handling Strategy

Not designed. This project has direct, cautionary experience building
collision-avoidance logic before it was needed: a dimensioning-tool collision
resolver was built, shipped, and then **reverted** the same day the product
owner tried it live and found it didn't actually work in practice (see
`docs/ROADMAP.md`'s "Collision avoidance reverted" entry) — a real example of
building a plausible-sounding geometry heuristic ahead of the evidence needed
to get it right. Routing-level collision handling (pipe-vs-pipe, pipe-vs-
structure) waits for a real case that demands it.

## 12. Validation Rules

Standing rule across the whole engine: recoverable constructability concerns
become warnings; invalid inputs and required Revit creation/connection
failures become explicit failed results and trigger rollback. Nothing is
silently ignored. Concretely, so far:
- A routing target with no matching connector is skipped, with a warning
  naming which one and why (`sanitary_validation.py`, mirrored for Water
  Supply in `generate_water_supply_command.py`).
- A branch exceeding `mep_max_branch_length_mm` is still built and routed —
  just flagged (§7).
- A slope outside the configured min/max (Sanitary only) is still written —
  just flagged (`slope_rules.py`).
- A `PipeWriter` failure (an individual pipe or fitting that couldn't be
  created) is counted and reported, never allowed to silently vanish from
  the result.
- The combined Water Supply pushbutton validates newly generated Hot and Cold
  pipe centerlines before accepting the grouped operation. It is intentionally
  limited to obvious same-elevation horizontal overlap/crossing, vertical riser
  overlap, and vertical-horizontal centerline crossings. A detected clash rolls
  back both systems and reports the segment labels/approximate point; this is
  a closeout guardrail, not a general Revit clash engine.

## 13. Debug Mode Documentation

**Not built yet.** Specified by the product owner 2026-07-10 as an internal
development tool: temporary view-only graphics (distinct colors per element
— corridor, trunk, branches, junctions, valve origin, projection points),
plus IDs/lengths/flow direction, visible before any real Revit geometry is
generated, auto-cleared on tool exit or when disabled. Gated behind a
Developer Mode that does not exist yet in `bkbim.core.settings` — that gate
needs to be designed before Debug Mode's panel can be "hidden from normal
users" as specified. Sequenced *after* the Routing Graph itself (§14) exists,
since there is nothing to visualize before then. Uses the same transparent-
color-overlay technique already live-verified for room/wall highlighting
(`room_highlight.py`, `wall_confirmation_prompt.py`) as its likely
implementation basis, extended to draw graph nodes/segments rather than
whole Room/Wall elements.

## 14. Routing Graph Architecture

See `domain/mep/routing/routing_graph.py` (Phase 1, shipped 2026-07-10) for
the actual implementation; this section is the prose version of the same
thing.

- `RoutingCorridor` — an ordered polyline; `project(point)` returns the
  nearest point on the whole corridor, the distance along the corridor to
  reach it, and the perpendicular distance off it. `direction_at(distance)`
  gives the corridor's own local direction at a point along its length (used
  to know which way a branch's parallel run should point).
- `OriginNode` — where the trunk starts (a position + an opaque, optional
  ref for a future placed component).
- `JunctionNode` — a tap point where the trunk continues and a branch splits
  off.
- `EndNode` — where the trunk terminates (the furthest target's tap point).
- `BranchNode` — one target's own 2-segment path (perpendicular stub +
  parallel run) back to its `JunctionNode`.
- `RouteSegment` — the base geometric unit: a straight run with a diameter.
- `RoutingGraph` — the whole thing: an `OriginNode`, a `RoutingCorridor`, an
  ordered list of `(JunctionNode, BranchNode)` pairs (nearest-to-furthest
  along the corridor), one `EndNode`, and a `warnings` list.
- `build_routing_graph(corridor_points, targets, wall_penetration_mm,
  max_branch_length_mm=None)` — the one builder function. `targets` is
  `[(target_ref, target_point, diameter_mm), ...]` — deliberately generic,
  never "fixtures" by name, so any future discipline can supply its own
  target list without this module changing.

Zero Revit imports anywhere in this file (ADR-0001) — fully unit-tested
under plain CPython, 22 tests as of this writing
(`tests/unit/test_routing_graph.py`).

## 15. Geometry Generation Workflow (Phase 2)

**Shipped and live-verified** (`revit/adapter/mep/pipe_geometry_writer.py`).
Consumes a `RoutingGraph` and creates every non-zero trunk and branch `Pipe`,
plus optional upstream feed pipes supplied by the Water Supply adapter,
before any fitting or connector operation. A genuine segment failure returns
a failed `Result`; the caller rolls back the complete route.

## 16. Fitting Generation Workflow (Phase 3)

**Shipped and live-verified 2026-07-10** (`revit/adapter/mep/fitting_generation_writer.py`).
A separate pass, run only after every pipe from Phase 2 exists: for each
interior junction (trunk continues past it) places a Tee joining trunk-in,
trunk-out, and the branch; for the LAST junction (nothing continues past it)
places an Elbow instead, or — if the branch has zero real pipes (target
essentially already at the trunk, see §12/§19) — connects the trunk directly
to the target's own real connector with no fitting at all. Also places one
Elbow within a branch's own path wherever it has more than one real pipe
(its horizontal-to-vertical turn). Consumes the `RoutingGraph` and the pipes
Phase 2 created; never influences routing decisions itself — by the time
this runs, the path is already fixed.

Live-verified current pipeline (Phase 1 → 2 → 3 together) against the real
project on 2026-07-16: 2 trunk pipes + 4 branch pipes, 1 Tee, 3 Elbows,
2 fixture inlet connections, 0 failures. The containing transaction group
was rolled back; the document returned to 0 pipes and both inlets returned
to disconnected.

The upstream feed path for the picked incoming-main/valve workflow has a
separate MCP rollback validation: 3 temporary feed pipes + 1 trunk pipe were
created, 3 elbows joined the feed/trunk path, and the document returned to
its original pipe count after rollback. The full interactive click-through
still requires manual ribbon validation.

Direct feed can land on the first fixture tap instead of before it. In that
case the final feed pipe is the upstream trunk side for the first Tee, so the
fitting pass must include that feed connector when evaluating the first
junction. It must not first consume that connector with a separate feed-to-
trunk elbow/union.

Interactive through-floor multi-wall testing exposed a feed-to-trunk gap
when the picked valve point was near the wall but not exactly on the wall-
projected corridor. The feed builder now terminates at the wall-projected
trunk origin, preserving the valve click as a routing break while ensuring
the generated feed endpoint and trunk endpoint are coincident for Revit
fittings.

The wall-corridor adapter no longer requires manually split wall elements at
turns. It treats selected straight walls as a small plan network, inserts
virtual nodes at centerline intersections, projects the valve and fixture
targets onto that network, and returns the connected wall path that reaches
the selected fixtures. This is still a single-route slice: fixture targets
that require branching wall paths are rejected.

The valve/origin point is allowed to sit away from the fixture wall
corridor. It is projected to the nearest point on the selected wall network;
the upstream feed route bridges from the picked valve location to that
projected trunk origin. Fixture targets still need to be near the selected
fixture-wall corridor because they define the blue trunk-and-branch route.

The connected straight-wall corridor has a separate MCP rollback validation:
2 temporary trunk pipes were created around a corridor corner, 1 elbow joined
the trunk corner, and the document returned to its original pipe count after
rollback.

## 17. Accessory Placement Workflow (Phase 4)

Water Supply now exposes an optional valve-family/type picker and wires the
selected Pipe Accessory into a Phase 4 accessory pass
(`revit/adapter/mep/accessory_placement_writer.py`). The routing engine does
not depend on this; this depends on the routing engine (and on Phase 2/3
geometry already existing). If no valve type is selected, the valve remains a
routing point only.

Placing a real valve family instance was a genuinely new Revit API surface
for this codebase (nothing had placed a `FamilyInstance` accessory before -
only `Pipe`/`PipeFitting` elements via the Piping API). Reflection over
`Document.Create`'s own methods confirmed there is **no direct
Connector-based `NewFamilyInstance` overload** - the working technique is
`NewFamilyInstance(XYZ, FamilySymbol, StructuralType.NonStructural)` at the
target point, then `Connector.ConnectTo` joining the valve's own connector
to the adjacent pipe's connector. Live-verified against a real Watts ball
valve family (`LFFBVD-PEX-F1960`) already loaded in the project, placed at
the trunk's origin and connected to the first trunk pipe - worked first
try, full Phase 2→3→4 pipeline together, rolled back.

The active integration is narrower and more realistic than the original
origin-valve spike: it searches the generated upstream feed geometry for a
horizontal valve-height feed segment through the selected valve point, places
the selected valve family centered on that point, aligns it with the feed
segment, splits the pipe at the valve connector locations, deletes the
middle pipe piece, and connects the remaining pipe ends to the valve. If the
selected family has fewer than two usable pipe connectors, vertical-only
connectors, or a connector spacing longer than the available valve segment,
the full route rolls back and reports the failure.

Current scope: inline valve placement is intended first for the ceiling
bypass valve segment created by the water-main -> valve -> trunk feed rule.
Balancing valves, meters, tags, supports, insulation, automatic valve-family
mapping, and vertical inline valve placement are still not built. Manual
Revit validation remains required for each office valve family/type because
connector authoring varies by manufacturer family.

## 18. Performance Considerations

Not yet a concern at the scale tested (single-room, a handful of fixtures).
No batching/caching strategy has been needed or built. Revisit once a real
multi-room or whole-building case actually demands it (§20) — not before.

## 19. Known Limitations

- Sizing (Water Supply): none — every segment uses the target's own
  connector diameter, no fixture-unit-based calculation.
- Corridor selection: nearest walls are suggested, but the user explicitly
  confirms the final wall.
- The active pushbutton supports one connected path of straight walls. Curved
  walls, loops, branches, and disconnected wall selections are rejected.
- One branch per projected trunk tap. Coincident taps are rejected before
  Revit geometry is created.
- A branch whose horizontal distance to the confirmed wall corridor differs
  substantially from the configured rough-in distance remains a warning, not
  a silent assumption. Warnings name the fixture (family/type/id), never a
  raw Revit `Connector` object.
- Door/window/structural-element handling: validation-only (warn), no
  automatic avoidance or rerouting.
- Valve placement: optional for Water Supply when the user selects a loaded
  Pipe Accessory family/type. The active inline placement supports a
  horizontal valve-height feed segment first; other accessory types and
  vertical valve placement are deferred.
- Debug Mode / Developer Mode: not built.
- Interactive room/fixture/wall/origin picking still requires a manual
  ribbon click-through; MCP validated the exact non-interactive flow function.
- Only pipe-flow disciplines are proven (Sanitary, Water Supply so far) —
  Cable Trays/Conduits/Ductwork compatibility with this graph shape is
  unproven, regardless of the generic naming (§1).

## 20. Future Improvements

- Automatic corridor selection (with real door/opening avoidance) once a
  real project shows manual wall-confirmation is too slow in practice.
- A true multi-candidate weighted routing scorer, if a real case arises where
  more than one plausible corridor exists (not needed for the single-
  confirmed-corridor case this engine handles now).
- Multi-room / apartment / whole-building distribution, reusing this same
  graph shape (§1, §20) — not built ahead of a real case that needs it.
- Sizing engines for both Sanitary (a real EN 12056-2 verification pass) and
  Water Supply (a fixture-unit method, once chosen).
- Expand accessory placement after the inline valve slice is manually
  validated: office default valve mapping, vertical valve placement, meters,
  tags, insulation, and supports.

## 21. Architectural Decision Log

Entries here mirror durable decisions also reflected in `MEP_SAD.md`/ADRs —
this log is the narrative, dated version; the ADRs are the formal record.

### 2026-07-22 - DWV resumes with a pure sloped collector graph
- **Reason:** Water Supply is now closed out enough to resume sanitary/DWV.
  The existing Sanitary Drainage command still fans each fixture directly to a
  clicked stack point, which is useful as a spike but does not represent a
  professional DWV collector network.
- **Alternatives considered:** wire a new Revit pushbutton immediately, or
  reuse Water Supply's `RoutingGraph` branch shape directly. Immediate Revit
  work would repeat the old fitting/rollback debugging pain before the
  topology is proven. Reusing Water Supply's graph blindly would import
  pressure-water assumptions into a gravity system.
- **Decision:** add `dwv_collector_graph.py` as pure domain logic first: one
  sloped collector main draining to a selected stack, fixture outlets
  projected onto a collector corridor, and 45-degree wye fitting intents at
  branch junctions. The follow-up product-owner correction makes the default
  bathroom corridor the WC/toilet drain backbone, not a wall corridor. Add
  `dwv_collector_flow.py` as the first Revit adapter seam for creating those
  graph-derived pipe segments only.
- **Trade-offs:** this duplicates a little corridor math around the existing
  `RoutingCorridor` instead of forcing a new universal graph abstraction.
  That is intentional under ADR-0002: extract shared infrastructure only once
  DWV and Water Supply prove the same behavior is genuinely reusable.
- **Future implications:** the next DWV slice should convert this graph to
  pipe geometry without fittings, then add a separate wye/elbow fitting pass
  after live Revit validation of the office sanitary fitting catalogue.

### 2026-07-22 - Bathroom DWV defaults to WC drain backbone, not wall corridor
- **Reason:** product-owner feedback clarified the real installation method:
  bathroom DWV is not normally run through walls except sink rough-ins/stubs.
  The toilet/WC has a 110mm drain to the main sanitary stack; floor drains,
  sinks, shower pans and similar secondary fixtures connect into that WC drain
  or into a nearby secondary branch that ultimately joins the WC drain.
- **Alternatives considered:** continue with the wall-corridor collector
  model created at the start of the DWV slice. Rejected as the default because
  it encodes a routing habit the product owner does not actually use for most
  bathroom drainage.
- **Decision:** add WC-backbone planning to `dwv_collector_graph.py` and wire
  the interactive Sanitary Drainage button to that topology for the pipe-only
  Stage 2 slice. Exactly one selected WC is required; other selected sanitary
  outlets project into the WC drain backbone. The WC connector first drops to
  a configured below-slab elevation, then the backbone slopes from that drop
  point to the stack.
- **Trade-offs:** close-fixture chaining (e.g. floor drain + shower pan first,
  then into WC drain) is not automatic yet. The first version branches each
  secondary fixture into the WC backbone directly so the main topology can be
  validated in Revit before adding clustering rules.
- **Future implications:** after the WC-backbone pipe geometry is validated,
  add a secondary-fixture grouping pass with explicit distance/priority rules
  and then implement wyes/elbows/connector joins.

### 2026-07-18 - Water Supply consolidates routing prompts into one branded settings window
- **Reason:** interactive testing showed the command had become too
  fragmented: many default pyRevit popups were required before any route was
  generated, and the mixed visual styles made the tool feel less like one BK
  BIM Tools workflow.
- **Alternatives considered:** keep the pyRevit `ask_for_string` /
  `CommandSwitchWindow` chain, or build a full multi-step room/fixture/wall
  wizard immediately. The popup chain was too noisy; the full wizard is
  larger than this closeout slice.
- **Trade-offs:** numerical/configuration inputs now live in one branded
  Water Supply Routing Settings window, while true model interactions still
  use Revit's native pickers because the user must click points, pipes, and
  walls in the active model.
- **Future implications:** the next UI polish slice should brand room,
  fixture and final result dialogs so Water Supply becomes a single coherent
  BK-style wizard end to end.

### 2026-07-18 - Water Supply room, fixture and result UI becomes branded wizard flow
- **Reason:** after the settings-window pass, room selection, fixture
  selection and completion messages still used default pyRevit UI, making the
  command feel like several unrelated tools stitched together.
- **Alternatives considered:** build one huge WPF window that stays open
  while the user clicks Revit geometry. Rejected for now because Revit point,
  object and wall picks are safer through native pickers and must keep access
  to the active model view.
- **Trade-offs:** Water Supply now has a branded wizard flow for data review
  and configuration, while native Revit pickers remain for physical model
  clicks/selections. This is not yet a dockable/live wizard, but it removes
  the largest pyRevit-style UI breaks.
- **Future implications:** a later UX slice can add progress indicators,
  preview graphics and a dockable/non-modal interaction model if the native
  picker steps still feel too interruptive.

### 2026-07-18 - Water Supply adds optional inline valve accessory placement
- **Reason:** the water-main -> valve -> fixtures workflow now needs the
  picked valve point to create a real Revit valve when the user chooses a
  loaded valve family/type, rather than always remaining a routing-only
  marker.
- **Alternatives considered:** keep valves fully deferred, or place a valve
  instance without splitting/connecting the pipe. Deferral no longer matched
  the requested workflow; unconnected placement would look finished while
  leaving an invalid MEP network.
- **Trade-offs:** the first implementation is intentionally limited to a
  horizontal valve-height feed segment and depends on the selected valve
  family's connector authoring. Unsupported valve families cause a clean
  rollback instead of silent partial placement.
- **Future implications:** once manually validated with office valve
  families, the same Phase 4 pattern can grow into default valve mappings,
  vertical inline valves, meters, and other water-supply accessories without
  changing the routing graph.

### 2026-07-18 - Water Supply closeout adds pure feed tests and grouped Hot/Cold clash validation
- **Reason:** interactive ceiling-route testing found several regressions in
  the incoming-main -> valve -> trunk feed geometry and hot/cold coordination.
  These were too easy to break while tuning Revit fittings by hand.
- **Alternatives considered:** rely on manual Revit screenshots only, or build
  a full collision engine. Manual-only testing was too fragile; a full clash
  engine is beyond the Water Supply closeout scope.
- **Trade-offs:** the validator checks centerlines and obvious axis-aligned
  cases only. It does not inspect solids, insulation, hangers, clearance zones,
  or every possible diagonal/curved future route.
- **Future implications:** DWV should follow the same pattern: put fragile
  geometry decisions in pure helpers with regression tests first, then add
  narrow Revit validation passes where obvious bad models should rollback.

### 2026-07-10 — Water Supply replaces independent-point routing with trunk-and-branch
- **Reason:** product owner tried the first Water Supply cut live; every
  fixture routed independently to one shared point produced a diagonal fan
  of pipes — not how real water supply is installed.
- **Alternatives considered:** none seriously — the product owner identified
  the correct real-world topology directly (main trunk + branches + tees)
  from professional experience.
- **Trade-offs:** significantly more engine complexity than the point-to-
  point model; justified because the point-to-point model was simply wrong,
  not a simplification worth keeping.
- **Future implications:** `plan_elbow_route` (the old model) stays in
  `path_planner.py` unchanged — it's still the right shape for a single
  isolated target with no trunk to share (and Sanitary Drainage doesn't need
  it touched), just retired as *Water Supply's* entry point specifically.

### 2026-07-10 — Trunk path corrected from fixture-chaining to corridor-derived
- **Reason:** a first redesign pass (visit fixtures nearest-to-furthest to
  build the trunk) was itself corrected by the product owner before any code
  was written: the trunk's shape must come from wall geometry, not from
  fixture positions.
- **Alternatives considered:** nearest-fixture-chaining (drafted, rejected
  same day, never implemented).
- **Trade-offs:** requires a corridor abstraction and point-to-curve
  projection (more upfront geometry work) instead of a simple distance sort;
  justified because the corridor-derived path is what actually matches real
  installation practice and structurally guarantees axis-aligned, wall-
  hugging runs rather than needing that enforced as an afterthought.
- **Future implications:** "furthest fixture" is now a derived property
  (last along the corridor) rather than its own calculation — any future
  discipline reusing this graph gets that property for free.

### 2026-07-10 — Three-stage separation (graph / geometry / fittings) adopted
- **Reason:** product owner's explicit ask, to make the engine "easier to
  test and extend" and to let a wrong layout be diagnosed as a routing-logic
  bug, a geometry-generation bug, or a fitting-generation bug without
  stepping through Revit geometry to find out which.
- **Alternatives considered:** the original single-pass `RevitPipeWriter`
  approach (create pipe, immediately attempt fitting/joining before moving
  to the next segment) — this is what shipped for Sanitary Drainage and the
  first Water Supply cut.
- **Trade-offs:** more moving pieces, more explicit hand-off points between
  stages; justified by testability — Stage 1 is now fully unit-testable
  under plain CPython with zero Revit dependency, which the interleaved
  approach could never be.
- **Future implications:** `RevitPipeWriter` needs restructuring to match
  (a pipes-only pass, then a separate fittings pass) — not done yet; the
  existing writer still interleaves, and is only valid for the old,
  superseded routing model.

### 2026-07-10 — Valve placement deferred to a separate layer
- **Reason:** placing a real valve family instance is a new, unspiked Revit
  API capability (this codebase has only ever created `Pipe`/`PipeFitting`
  elements, never a placed `FamilyInstance` accessory), and no valve family/
  type has been identified in the project yet (same class of open input
  `PipeType` needed before it could be resolved).
- **Alternatives considered:** building real valve placement as part of the
  Phase-1 graph itself — rejected, since the routing graph should not depend
  on whether a physical valve ever gets placed.
- **Trade-offs:** the graph's `OriginNode.ref` stays `None`/opaque for now;
  a real valve family instance can be attached later without changing the
  graph shape.
- **Future implications:** Phase 4 (Accessories, §17) picks this up whenever
  it starts; routing and geometry generation (Phases 1–2) never wait on it.

### 2026-07-10 — Branch shape corrected from "perpendicular-then-parallel" to "horizontal-then-vertical", found live testing Phase 2
- **Reason:** the first Phase-1 implementation projected a target onto the
  corridor using full 3D distance, and built the branch as one perpendicular
  stub (toward the corridor) + one parallel run. Live-tested against a real
  wash basin whose cold-water connector sits ~400mm above the corridor's own
  height: the 3D projection let that elevation difference dominate, so the
  "perpendicular stub" moved almost entirely *vertically* instead of
  toward the wall, and the "parallel run" was really a disguised diagonal
  drop through most of the elevation change — exactly the kind of layout
  that would look wrong to a plumber. Working through the corrected
  geometry also surfaced a deeper point: for a single target routed to its
  own mathematically-nearest corridor point, the path is *always* purely
  perpendicular by construction — a genuine "parallel run to reach the tee"
  segment only makes sense when the tee's location is deliberately offset
  from the target's own nearest point (e.g. a target on a different wall
  than the corridor, needing a corner turn) — not modeled yet, a disclosed
  limitation.
- **Alternatives considered:** keeping the fixed `wall_penetration_mm` as a
  literal first-segment length regardless of the target's real distance to
  the corridor — rejected, since real data (a rough-in only ~0.09mm off the
  corridor's own line) showed a fixed 80mm stub would overshoot straight
  past the wall.
- **Fix shipped:** `RoutingCorridor.project` now projects using HORIZONTAL
  (X,Y) distance only — same "flatten Z before projecting" lesson as
  `nearby_wall_finder.py`'s wall-highlight fix earlier the same session —
  and a branch is now a horizontal segment (align with the tap point's plan
  position, at the target's own elevation) followed by a vertical segment
  (reach the corridor's elevation) — collapsing to a single segment when
  the target's own elevation already matches the corridor's. `wall_penetration_mm`
  is now a *validation* reference (warn if a target's real horizontal
  distance differs a lot from the configured expectation) rather than a
  literal segment length.
- **Trade-offs:** doesn't yet handle a target mounted on a genuinely
  different wall than the corridor — flagged as a known limitation (§19),
  not silently guessed at.
- **Future implications:** any future discipline reusing this graph inherits
  the corrected, live-verified shape automatically.

### 2026-07-10 — PipeGeometryWriter skips near-zero-length segments instead of failing
- **Reason:** live-testing Phase 2 against the same real WC/basin connectors
  showed `Pipe.Create` throwing for segments shorter than Revit's own
  minimum pipe length (a target essentially already at the corridor's line,
  or a segment reduced to floating-point noise after the branch-shape fix
  above) — 3 of 4 branch segments in the test case were this short.
- **Alternatives considered:** an exact `start == end` equality check (the
  original implementation) — insufficient, since real geometry produces
  near-zero but not exactly-zero segments (floating-point rounding, or a
  genuinely tiny but non-zero rough-in distance).
- **Fix shipped:** a length threshold (`_MIN_PIPE_LENGTH_MM = 10.0`, a
  generous margin over Revit's actual minimum) — segments shorter than this
  are counted as `skipped` (a normal outcome: the two points are already
  effectively coincident, no pipe needed), distinct from `failed` (a genuine
  `Pipe.Create` error for any other reason).
- **Trade-offs:** none significant — this only affects sub-10mm segments,
  which never represent a real, needed pipe run.
- **Future implications:** Phase 3's fitting pass needs to handle a branch
  with zero real pipes (a target essentially at the trunk already) —
  the tee/connection logic can't assume every branch has at least one pipe
  to find a connector on.
