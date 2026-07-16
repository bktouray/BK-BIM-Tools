# BK BIM Tools — MEP Platform Software Architecture Document (SAD)

- **Product:** BK BIM Tools — MEP Platform (long-term)
- **Status:** Living document; active slice updated 2026-07-16
- **Governing decision:** [ADR-0004](../ADR/0004-mep-vertical-slice-sanitary-first.md) — build
  Sanitary Drainage end-to-end first, extract the shared MEP framework once a
  second discipline needs it. Inherits the base suite architecture from
  [SAD.md](SAD.md) and [ADR-0001](../ADR/0001-python-engine-strategy.md)/
  [ADR-0002](../ADR/0002-vertical-slice-first.md)/[ADR-0003](../ADR/0003-extension-consolidation.md) —
  this document only adds what's new for MEP.

## Active implementation update (2026-07-16)

Sanitary Drainage remains paused. The active water-supply ribbon tools are
`MEP.panel/GenerateWaterSupplyCombined.pushbutton`, titled **Route Water
Supply**, `MEP.panel/GenerateWaterSupply.pushbutton`, titled **Route Cold
Water**, and `MEP.panel/GenerateHotWater.pushbutton`, titled **Route Hot
Water**. The combined button is an orchestration/start window over the same
Cold/Hot flows; it does not introduce separate routing logic.
Their current contract is one room, selected unconnected cold/hot fixture
inlets, one connected straight-wall path, a picked incoming water-main
point/height or selected existing main-pipe tie-in, a picked valve routing
point/height, and one selected trunk mode: in the ceiling, through the floor,
or in the walls. The valve is a routing point only in this slice; automatic
valve-family placement remains deferred. All feed, trunk, and branch pipes
are created before fittings and connector joins; failure rolls back the
complete route. Hot Water offsets its wall-derived corridor from the Cold
Water wall reference using `Standard.mep_hot_cold_spacing_mm` (50 mm office
default), with a signed per-run override for flipping sides. Cold Water has
manual user validation; Hot Water still requires manual Revit validation
before being described as live-verified.

The actual source-of-truth implementation is:

- pure graph: `domain/mep/routing/routing_graph.py`
- command: `app/commands/generate_water_supply_command.py`
- graph-to-pipes: `revit/adapter/mep/pipe_geometry_writer.py`
- fittings/connections: `revit/adapter/mep/fitting_generation_writer.py`
- transaction/UI flow: `revit/adapter/mep/water_supply_flow.py`

The older Sanitary-first sections below retain the architectural history.
Where they describe Water Supply as design-only or Revit fittings as
unverified, this update and the current files above supersede them.

Every section below names the engine requested in the original platform brief,
states what Sanitary Drainage's slice actually needs from it, and states
explicitly what is deferred. Nothing here is a promise about how Cold Water,
HVAC, or any other discipline will work — those get designed when they're built,
per ADR-0004.

---

## 1. How this fits the existing suite

MEP is a new top-level area alongside Documentation/Modeling/QA-QC/Utilities, but
it is **not a separate codebase, engine, or UI framework.** It reuses, unchanged:

- The `core → domain ← revit(adapter) / app / ui` layering and dependency-inversion
  rule from [SAD.md §2](SAD.md).
- The hybrid engine split (ADR-0001): domain/core/app stay pure IronPython-2.7-
  compatible; nothing here needs CPython-only packages, so MEP slice 1 does not
  touch the CPython leaf-module path at all.
- `bkbim.core` (settings, logging, DI, result, errors, config) as-is.
- The `Standard` profile pattern (`domain/standards/standard.py`) — extended with
  MEP-specific fields, not replaced.
- The `ModuleWindow` WPF shell and Tier 1→2→3 UI investment discipline (ship an
  alert-based Tier 1 first if the underlying engine is unproven; invest in a full
  wizard only once real usage confirms it — same call already made for Auto
  Dimension in Phase 1).
