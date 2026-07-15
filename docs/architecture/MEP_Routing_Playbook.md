# BK BIM Tools — MEP Routing Playbook

- **Status:** Living document — required to stay in sync with the routing
  engine's code and tests. Started 2026-07-10.
- **Related:** [MEP_SAD.md](MEP_SAD.md) (overall MEP platform architecture),
  [ADR-0004](../ADR/0004-mep-vertical-slice-sanitary-first.md) (vertical-slice
  strategy this engine is built under).

This is the engineering specification for the routing engine: not just what
it does, but why it behaves the way it does. A new developer should be able
to understand the routing engine by reading this document before reading any
code. Whenever the routing engine changes, this document changes with it —
code, tests, this playbook, and MEP_SAD.md (if the architecture itself
shifts) are updated together, not sequentially.

---

## 1. Vision and Design Philosophy

The Routing Graph is meant to become one of BK BIM Tools' core shared
services — every future routing tool (Water Supply, Sanitary, Vent, Storm,
Fire Protection, Gas, and eventually non-pipe systems) consumes the same
engine rather than each discipline inventing its own. This is infrastructure,
not a one-off plumbing script.

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
3. **Every segment is axis-aligned** — parallel or perpendicular to the
   corridor's own local direction. No diagonals, anywhere, ever. (The
   original, rejected Water Supply cut violated this by connecting fixtures
   directly to a shared point; that's the bug this rule exists to prevent
   from recurring.)
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

- One `RoutingGraph` per system (Cold, Hot — built independently, never
  merged into one graph even when both are requested in the same run).
- Origin = the valve's location (§9 — valve *placement* is a separate later
  concern; the routing graph only needs the valve's *position*).
- Corridor = the confirmed wall(s)' centerline(s), offset by
  `Standard.mep_in_wall_offset_mm` (not yet given a real value — ask before
  trusting a default, same disclosure rule as every other unconfirmed
  `mep_*` field).
- Branch shape: perpendicular exit from the fixture connector → straight
  stub of `Standard.mep_wall_penetration_mm` (= 80mm, product-owner-
  confirmed) toward the corridor → one 90° turn → parallel run to the tap
  point → Tee into the trunk.
- Hot + Cold together: two independent corridors/graphs, offset from each
  other by `Standard.mep_hot_cold_spacing_mm` (= 150mm, product-owner-
  confirmed), built with the same logic so they stay visually parallel.
- No sizing engine yet (§10) — each branch segment is sized from the
  fixture's own connector diameter.

## 4. Sanitary Routing Rules

Shipped, then **paused** 2026-07-10 in favor of Water Supply (ADR-0004
update) — kept here for continuity, not because it's the current focus.

- Slice 1 uses `plan_direct_route` (a single straight segment per fixture,
  slope-validated against `Standard.mep_*` EN 12056-2-shaped fields) — this
  predates the RoutingGraph model and has **not** been migrated onto it.
  Whether it should be is an open question for whenever Sanitary Drainage
  resumes, not decided now.
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
already accepts an arbitrary ordered point list, so this isn't a structural
limitation, but building the UI/adapter logic that turns "the walls the user
picked" into one ordered, connected point sequence (deciding which end
connects to which) hasn't been built yet either. Currently assumes a single
confirmed wall (or an already-ordered point list supplied directly).

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
- Tee fitting creation (`NewTeeFitting`) has **never been live-tested** in
  this codebase — a different Revit API call than the already-proven
  `NewElbowFitting` (joins 3 connectors, not 2). This needs its own rolled-
  back live spike before Phase 3 (§16) is trusted with it, same bar every
  other new Revit API surface in this project has had to clear.

## 9. Fitting Placement Strategy

See Phase 3 (§16). Fittings are placed in a **separate pass, after every
pipe in the graph already exists** — not interleaved per-segment the way the
very first `RevitPipeWriter` implementation did it (create pipe, immediately
try to join/fit before the next pipe exists). This ordering avoids acting on
half-built pipe state and is easier to test/debug independently: a fitting
bug can be isolated from a pipe-geometry bug by construction, not by
inspection.

Only `FittingPlan.KIND_ELBOW` (proven live) and the new, generic
`FittingPlan.KIND_TEE` (not yet built — distinct from the existing,
Sanitary-specific `KIND_TEE_SANITARY` sweep/wye, since water-supply tees have
no such sweep-entry requirement) are in scope for Water Supply's first cut.
Reducers, couplings, and gap repair are named in the product owner's spec
as Phase 3 responsibilities but not yet designed in any detail here.

## 10. Pipe Sizing Philosophy

**Not built for Water Supply.** A fixture-unit-based sizing method (BS 8558 /
BS EN 806-3 or otherwise) has not been decided with the product owner —
this engine does not guess one (ADR-0004's own rule, applied to itself).
Every Water Supply segment is currently sized from the routing target's own
connector diameter. Sanitary Drainage's sizing (BS EN 12056-2 shape) is
unrelated and unaffected — see §4.

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

Standing rule across the whole engine: **every check that can fail produces
a warning string on the relevant plan/graph object, never an exception and
never a silent no-op.** Concretely, so far:
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
under plain CPython, 12 tests as of this writing
(`tests/unit/test_routing_graph.py`).

## 15. Geometry Generation Workflow (Phase 2)

**Not built yet.** Will consume a `RoutingGraph` and create real `Pipe`
elements for every `RouteSegment` in the corridor + every branch — nothing
else. No fittings, no accessories, no connections at this stage; the goal is
purely to verify the graph produces the expected trunk-and-branch layout in
real geometry before any joining logic runs.

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

Live-verified full pipeline (Phase 1 → 2 → 3 together) against the real
project: 1 Tee (basin's interior junction) + 1 direct connection (WC's last
junction, zero branch pipes) + 0 elbows (basin's branch only had one real
pipe after Phase 2's skip-if-too-short rule), 0 failures, rolled back.

## 17. Accessory Placement Workflow (Phase 4)

**Shipped and live-verified 2026-07-10** (`revit/adapter/mep/accessory_placement_writer.py`),
scoped to one isolation valve at the trunk's origin - balancing valves,
meters, tags, supports, and insulation are still not built. The routing
engine does not depend on this; this depends on the routing engine (and on
Phase 2/3 geometry already existing).

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

Known simplification: the valve is placed AT the origin (where the trunk
begins) and only ONE of its two connectors is joined (to the trunk) - the
other, representing the incoming supply main, is left unconnected, since
modelling the incoming main itself is out of this engine's scope.

## 18. Performance Considerations

Not yet a concern at the scale tested (single-room, a handful of fixtures).
No batching/caching strategy has been needed or built. Revisit once a real
multi-room or whole-building case actually demands it (§20) — not before.

## 19. Known Limitations

- Sizing (Water Supply): none — every segment uses the target's own
  connector diameter, no fixture-unit-based calculation.
- Corridor selection: fully manual (user-confirmed walls), no automatic
  wall/corridor detection.
- Multi-wall corridors: structurally supported by `RoutingCorridor`, but the
  UI/adapter glue to turn multiple confirmed walls into one ordered point
  sequence doesn't exist yet — currently assumes a single wall or an
  already-ordered list.
- Door/window/structural-element handling: validation-only (warn), no
  automatic avoidance or rerouting.
- Valve placement: routing-origin-only; no real component is placed.
- Debug Mode / Developer Mode: not built.
- Tee fitting creation: not live-verified yet (§8).
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
- Real valve/accessory placement (Phase 4, §17).

## 21. Architectural Decision Log

Entries here mirror durable decisions also reflected in `MEP_SAD.md`/ADRs —
this log is the narrative, dated version; the ADRs are the formal record.

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