- The **Result[T] / typed-error / Transaction-ownership** contract every command
  already follows.
- The **"2nd consumer" extraction rule** (ADR-0002): a piece of logic only moves
  from `domain/mep/sanitary/` into a shared `domain/mep/` module once a second
  discipline's command actually needs it.

New package: `domain/mep/`, `revit/adapter/mep/`, `app/commands/generate_sanitary_drainage_command.py`,
`ui/views/SanitaryDrainageWizard.xaml` — additive, touches no existing module.

## 2. Folder structure (slice 1 only)

```
lib/bkbim/
├─ domain/
│  └─ mep/
│     ├─ models/
│     │  ├─ connector_info.py        # position, direction, size, system, flow (pure data)
│     │  ├─ fixture_info.py          # family/type/room/connectors/fixture-units
│     │  ├─ routing_plan.py          # ordered pipe segments + fittings, pre-creation
│     │  └─ system_classification.py # Sanitary/Vent/... enum-like constant set
│     ├─ sanitary/                   # slice-1-specific logic — NOT shared yet
│     │  ├─ dfu_sizing.py            # fixture-units -> pipe size table (data-driven)
│     │  ├─ slope_rules.py           # min/max slope per pipe size
│     │  └─ fitting_rules.py         # wye/tee/reducer selection rules
│     ├─ routing/
│     │  └─ path_planner.py          # generic shape (see §5); Sanitary is the only caller
│     ├─ validation/
│     │  └─ sanitary_validation.py   # pre-generation checks, returns Result-style warnings
│     └─ ports.py                    # IFixtureReader, IRoomReader, IPipeWriter, IExistingSystemReader
├─ revit/adapter/mep/
│  ├─ room_reader.py                 # native Rooms + MEP Spaces, active-doc scope
│  ├─ fixture_reader.py              # OST_PlumbingFixtures + ConnectorManager reads
│  ├─ pipe_writer.py                 # Pipe.Create + fitting creation, one transaction
│  └─ sanitary_system_classifier.py  # maps read fixtures -> MEP System (Sanitary/Vent)
├─ app/commands/
│  └─ generate_sanitary_drainage_command.py
└─ ui/views/
   └─ SanitaryDrainageOptions.xaml (+ .py)   # Tier 2, scoped wizard — see §7
```

Nothing under `domain/mep/routing|sizing|validation` (the *shared* future home)
gets created until Cold Water or another discipline is actually being built —
until then, Sanitary's own logic lives in `domain/mep/sanitary/` so it's obvious
what's proven-for-one-consumer versus genuinely shared.

## 3. Building Intelligence Engine — scoped to what Sanitary needs

The full brief asks this engine to understand rooms, spaces, levels, grids,
structure, links, existing systems, stacks, shafts, zones, phases, worksets, and
design options before anything else is built. Slice 1 needs a small, real subset:

**In scope now:**
- Native Revit **Rooms** + **MEP Spaces** in the active document (reuse the
  existing room/element-collection pattern already proven in the dimensioning
  tools — `FilteredElementCollector` scoped and category-filtered, not collected
  broad then filtered in Python, per the suite's existing collector-efficiency
  rule).
- **Plumbing Fixtures** (`OST_PlumbingFixtures`) with their connectors, read via
  `MEPModel.ConnectorManager` — this is genuinely new territory for this
  codebase (every prior tool read geometry/faces, never MEP connectors) and
  **needs a live-testing spike against the product owner's real fixture families
  before any sizing/routing logic is trusted**, matching the discipline already
  used for wall-reveal geometry and column references.
- **Levels** (for single-level routing only — see §5).

**Explicitly deferred until a second discipline demands them** (ADR-0004 §
"deferred"): linked-model room/fixture detection, worksets, design options,
phases, existing stack/shaft detection, building-zone grouping. A Sanitary slice
scoped to "fixtures in rooms in the active model, one level" is enough to prove
the pattern; none of the above changes the shape of `IFixtureReader`/`IRoomReader`
in a way that can't be extended additively later.

## 4. Rule Engine (Standards) — extends the existing `Standard` profile

No new engine. `domain/standards/standard.py`'s existing profile pattern (already
used for dimension offsets/tolerances) gains a second, independent set of fields
for MEP — a `Standard` is still one object per office/region, MEP fields just
ride alongside the existing dimensioning ones:

- `dfu_to_pipe_size_table` — data, not code: list of `(max_dfu, pipe_size_mm)`
  pairs. Ships with **one populated profile** (the standard the product owner
  actually specifies — this is an open input needed before `sanitary/dfu_sizing.py`
  can be written, not before the architecture; flag this as the first real
  question when slice 1 build starts).
- `min_slope_percent` / `max_slope_percent` per pipe size band.
- `default_pipe_material` / `default_pipe_type_name` (a real Revit `PipeType`
  name to look up, same pattern as `DimensionType` lookups elsewhere).

Additional standards (a second DFU table, a UK vs. IPC variant) are added as more
data entries later — never as new code paths, matching the existing "Standards
are inputs, never embedded" driver from SAD.md §1.

## 5A. Water Supply Routing — trunk-and-branch redesign (2026-07-10, refined)

The first Water Supply cut (§5/§10 below, as originally shipped) routed every
fixture independently, straight back to one shared point. Product owner tried
it live and rejected it outright: real water supply is installed as **one
continuous main distribution trunk, with short branches tapping off it** — not
a star of independent point-to-point runs. A first redesign pass (trunk built
by visiting fixtures nearest-to-furthest) was itself corrected by the product
owner before any code was written: **the trunk's path comes from the wall
corridor, not from fixture positions.** This section is that corrected
design. Nothing here is built yet — **design only, pending confirmation**,
per the product owner's explicit "do not write code immediately" instruction.

### Three-stage separation (product owner's own restructuring)
The engine is explicitly split into three stages, each independently
testable:
1. **Abstract routing graph** — pure domain, no Revit types (ADR-0001): trunk
   polyline + branch stubs + tee/elbow junction points, as plain geometry
   (points, directions, connection topology). Fully unit-testable under
   CPython, same as every other domain planner in this suite.
2. **Graph → Revit pipe geometry** — the adapter turns each graph edge into a
   real `Pipe.Create` call. No fittings yet at this stage.
3. **Fittings/accessories placement** — a separate pass over the completed
   pipe geometry: elbows and tees at every graph junction, valves (see below)
   last. Doing this as a distinct pass *after* all pipes exist (rather than
   interleaved per-segment, which is how `RevitPipeWriter` currently creates
   an elbow immediately after each pair of segments) avoids acting on
   half-built pipe state and matches the product owner's explicit ask that
   this separation "make the engine easier to test and extend."

This maps directly onto the existing layering (`domain` = pure planning,
`revit/adapter` = execution) — it formalizes and splits what
`RevitPipeWriter.write()` currently does in one pass into two.

### Trunk path = wall corridor, not fixture-chaining (the key correction)
The trunk's path is derived from the **selected wall(s)' own geometry** — a
corridor is a connected sequence of wall centerlines (offset by
`mep_in_wall_offset_mm`), independent of where any fixture sits. Fixtures do
**not** determine the trunk's shape; each fixture's tap point is found by
**projecting the fixture onto the corridor** (nearest point along the
corridor's own path to that fixture) — the same kind of point-to-curve
projection technique already proven in `nearby_wall_finder.py`
(`Curve.Project`, already live-verified, with the same "flatten Z first"
lesson learned there applying again here if the corridor curve sits at a
different Z than the fixture). A fixture's position along the corridor
(distance from the valve/origin end) determines tee order automatically —
no separate "furthest fixture" distance calculation is needed once the
corridor itself is the path; "furthest" simply falls out as "last along the
corridor."

### Incoming main and valve routing point
The active Cold Water flow now follows the requested water-main -> valve ->
fixtures sequence. The user picks an incoming water-main plan point and
height, then picks the valve plan point and height. The valve is still a
routing break/position, not an automatically placed `PipeAccessory`. Upstream
feed pipes are created as geometry first and joined in the fittings pass,
after every generated route pipe exists. Physical valve placement remains a
later, separate accessory capability: the route never creates, replaces, or
chooses valve families.

### Per-fixture branch — engineering rules (refined)
Fixture connector → perpendicular exit → straight stub into the nearest wall
(`Standard.mep_wall_penetration_mm = 80.0` — product owner's own confirmed
number) → one clean 90° turn → straight run parallel to the wall to the
corridor tap point → Tee into the trunk. Additional rules from this round:
- **Maximum branch length warning** — if a branch's total length exceeds a
  configurable threshold (new `Standard.mep_max_branch_length_mm` — not yet
  given a real value, same "ask before trusting a default" disclosure as
  every other unconfirmed `mep_*` field), emit a warning, never block the run
  (matches this suite's standing "surface problems, don't silently fail"
  rule already used throughout `sanitary_validation.py`/`slope_rules.py`).
- **Avoid doors, windows, and structural elements** — scoped honestly: full
  automatic path-*rerouting* around obstacles is the harder pathfinding
  problem this project has repeatedly deferred (ADR-0002/0004's existing
  non-goal, restated here rather than quietly reintroduced). What's buildable
  now is **validation**: check whether a branch's wall-penetration point or
  the trunk's own path overlaps a door/window opening or a structural
  element's extents, and warn if so — the same warning-not-block discipline
  as the branch-length check above. Actual automatic avoidance (nudging the
  tap point, rerouting around an obstruction) is a later refinement once
  real projects show the simple validation-and-warn version isn't enough.

### Weighted routing strategy, scoped to what's concretely buildable now
The product owner's ask — prioritize corridor adherence, minimal fittings,
and straight runs over raw shortest-path length — is **structurally satisfied
by the corridor-first design above**, not by a separate scoring/optimization
engine: since the trunk's path already comes from the wall corridor (not a
shortest-path search), and every segment is axis-aligned by construction,
"shortest total pipe length" was never a candidate objective to begin with.
A true multi-candidate weighted scorer (for cases with more than one
plausible corridor, or ambiguous tap points) is a real future capability, not
built now — the single-confirmed-corridor case doesn't need one yet, and
inventing a general scoring system ahead of a real case that needs it would
be exactly the kind of speculative generalization ADR-0002 warns against.

### Hot + Cold together
Two independent corridors/trunks (own valve origin, own tees, own branches
each), offset from each other by `Standard.mep_hot_cold_spacing_mm = 50.0`
(product owner's own confirmed number) — same corridor, offset in the
perpendicular-to-wall direction, so they stay visually parallel throughout.

### Fittings
Reuses `FittingPlan.KIND_ELBOW` (already live-verified). Needs a new, generic
`FittingPlan.KIND_TEE` (distinct from the existing, still-unused
`KIND_TEE_SANITARY`, which is a sweep/wye specifically for gravity drainage —
water supply tees have no such constraint). **`NewTeeFitting` has never been
spiked live** — a different Revit API call than the already-proven
`NewElbowFitting`, joining 3 connectors instead of 2. Needs its own rolled-
back live verification (Stage 3 above) before `RevitPipeWriter` is trusted to
create one for real.

### Scaling posture (product owner's long-term-vision note, not built now)
The graph-based Stage-1 model (corridor + tap points + junctions) is
deliberately not hardcoded to "one room" — a corridor is just a connected
sequence of wall segments, which can span more than one room, and nothing in
the abstract graph shape assumes a single bathroom. That said, **multi-room/
apartment/whole-building distribution is not being built now** — same
ADR-0002 discipline as everything else in this suite: the shape stays open to
it, but the actual capability gets built when a real multi-room case demands
it, not speculatively ahead of one.

### What this replaces
`generate_water_supply_command.run()`'s per-fixture independent-loop shape
(shipped 2026-07-10, same day) and the nearest-fixture-chaining trunk model
(also drafted and corrected same day, never built) are both superseded by
this corridor-based model. `plan_elbow_route` itself stays in
`path_planner.py` unchanged (still the right shape for a single isolated
fixture with no corridor to share, and Sanitary Drainage doesn't need it
touched either way).

## 5. Routing Engine — generic shape, Sanitary-only content

Per the brief's own instruction ("never design separate routing engines per
discipline"), the routing engine's *shape* is designed generically now, even
though only Sanitary calls it:

```
RoutingRequest(start_connectors, target, constraints)
     → path_planner.plan_route(request) → RoutingPlan (ordered segments + fitting slots)
```

- `constraints` includes an optional `SlopeStrategy` — Sanitary supplies one
  (gravity, min/max slope from the Standard); a future pressure-fed discipline
  (Cold Water) would simply not supply one. This is the one piece of
  future-proofing built in deliberately, since "does this system need slope" is
  a real branch point the brief itself calls out, not a speculative guess.
- **Slice 1 routing is deliberately simple**, matching the same "ship the direct
  case, defer obstacle avoidance" call already made for structural-dimension
  collision handling: connect each fixture's outlet connector to the nearest
  declared vertical stack/riser connection point (a point the user places or
  selects, not auto-discovered) via a direct orthogonal run. **No general
  obstacle-avoiding pathfinding, no automatic stack placement, no multi-level
  routing** in slice 1 — these are exactly the kind of heuristics ADR-0002 and
  the project's own history (side-picking, collision avoidance) warn against
  inventing upfront. If direct routing proves insufficient in real testing,
  that failure is the signal to build pathfinding — not an assumption made now.
- **Branch merging corrected to deferred, after starting to build it
  (2026-07-10):** originally scoped as in-scope for slice 1 ("unavoidable for
  any real bathroom group"). Attempting to actually design the merge geometry
  (where along a shared run a second fixture's branch joins) showed it needs
  real fixture connector positions to do safely — inventing the join-point
  heuristic without live data is exactly the class of mistake this suite's own
  history warns against (the wall_run_planner coincident-point bugs, the
  collision-avoidance neighbor-only bug — both were geometry heuristics that
  looked reasonable until tested against real positions). Slice 1 now gives
  each fixture its own direct segment to the shared target point instead —
  more pipe count than a real design would use, but honest about what hasn't
  been verified yet. Branch merging is deferred to right after the
  ConnectorManager live-testing spike (Sec 3), once real connector geometry
  exists to design and test against.

## 6. Connector Detection, Geometry, and Fitting Generation Engines

These three are grouped because slice 1 treats them as one investigation, not
three separate subsystems yet:

- **Connector detection**: `MEPModel.ConnectorManager.Connectors` off a real
  `FamilyInstance` — orientation, size, and system classification per connector.
  **Unverified in this codebase; first live spike required** before
  `fixture_reader.py` is trusted, same bar every other adapter met (e.g. the
  symbol→instance-reference technique was proven against a real column before
  Auto Dimension shipped).
- **Geometry**: reuses `domain/geometry/units.py` (mm/ft conversion) as-is; adds
  only what pipe routing needs (centerline offset math, invert-elevation
  calculation from slope) as pure functions — not a separate geometry stack.
- **Fitting generation**: Revit's Piping API (`Plumbing.Routing`/manual
  `NewElbowFitting`/`NewTeeFitting` via `Doc.Create`) is **uncharted API surface
  for this codebase** — every prior tool created annotations (dimensions,
  marks), never physical MEP elements with connector-to-connector joins. This
  needs its own live-tested spike (create one pipe + one fitting, roll back,
  inspect) before `pipe_writer.py` is trusted with a real generation run,
  exactly like the reference-provider and dimension-writer spikes in Phase 1.

## 7. Validation, Preview, and UI — Tier-appropriate for an unproven engine

- **Validation**: `sanitary_validation.py` returns the same `Result`-shaped
  warnings every other command uses (missing connector, no DFU data for a
  fixture type, fixture with no reachable stack) — not a separate validation
  framework.
- **Preview**: ships as a **plain list/table preview** (planned segments, sizes,
  lengths) inside the Tier 2 options window — not live 3D temporary geometry.
  Matches the project's own precedent: Auto Dimension shipped Tier 1 (alert)
  first and earned its Tier 2/3 WPF investment only after the engine was proven;
  a routing/fitting engine that has never been live-tested does not yet justify
  a 3D preview renderer.
- **UI**: one scoped options window, not the full 10-step wizard — Rooms/Levels
  are pre-scoped to "active view" (matching the auto-detect pattern already used
  everywhere else in this suite, no box-select); the window shows: detected
  fixture groups (enable/disable per group) → routing target picker (pick/place
  the stack connection point) → Standard/pipe-type selection → preview table →
  Generate. Steps the original 10-step wizard listed that don't apply to a
  single-discipline, single-level slice 1 (multi-system selection, per-system
  routing-preference pages) are simply not built yet.

## 8. Explicit non-goals for slice 1 (disclosed, not silently dropped)

Matching the project's standing practice of disclosing scope limits rather than
guessing past them (e.g. wall core/finish referencing, CollapseSheets):

- No HVAC Ductwork, Cable Trays, Electrical Conduits, Fire Protection, Medical
  Gas, Gas, Hydronic, or any system besides Sanitary Drainage.
- No obstacle-avoiding pathfinding, no automatic riser/stack discovery or
  placement, no multi-level system generation.
- No Family Mapping persistence system (custom-family → fixture-type memory)
  — if slice 1's fixture families need mapping at all, it's a manual per-run
  choice first, persisted only if real use shows it's needed (same "prove it
  before persisting it" bar Auto Mark's per-family prefix store already met).
- No linked-model awareness, worksets, design options, phases, or building-zone
  grouping in the Building Intelligence read.
- No AI layer changes — slice 1's command follows the existing contract
  (`generate_sanitary_drainage_command.run(structured_params)`, callable
  identically from ribbon or MCP); no new AI infrastructure is needed to reach
  that bar, per SAD.md §4.4/§5.

## 9. Performance and testing — same bar as every other module

- Batch reads, single transaction, plan-then-apply (SAD.md §5) — unchanged.
- Unit tests for every pure `domain/mep` module (`pytest tests/unit`, plain
  CPython, no Revit) — same as 200+ existing tests.
- Live verification against the product owner's real project, every write
  wrapped in a rolled-back `Transaction`, never `Commit()`, per
  [[revit-live-testing-safety]] — non-negotiable for the first real pipe/fitting
  creation given how unproven that API surface is here.
- Real dataset performance (hundreds of fixtures) is validated when it's tested,
  not designed for speculatively — matching how every prior module actually
  earned its performance characteristics (proven on the real 50-150 element
  views already in this project, not synthetic 50,000-element benchmarks).

## 10. What happens at the second discipline (Cold Water)

Per ADR-0004, only at that point does extraction happen: `domain/mep/sanitary/`'s
`path_planner` usage gets generalized into `domain/mep/routing/` once Cold
Water's command needs the same shape without slope; `dfu_sizing.py`'s pattern
(Standard-driven lookup table) gets mirrored, not necessarily shared code, since
Cold Water's sizing table has a different shape (fixture-unit → GPM/flow rate,
not DFU → drain size). This section exists so the extraction has a named next
step — it is not itself a task for slice 1.
