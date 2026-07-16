# BK BIM Tools — Development Roadmap

- **Status:** Draft v0.1 (2026-07-05)
- Strategy: **vertical slice first, framework by extraction** (ADR-0002).

## Active MEP checkpoint — 2026-07-16

**Route Cold Water** now implements the first narrow end-to-end Water Supply
slice: one room, selected fixtures, one connected straight-wall path, picked
or existing-pipe incoming main and valve routing point, pure graph, all pipes,
then fittings and fixture connections in an atomic transaction. Cold Water has
been manually validated by the product owner. **Route Hot Water** now reuses
that same flow with Domestic Hot Water connectors/system type; it still needs
manual Revit validation.

Next MEP work should harden Cold/Hot Water from real user feedback before
adding valve-family placement, curved/branching wall corridors, sizing,
collision avoidance, coordinated hot/cold offsets, or preview.

## Phases

| Phase | Goal | Exit criteria |
|---|---|---|
| **0 — Foundation** ✅ Done 2026-07-05 | `bkbim.core` (settings, logging, DI, result, errors, config); repo/docs/test scaffolding; consolidate 3 extensions (ADR-0003). | An empty shell tool runs through the full stack; ADRs written; MCP bridge calls an `app` command. |
| **1 — Vertical slice** | Build Auto Dimension through `domain`/`app`/`revit`/`ui` from first principles (ADR-0002 correction: v5 is unverified third-party code, not a port source). | Correctness verified against real models per standard; no `DEBUG` global; unit-tested engines; WPF settings window on shared shell. |
| **2 — Harvest** | Build **Auto Tags** (Module 02); extract genuinely shared parts into the platform. | Two modules share shell + standards + presets + logging with no copy-paste. |
| **3 — Standards + Presets GA** | BS/ISO/AIA profiles, preset import/export, Settings module. | An office defines a custom standard without writing code. |
| **4 — AI/MCP integration** | NL → command routing via the existing bridge. | "Dimension Level 2 exterior walls, BS" executes deterministically. |
| **5+ — Horizontal scale** | Documentation → QA/QC → Modeling → Utilities, module by module. | Each new module is additive; touches no existing tool. |
| **Phase 2 (C#)** | Migrate mature modules; commercial installer + licensing enforcement. | — |

## Module backlog (grouped, unordered within group)

- **Documentation:** Auto Dimension (01), Auto Tags, Auto Room Tags, Auto Sheets,
  Auto Views, Auto Sections, Auto Elevations, Auto Callouts, Auto Keynotes,
  Auto Legends, Auto Detail Components, Auto Annotation.
- **Modeling:** Smart Walls, Smart Doors, Smart Windows, Rooms, Floors, Roofs, Stairs,
  Structural, Foundations, Beams, Columns.
- **QA/QC:** Standards Checker, Naming Audit, Clash Review, Missing Tag Detection,
  Sheet Review, Documentation Audit, BIM Health Reports.
- **AI:** BK AI Assistant, NL Commands, Office Standards AI, Documentation Assistant,
  AI Modeling Assistant, Prompt Library.
- **Utilities:** Project Cleaner, Batch Rename, Batch Parameter Editing, Family
  Utilities, View Manager, Sheet Manager, Revision Manager, Export/Import Utilities.
- **Settings:** Preferences, Presets, Office Standards, Logging, Updates, Licensing,
  Developer Mode.
- **MEP (long-term platform, ADR-0004):** Sanitary Drainage shipped a real
  pushbutton (room pick/highlight, wall detect/confirm, live-tested end-to-end)
  then **paused 2026-07-10** in favor of **Water Supply**. The active
  2026-07-16 slice has proven Cold Water and introduced Hot Water as the
  first reuse sibling pending manual Revit validation.
  See [architecture/MEP_SAD.md](architecture/MEP_SAD.md) and
  [ADR-0004's update](ADR/0004-mep-vertical-slice-sanitary-first.md). Still
  to come: Vent, Storm, Grey/Black Water, Rainwater Harvesting, Fire
  Protection, Medical Gas, Gas, Hydronic, HVAC Ductwork, Cable Trays,
  Electrical Conduits — each its own vertical slice; shared
  routing/rule/sizing framework extracted only once a second discipline needs it.

## Immediate next deliverables

Delivered 2026-07-05: UI/UX specification ([ux/UX_SPEC.md](ux/UX_SPEC.md)) and the
Phase-0 task plan ([architecture/PHASE_0_PLAN.md](architecture/PHASE_0_PLAN.md)),
which Phase 0 execution (below) then completed.

### Phase 0 — what actually shipped

- Ribbon tab renamed to "BK BIM Tools" (`BKDesigns.tab/bundle.yaml`); panel folders
  added for Modeling, QA/QC, AI, Utilities, Settings (empty, awaiting later modules).
- `lib/bkbim/{core,domain,app,revit,ui}` package skeleton created.
- `bkbim.core` implemented: `result.py`, `errors.py`, `logging.py`, `config.py`,
  `settings.py`, `di.py` — 24 passing unit tests under `tests/unit/`, run with plain
  CPython (`C:\Python314\python.exe -m pytest tests/unit`), no Revit required.
- Domain contracts: `SelectionSummary` model + `IElementReader` port
  (`domain/ports.py`) — the first concrete dependency-inversion seam.
- Revit adapter: `RevitElementReader` (`revit/adapter/model_reader.py`), stub
  `revit/version/revit2026.py` for future API-quirk isolation.
- App layer: `count_selected_command.run()` — the template every future command
  copies (resolve via DI, call the port, return a `Result`, never raise).
- UI: `Documentation.panel/CountSelected.pushbutton` — a ~20-line Tier-1 shim
  (per UX_SPEC §3.1), no custom WPF yet.
- MCP bridge: `revit_mcp/selection.py` route (`/selection/count/`) +
  `tools/selection_tools.py` (`count_selected_elements`) in
  `revit-mcp-python.extension` — calls the **identical** `count_selected_command.run()`
  the ribbon button calls, proving ribbon and AI share one code path.
- Exit criterion met: the full `core → app → domain → revit → ui` chain runs, and
  the same command is reachable from both the ribbon and an MCP tool.

### Phase 0 smoke test (2026-07-05) — live in Revit 2026

Ran directly against the open document via `execute_revit_code`, not just unit tests:

- Confirmed the real engine: **IronPython 2.7.12**, not IronPython 3.4 as ADR-0001
  originally assumed. ADR-0001 corrected; `bkbim.core.config`'s default engine label
  fixed to `"ironpython2.7"`.
- Found and fixed: a non-ASCII em-dash in `bkbim/__init__.py`'s docstring raised a
  `SyntaxError` under the live engine (Python 2 requires a declared encoding for
  non-ASCII source bytes). Added `# -*- coding: utf-8 -*-` headers across all
  `__init__.py` files as a guardrail.
- Found and fixed: `sys.path` is **not** shared across pyRevit extensions - the
  assumption in `revit_mcp/selection.py` that `bkbim` would just be importable was
  wrong. Fixed by explicitly inserting `BKDesigns.extension/lib` onto `sys.path`,
  computed relative to `revit_mcp/selection.py`'s own location.
- After both fixes: every `bkbim` module imports cleanly under the live engine;
  `count_selected_command.run()` correctly counted 0 selected elements, then 3
  selected walls (by category) after a live selection was made and cleared; the real
  `revit_mcp/selection.py` route function (captured via a fake `api.route()`) returned
  `{"status": "success", "count": 3, "by_category": {"Walls": 3}, ...}` with HTTP 200.
- Not yet tested: the actual HTTP endpoint end-to-end (needs a pyRevit session
  reload to pick up the new route registration) and clicking the ribbon button
  through the Revit UI itself (no UI-click tool available). Both are lower-risk than
  what was tested, since they reuse the exact same verified code path.

### ADR-0002 correction (2026-07-05)

Product owner clarified `Auto Dims SC v5` is **third-party code found on GitHub that
does not work well** - not this team's validated prior work, and confirmed "all of
them tbh, you might wanna start from scratch" when asked which failure modes apply.
No dedicated test project is available; Phase 1 is verified against general
professional judgment plus incremental live testing in the product owner's own open
Revit session. ADR-0002 updated accordingly; v5 is now reference-only, not a code
source. See `docs/architecture/PHASE_1_PLAN.md`.

### Phase 1 groundwork shipped 2026-07-05 (Stages 1-2 of PHASE_1_PLAN.md)

- `domain/geometry/units.py` (mm/ft conversion), `domain/models/element_info.py`
  (`ElementInfo`), `domain/models/grid_info.py` (`GridInfo`),
  `domain/standards/standard.py` (`Standard` profile - replaces v5's module-level
  offset/tolerance constants with per-profile data). 38 unit tests total, all passing.
- **Live smoke test found a third real bug**: `"{:.1f}".format(x)` raises
  `ValueError: Precision not allowed in integer format specifier` under IronPython
  2.7 when `x` is a plain `int` (CPython silently casts int->float; IronPython 2.7
  does not). Invisible to CPython-only tests - only surfaced by testing live in
  Revit. Fixed with explicit `float(...)` casts in both model `__repr__` methods;
  added regression tests; recorded in
  [[revit2026-ironpython-quirks]] memory for future code.
- All four new modules re-verified importing and running correctly under the live
  IronPython 2.7 engine after the fix.

### Phase 1 Stage 3 shipped 2026-07-05 — dimension planner (pure logic)

Product owner confirmed: keep it simple, iterate from testing rather than inventing
heuristics upfront. `domain/dimensioning/planner.py` (`plan_element_axis`) + new
value objects `DimensionPlan` and `AxisFaces`. Deliberately minimal: one dimension
per element per axis, fixed `default_side` from the `Standard` profile (no
side-picking heuristic, no collision avoidance, no multi-row overalls - all explicit
future iterations, not silently reintroduced). The only classification kept is
whether a nearby grid is on-edge/inside/outside the element's span, since that
determines which references are *correct* to combine, not how it looks.

18 new unit tests (56 total) cover every branch, including cases v5 itself likely
never tested: reversed input coordinate order, grids beyond snap distance, grids on
either side of the element span, and a degenerate zero-width edge case. All verified
live under the real IronPython 2.7 engine too.

### Phase 1 Stage 4 shipped 2026-07-05 — reference provider (Revit adapter)

`domain/references/ports.py` (`IReferenceProvider`) + `revit/adapter/reference_provider.py`
(`RevitReferenceProvider`). The riskiest technique - converting a family instance's
type-level symbol geometry reference into an instance-level one via stable-representation
string surgery - was split into a Revit-import-free helper
(`revit/adapter/stable_representation.py`) specifically so it's genuinely unit-testable
under plain CPython, not just reachable in a live Revit session. (First attempt wrapped
this logic inside `reference_provider.py`, which does `clr.AddReference(...)` at module
scope; that made the "pure" claim false, since the whole module - and the test - would
always skip under CPython. Caught before it shipped.)

**Definitive live verification** (not just "imports cleanly" this time): created real
dimensions inside a transaction and rolled them back, against the actual open project
(`BKD - NO.007.26_P3_WORKING REVIT FILE_ARC+STR_BKT_15-05-2026`):
- Wall solid-face path: created a valid 250mm dimension from two wall faces.
- **Structural column family-instance path** (the hard case): created a valid 200mm
  dimension using symbol->instance-ref-converted references. This is the strongest
  possible confirmation the technique works on this real model, not merely that a
  `Reference` object came back non-null.
- Both dimensions rolled back cleanly; no permanent change to the user's file.
- One environment hiccup during this stage: Revit's UI thread became briefly
  unresponsive (even the health-check endpoint timed out) after an unbounded
  collector loop; recovered on its own. Lesson: keep live Revit test loops bounded
  (test 1 element, not "loop until 3 succeed" over a 200+ element collection) -
  applied for the rest of Stage 4's verification.

61 unit tests total (5 new ones for the stable-representation helper).

### Phase 1 Stage 5 shipped 2026-07-05 — dimension writer + scoped failure policy

`revit/adapter/dimension_writer.py` (`DimensionWriter.write(plan)` - turns a
`DimensionPlan` into a real `doc.Create.NewDimension` call; does not own the
transaction, per SAD Sec 4.4) + `revit/adapter/failure_policy.py`
(`ScopedFailurePolicy` - only deletes element ids explicitly registered via
`register_created()`, fixing v5's blanket-delete-on-any-error behavior). Both
import cleanly under the live IronPython 2.7 engine.

**Incident during live verification, disclosed in full:** a first verification pass
called `t.Commit()` instead of `t.RollBack()` by mistake, which created a real,
permanent 200mm dimension in the product owner's actual project file - not a
rolled-back test like every prior check. Caught immediately: confirmed there was
exactly one dimension in the entire active view (matching the test's exact value, so
identification was unambiguous), deleted it in a follow-up transaction, and verified
the view returned to zero dimensions. Disclosed to the product owner before
continuing. **Process fix:** every exploratory live-Revit test from here on uses
`RollBack()` with no exceptions - re-ran the writer+policy test correctly afterward
and confirmed it works (200mm dimension created, zero errors/warnings from the
policy, cleanly rolled back, verified zero dimensions remained).

### Phase 1 Stages 6-7 shipped 2026-07-05 — app command, pushbutton, real verification

**Scope decision:** shipped Stage 6's UI at **Tier 1** (box-select + result alert),
not the Tier 2 WPF options panel the original plan named. Reasoning: validate the
dimensioning engine against real data first; investing in a polished options panel
before knowing the underlying logic is trustworthy risks throwaway UI work. The
Tier 2 shell is a fast-follow once real usage confirms the engine's behavior, not a
cut corner - documented here so it isn't mistaken for an oversight.

- `domain/dimensioning/ports.py` (`ISelectionReader`, `IDimensionWriter`,
  `IFailureTracker`) - `DimensionWriter` and `ScopedFailurePolicy` now formally
  implement these (multiple inheritance of a .NET interface + a plain Python port
  confirmed working live under IronPython 2.7).
- `revit/adapter/selection_reader.py` (`RevitSelectionReader`) - classifies a
  pre-picked selection into `ElementInfo`/`GridInfo`, porting v5's minimum-size and
  nested-family-instance filters (re-verified, not assumed).
- `app/commands/auto_dimension_command.py` - zero Revit imports, orchestrates
  selection -> per-axis planning -> writing -> failure tracking, returns a `Result`.
  6 new unit tests using fakes (67 total) - genuinely testable because the app layer
  stayed Revit-free.
- `Documentation.panel/AutoDimension.pushbutton/script.py` - real, working ribbon
  button: box-select grids + walls/columns, Enter, creates dimensions inside a
  transaction with the scoped failure policy attached.

**Stage 7 - real verification, not just a smoke test:** ran the full command against
a real, bounded selection from the product owner's actual open project (4 real
grids - "3","4","B","C" - plus 5 real walls and 3 real columns), inside a
transaction, always rolled back per [[revit-live-testing-safety]]. Result: **16
dimensions created, 0 skipped, 0 errors, 0 warnings.** Inspected every dimension's
actual values (`Value` is `None` for multi-segment chains - a normal Revit API
behavior, not a bug; read `.Segments[i].Value` instead): 250mm wall-thickness
segments repeated correctly, plausible column widths (100-300mm), and span segments
ranging ~1.6m-9.4m, all architecturally sensible with no anomalies. Rolled back
cleanly; confirmed zero dimensions remained afterward.

**Phase 1 (all 7 stages) is now complete**: a real, working Auto Dimension tool
exists, built from first principles, verified two ways at every stage (pure unit
tests + live Revit testing against the product owner's actual project), with none
of v5's known problems (blanket-delete failure handling, unverified reference
technique, untested heuristics) carried forward unexamined.

### What's deliberately NOT in this first iteration (by design, not oversight)

- No side-picking heuristic (fixed `Standard.default_side`), no collision avoidance,
  no multi-row overalls, no curved/angled wall or grid support, no Standards catalog
  beyond one default profile. Each is an explicit candidate for the next iteration,
  informed by real usage rather than invented upfront (ADR-0002).

## Grid Dimensions feature (2026-07-05, same-day follow-up to Phase 1)

Product owner attached two real reference drawings (`GROUND.pdf` architectural,
`str.pdf` structural) and asked for a dedicated one-click Grid Dimensions tool:
two strings per side (grid-to-grid + overall), on all sides, with adjustable
spacing (slider + type-in) and a selectable dimension style.

**Visual confirmation:** rendered both PDFs (pymupdf, after `pdftoppm` turned out
unavailable) and confirmed the exact convention already designed matches the real
drawings precisely - inner sequential string, outer overall string further out,
mirrored on both ends of each grid direction. No design changes needed; the choice
of dimension *style* (tick marks, arrows, text) is inherently handled by the
DimensionType the user picks, not something the code needs to hardcode to "match"
the drawings.

- `DimensionPlan.KIND_GRID_SEQUENTIAL` / `KIND_GRID_OVERALL` - new plan kinds.
- `domain/dimensioning/grid_chain_planner.py` (`plan_grid_chains`,
  `compute_bounding_span`) - pure logic, placing both strings on both ends of each
  orientation's perpendicular span.
  **Real bug caught before it shipped:** the first version used one perpendicular
  span for both grid orientations; vertical grids need the Y-extent and horizontal
  grids need the X-extent, which differ on any non-square building. Fixed to accept
  `x_span`/`y_span` separately, with a regression test that deliberately sets one
  span to an absurd value to prove it's never used by the wrong orientation.
- `DimensionWriter` extended with an optional `dimension_type` - verified live that
  the 4-arg `NewDimension` overload works and correctly applies the chosen style.
- `revit/adapter/element_naming.py` (`type_name`) - **corrects** the
  `Element.Name.GetValue()` fix already recorded for `WallType` in
  [[revit2026-ironpython-quirks]]: it does NOT work reliably for `DimensionType`
  (inconsistent live). New helper tries `SYMBOL_NAME_PARAM` first, with the old
  fixes as fallbacks - now a shared, reusable utility (earned via ADR-0002's
  "2nd consumer" rule: WallType naming in `bkd_walllegend.py`, now DimensionType).
- `app/commands/auto_grid_dimension_command.py` - zero Revit imports, reuses the
  same `RevitSelectionReader` as Auto Dimension (grids are already classified by
  it). 6 new unit tests.
- **First real Tier 2/3 WPF window**: `ui/views/GridDimensionOptions.xaml` +
  `grid_dimension_options.py` - dimension-style dropdown, two slider+textbox pairs
  (grid-to-grid spacing, gap to overall), Run/Cancel. Tokens inlined for this first
  window per UX_SPEC; migrates to a shared `Tokens.xaml` once a second window needs
  them (ADR-0002). Live-verified (without `ShowDialog()`, which would hang
  headlessly): XAML loads, named elements bind, slider<->textbox sync works both
  directions, out-of-range input clamps to the slider's Maximum, and garbage text
  input falls back safely instead of crashing.
- `AutoGridDimension.pushbutton` - box-select, options window, transaction-wrapped
  run.

**Live verification against the real project** (bounded, rolled back per
[[revit-live-testing-safety]]): grids "3","4","B","C" + 5 real walls, with
user-adjusted spacing (1000mm/500mm, not the defaults, proving adjustability) and
an explicitly chosen `DimensionType`. Result: **8 dimensions created** (2
orientations x 2 sides x 2 strings - exactly "all sides"), 0 skipped/errors, every
one correctly using the chosen dimension style (verified by `DimensionType.Id`),
values architecturally sensible (3212.5mm between grids 3-4, 1800mm between B-C).
Cleanly rolled back, verified zero remained.

88 unit tests total.

### Grid Dimensions usability fixes (same-day, after first real use)

Product owner tried the feature ("worked nicely") and reported two problems: box-
select was unwanted friction (wanted auto-detection), and the options window
couldn't expand so some content wasn't visible.

- **Root cause of the visibility complaint was a real layout bug, not just missing
  resizability**: `GridDimensionOptions.xaml`'s "Gap to overall string" row was
  pinned to a fixed 20px `RowDefinition` while its content (label + slider +
  textbox) needs ~55-60px - WPF clips content in fixed-height rows instead of
  growing them. Rewrote the layout to one `Auto` row per control block (margins for
  spacing, no more fixed-pixel spacer rows to keep in sync with content rows - the
  exact bookkeeping mismatch that caused this), added a trailing `*` row so any
  extra space from resizing lands below the content, and switched
  `ResizeMode="NoResize"` to `CanResizeWithGrip` with `MinWidth`/`MinHeight` so the
  window can be resized at all. Verified live by directly inspecting the
  constructed WPF objects (`ResizeMode`, `RowDefinitions[4].Height` is `Auto`, not a
  fixed value) - not just re-reading the XAML source.
- **Removed the box-select prompt entirely.** `AutoGridDimension.pushbutton` now
  auto-detects every grid/wall/column visible in the active view via
  `FilteredElementCollector` before opening the options window - zero changes
  needed in `domain`/`app` (the existing `selection_reader.read()` already accepted
  any element list regardless of source).
- Live-verified end-to-end: 111 elements auto-detected in the active view (18
  grids, 59 walls, 34 columns), 8 dimensions created correctly with 0 errors,
  cleanly rolled back.
- One environment hiccup during this round of testing: Revit briefly stopped
  responding to MCP calls entirely (health check itself timed out, then reported
  a connection failure) for a couple of minutes before recovering on its own -
  unrelated to any code change, but worth remembering that this can happen and
  isn't necessarily a sign of a code-caused hang.

## Auto Dimension for Walls and Openings (2026-07-05, third module-01 feature)

Product owner asked for "general auto dimension for walls and openings" - one
continuous dimension string per wall, from end to end, broken at every hosted
door/window's jambs. This is the standard architectural convention, distinct from
the earlier element-to-grid Auto Dimension and the grid-to-grid Grid Dimensions
feature.

**Critical finding, investigated before writing any orchestration code**: tested
`faces_for()` (the existing, already-verified technique) directly on a real door's
own family geometry - it returned a ~1280mm span, but the door's actual
`DOOR_WIDTH` parameter is 1200mm. Cross-checked against the door's real location:
the WALL's own cut geometry (its reveal faces at the opening) gave exactly
15.994-19.931 ft, matching the door's true center +/- half its real 1200mm width to
the millimeter. Confirmed the same for a 2000mm window on the same wall. **Jamb
references for wall-run dimensioning must come from the wall's own cut geometry,
not the door/window family's geometry** - the family's frame/casing can extend
slightly beyond the actual rough opening, which is architecturally correct for the
family but wrong for a dimension meant to show the opening itself.

The wall's own geometry produces MORE than 2 length-axis faces once it has
openings (the 2 outer end faces plus a converging near/far pair per opening void) -
and compound (multi-layer) walls can produce near-duplicate reveal faces per
opening (core layer vs. finish/plaster layer, offset by the finish thickness).
Resolved by matching each opening to its CLOSEST bracketing face pair by the
opening's own known location (from the door/window element itself, already
enumerable) - grounding the geometric ambiguity in reliable semantic data rather
than trying to geometrically deduplicate layer artifacts.

- `DimensionPlan.KIND_WALL_RUN`; `domain/dimensioning/wall_run_planner.py`
  (`plan_wall_run` - pure, merges the wall's own end faces + matched opening jamb
  faces into one ordered chain); `RevitReferenceProvider.wall_run_faces()` (the
  validated technique above) + new `IWallRunReader` port;
  `revit/adapter/opening_reader.py` (`group_openings_by_host` - doors/windows
  grouped by host wall, scoped to the view); `app/commands/auto_wall_opening_dimension_command.py`
  (zero Revit imports); `AutoWallOpeningDimension.pushbutton` (auto-detect, Tier 1,
  matching the pattern already established for Grid Dimensions - no box-select).
- 13 new unit tests (101 total).
- **Live-verified with real dimension creation**, not just face detection: created
  a full 6-reference wall-run string against the validated door+window wall inside
  a rolled-back transaction - segments came out as 775/2000/750/1200/175mm, summing
  exactly to the wall's real 4900mm length, with the 2000mm and 1200mm segments
  matching the window and door's real parametric widths precisely.
- **Broader verification** against 10 real walls (not just the one hand-picked
  case): 8 dimensions created, 2 skipped defensively (not guessed), 0 errors. One
  wall produced a 14-reference/13-segment chain for a 6-window facade with a
  symmetric, plausible pattern (~11.25m total). Cleanly rolled back, verified zero
  remained.
- Deliberately out of scope this iteration (consistent with the "simple, iterate"
  pattern): angled/curved walls, dimension-style selection UI (reused Standard
  defaults, matching how the original Auto Dimension shipped Tier 1 first too).

### Wall & Opening Dimension: style + spacing options, and a real "core vs finish" investigation

Product owner asked for three things: dimension-style selection, spacing, and an
option to reference wall **core** vs **finish** faces. Style + spacing were
straightforward (same proven Grid Dimensions pattern - new
`WallOpeningDimensionOptions.xaml`, one offset slider/textbox instead of two).

**Core vs finish required real investigation before building anything**, and it
surfaced a genuine limitation, disclosed to the product owner rather than guessed
around: at the door/window jambs already tested, a "duplicate face" turned out to
be a partial-height threshold detail, not a core/finish difference - and a search
across 25 real walls for a candidate at the wall's own END caps found a 75mm gap
that matched neither layer's actual finish thickness (25mm each), strongly
suggesting it was a **T-junction artifact** from an intersecting 150mm wall, not
core/finish either. Root cause: compound-structure layers (core/finish) are a
**thickness-direction** concept, while how far a wall's finish extends past its
core at an **end** is governed entirely by wall-join resolution - an unrelated,
harder Revit API problem with no simple derivation from the layer definitions.
Asked the product owner to scope this; confirmed "wall end caps only" - this
remains open, deferred pending dedicated investigation into wall join conditions,
rather than shipped as an unreliable best-effort toggle.

**Real bug caught by testing, fixed in both Grid Dimensions and Wall & Opening
Dimension**: the dimension-style dropdown was listing ALL `DimensionType` elements
(Linear, Angular, Radial, SpotElevation, ...) with no filtering - picking a
non-linear style crashed every `NewDimension` call ("The dimension type is a
non-linear dimension type"). Fixed with a new shared
`revit/adapter/dimension_type_reader.py:list_linear_dimension_types()` (filters on
`DimensionType.StyleType == DimensionStyleType.Linear`), used by both pushbuttons -
earned as a shared helper per ADR-0002's "second consumer" rule, since the same
bug existed identically in both places.

- Live-verified end-to-end: 5 dimensions created, all using a deliberately
  non-default chosen linear style, with a non-default 1500mm offset, 0 errors,
  cleanly rolled back. Confirmed 37 of the project's dimension types are
  Linear-usable (out of many more total types across all styles).

### Crossing-wall breaking (2026-07-05, product owner screenshot)

Product owner tried the feature and asked for one more thing, shown via an
annotated screenshot: long wall-run dimension strings should stop and break at
every perpendicular wall crossing them (like the blue-boxed partitions in the
image), not run straight through - matching standard practice.

**Also investigated further, per the same request: "take all dimensions from the
core."** Checked `HostObjectUtils.GetSideFaces` (only supports Interior/Exterior,
no Core option) combined with `CompoundStructure` layer widths - this DOES let you
compute the core boundary's coordinate arithmetically (validated: computed core
width matched the Structure layer's declared width exactly, 200mm). But Revit
dimensions need a real geometric `Reference`, not a computed coordinate - and a
second check confirmed the core boundary has **no exposed face anywhere** in these
fused wall solids (checked a second, fresh wall) - only the outermost finish-layer
faces are ever exposed; the core/finish seam is bonded internally, not a surface.
This is a hard limitation, not something achievable by trying harder at face
scanning - "core" referencing stays out of scope pending a fundamentally different
technique (if one exists at all for Revit's fused compound-wall geometry).

**Crossing-wall breaking, however, was clean and achievable**, reusing existing
validated infrastructure almost entirely:
- `domain/dimensioning/crossing_wall_detector.py` (`find_crossing_walls`) - pure
  logic: a candidate wall "crosses" the main wall when it runs perpendicular,
  overlaps the main wall's length span, and touches its thickness band. 11 unit
  tests, including the two real duplicate-reference bugs found below.
- No new adapter method needed for face resolution - a crossing wall's own
  thickness-direction faces are exactly its faces with normal along the main
  wall's length axis, so the already-validated `IReferenceProvider.faces_for()`
  resolves them directly.
- `auto_wall_opening_dimension_command.py` extended to merge crossing-wall break
  spans alongside opening spans before calling `plan_wall_run` (same merge
  mechanism, no new domain model needed).

**Two real duplicate-reference bugs found via live testing on the actual crossing
case, both fixed:**
1. A partition crossing a wall is sometimes modeled as two SEPARATE wall elements
   (one continuing on each side), both independently detected as "crossing" with
   coordinates differing only in the ~10th decimal place. Fixed with a dedup pass
   in `find_crossing_walls` collapsing near-coincident crossings (~3mm tolerance)
   to one.
2. Even after that fix, a crossing wall's own face can land almost exactly at the
   *main* wall's own end face (a T-junction very close to a corner) - produced two
   spurious ~0mm segments in a real dimension. Fixed with a general coincident-
   point dedup pass in `plan_wall_run` itself (the single point where every break
   source - openings, crossings, wall ends - is finally merged), rather than
   patching each pairwise coincidence source separately.
- Live-verified against the exact real wall these bugs surfaced on: clean result,
  8 refs / 7 segments, `[250, 1500, 250, 2300, 250, 950, 250]`mm summing to the
  wall's full 5750mm length - the two 250mm segments are the two real crossing
  walls' own thickness, architecturally correct and matching the screenshot's
  intent exactly. 117 unit tests total.

### Refinement round: split (not segment) at crossings; wall-type filter for core/finish

Product owner tried the crossing-wall feature and asked for two changes: (1) don't
show the crossing wall's thickness as a segment - break the dimension and start
after the wall instead (multiple separate dimensions, not one long chain with the
crossing's width as a segment); (2) still wants core-vs-finish control, and
revealed the real path to it - switching to a modeling convention where each wall
layer (blockwork, plaster, tile, ...) is its own separate wall element, which
sidesteps the "no exposed core face" problem entirely, since "core" then just
means "the structural wall type," which has real, referenceable faces.

- **`wall_run_planner.py` restructured**: `plan_wall_run` (singular) replaced with
  `plan_wall_runs` (plural) - returns `list[DimensionPlan]`, one per contiguous run
  between crossing walls, instead of one chain spanning the whole thing. A
  crossing wall's own thickness is never part of any chain; each run keeps its own
  hosted openings as internal segments. 11 rewritten unit tests.
- **`auto_wall_opening_dimension_command.py` updated** to write every plan
  returned per wall (a wall with N crossings now produces N+1 dimensions), keeping
  crossing detection and opening detection unchanged.
- **Wall-type filter, addressing "core vs finish" via the user's actual new
  workflow**: `revit/adapter/wall_type_reader.py:list_wall_types_in_view()` lists
  the distinct wall types present in a view; a new multi-select `ListBox` in
  `WallOpeningDimensionOptions.xaml` (default: all selected, so nothing changes
  unless the user narrows it) lets the user pick which type(s) count as
  dimension-worthy. Non-selected types (e.g. a separate plaster/tile wall layer)
  are excluded entirely - including as crossing-wall candidates - achieving
  "dimension from the core" exactly once the user models layers as separate walls,
  without needing an unreliable geometric core/finish detection.
- **Real bug caught live while building the wall-type lister**: `OST_Walls` can
  include non-`Wall` elements (a `FamilyInstance`, likely a curtain wall panel,
  raised `AttributeError` on `.WallType`). Fixed with an explicit `isinstance(w,
  Wall)` guard, applied in both the new lister and the main pushbutton's wall
  collection (2 of 59 raw `OST_Walls` elements in this view were non-Wall).
  **Already-useful finding**: this view already has a wall type literally named
  "0.025 PLASTER" (25mm) - confirming the product owner has begun exactly the
  layer-separated modeling this feature supports.

**Verified live:**
- Split behavior: the exact real wall with 2 crossings now produces **3 separate
  dimension elements** (1500mm, 2300mm, 950mm) - no crossing-wall-thickness
  segment anywhere, cleanly rolled back.
- Wall-type filter: correctly narrows 57 real walls down to 12 when filtered to a
  single selected type ("0.025 PLASTER"); the options window defaults to all 4
  types selected and correctly reflects deselection.
- 120 unit tests total.

### Skip already-placed dimensions (2026-07-05, same day - "safe to re-run")

Product owner: "if there's a dimension already placed, skip it - sometimes I want
to update dimensions, not redo everything." Real gap confirmed: none of the three
dimensioning tools checked for existing dimensions before creating new ones -
re-running any of them always duplicated everything already there.

**Shared mechanism, one build reused by all three tools** (not duplicated three
times): `domain/dimensioning/ports.py:IExistingDimensionChecker` +
`revit/adapter/existing_dimension_checker.py:RevitExistingDimensionChecker`.
Matches on a planned dimension's two ENDPOINT references (its overall span) against
every existing dimension's references in the view, via stable-representation string
comparison (`reference_stable_key`, added to `stable_representation.py`) - if an
existing dimension's reference set already contains both endpoints, the plan is
skipped, not duplicated. Deliberately matches on endpoints only, not the full
internal reference set: if a model change adds a new opening inside an
already-dimensioned span, the span still counts as "already handled," matching
what was actually asked for (skip if placed, don't try to detect "did the content
change").

- All three app commands (`auto_dimension_command`, `auto_grid_dimension_command`,
  `auto_wall_opening_dimension_command`) now accept this checker and skip any plan
  it flags, before ever calling the writer. Result values gained a third counter,
  `already_existing`, alongside `created`/`skipped`, so the alert message now
  reads e.g. "3 dimension(s) created (0 already existed, 0 skipped)" - clear
  feedback on what an "update" run actually did.
- A broken/erroring checker fails OPEN (falls through to creating the dimension
  normally), not closed - a checker bug must never silently block all
  dimensioning.
- **No separate "Update Dimensions" button was added.** Since skip-if-existing is
  now the default behavior everywhere, the three existing buttons already ARE the
  requested "update" workflow - re-running any of them after a model change only
  adds what's missing. A dedicated button would do exactly the same thing, so it
  was left out; a genuinely different "force full redo" mode remains possible
  later if ever requested.

**Verified live, definitively** (not just unit-tested): ran the real wall/opening
command twice, back to back, against the exact same wall inside one transaction.
First run: 3 created, 0 already existing. Second run, same wall, same context: **0
created, 3 already existing** - dimension count in the view stayed at 3, not 6.
Cleanly rolled back afterward. 128 unit tests total.

### Core vs finish wall-face referencing - actually solved this time (2026-07-06)

The earlier "Investigated, not shipped" conclusion (Phase 1, style + spacing round)
said core-face referencing wasn't achievable because a compound wall's own fused
solid geometry never exposes a face at the internal core/finish boundary. The
product owner pushed back a third time with direct counter-evidence: their own
Revit temporary dimensions, referencing core faces, on this exact model. That
evidence was taken as a real signal to dig further rather than as noise.

Re-investigation via .NET reflection (not just re-checking the wall's own
geometry) found the actual mechanism: Revit's native **Parts** feature.
`PartUtils.CreateParts` splits a compound wall into one independent Part element
per layer, and each Part's own `Solid` geometry lands exactly on that layer's
arithmetic boundary - real, referenceable faces, because it's a real, separate
element, not a boundary inside a fused solid. This is almost certainly the
mechanism behind Revit's own "core face" temporary dimension behavior.

- **`revit/adapter/wall_core_resolver.py:resolve_dimension_source(doc, wall,
  mode)`** - "finish" returns the wall itself (default, unchanged behavior);
  "core" returns the wall's core-layer Part (matched via
  `PartUtils.GetAssociatedParts` + `Part.GetMaterialIds` against
  `CompoundStructure`'s declared core layer material ids), or `None` if the wall
  has no Parts yet. Does not create Parts automatically - that's a real,
  persistent modeling decision (affects schedules/quantities/exports) left to the
  user's own "Create Parts" action.
- Wired in at the **pushbutton** (adapter) layer, not the app command:
  `wall_core_resolver.py` needs `PartUtils`, and per ADR-0001 no Revit imports
  belong below the adapter layer - the app command needed zero changes since it
  already treats `wall_ref` as an opaque handle. Both the main wall's own faces
  and each crossing wall's thickness faces are resolved the same way, so a
  crossing wall also breaks at its own core face in Core mode.
- `WallOpeningDimensionOptions.xaml` gained a "Reference from" Core/Finish choice
  (default: Finish, so nothing changes unless picked deliberately). A wall with no
  Parts in Core mode is skipped and its count reported in the completion alert -
  never silently dimensioned from finish faces as an unannounced fallback.

**Verified live** (real project, every transaction rolled back, nothing
committed): a wall with no Parts correctly resolved to `None`; after
`PartUtils.CreateParts`, resolved to its real core Part. `wall_run_faces()` on
that Part (the *same, unchanged* function used for whole walls) read a 4950mm
core-to-core span vs. 4900mm finish-to-finish on the same wall, and its hosted
door's opening read exactly 1200mm - matching the door's own `Width` parameter
exactly. `faces_for()` on the same Part (the function that resolves a *crossing*
wall's thickness faces) read 200mm core thickness vs. 250mm finish-to-finish -
confirming a crossing break also lands on the core face in Core mode.

### Parts-based Core mode reverted (2026-07-06, same day)

Product owner separately asked whether core-face referencing was possible
**without** creating Parts, since Revit's own interactive Tab-to-select-core-face
works with no Parts present. Investigated live: Revit does track the exact
core-boundary coordinates internally (degenerate marker solids sit precisely on
the arithmetic core-layer boundary), but every face and edge on that marker
geometry has `Reference = None` - unusable for `NewDimension` via the public API.
A genuine `Line` reference was found at the core centerline, but a centerline
isn't a face, and for a symmetric wall it's indistinguishable from the overall
wall centerline anyway. Re-confirmed `HostObjectUtils.GetSideFaces`'s
`ShellLayerType` truly has only Interior/Exterior. **Conclusion: the interactive
Tab-pick uses internal Revit hit-testing not exposed through the public API;
Parts remain the only API-accessible mechanism found for a real core-face
`Reference`.**

Given that, the product owner chose to switch to the **per-layer wall modeling
convention** instead (blockwork/plaster/tile as separate wall elements) rather
than require "Create Parts" as a per-wall prerequisite - the wall-type filter
(built earlier, see "Refinement round" above) already supports exactly this
convention, so nothing new was needed on that front.

**Removed:** `revit/adapter/wall_core_resolver.py` deleted; the Core/Finish radio
choice removed from `WallOpeningDimensionOptions.xaml`/`.py` (window restored to
its prior size/rows); `AutoWallOpeningDimension.pushbutton/script.py` restored to
its pre-Core-mode state. 128 unit tests still pass (none depended on the removed
adapter).

### Auto Dimension for Structural Elements (columns, footings) - new tool (2026-07-06)

Product owner: auto-dimension structural columns/footings in plan, needing two
different modes depending on the situation - "sometimes I want column edge to
grid to column edge, and an overall dimension... in other cases I measure from
column to column attached on a grid in a continuous dimension strip without
referencing the grids." Checked published structural drafting conventions before
designing (gridlines conventionally align to column centerlines; continuous
dimension strings to column faces/centerlines is documented standard practice).

Both modes share one grouping mechanism: columns/footings are grouped into
"rows" by proximity to a grid line of one orientation (the same grid line all
columns in that row snap to), ordered along the row's own axis:

- **Grid + Column mode**: alternates each column's own near/far face with its
  own nearest CROSSING grid (perpendicular to the row) across the whole row,
  reusing the same on-edge/inside/outside-of-span classification the original
  Auto Dimension tool established (`planner.py:plan_element_axis`), scoped down
  to merge many columns' segments into ONE chain instead of one dimension per
  column. A separate OVERALL string is added further out (first column's outer
  face -> last column's outer face) - the same near-string + overall-further-out
  convention Grid Dimensions already uses.
- **Continuous strip mode**: identical row grouping, but the emitted dimension
  touches only column faces, never a grid reference - no overall string either
  (the chain's own first-to-last span already is one).

Shipped: `column_grid_planner.py` (pure, 17 unit tests); `Standard` gained
`structural_chain_offset_mm`/`gap_mm` (kept independent of Grid Dimensions' own
fields so tuning one tool never silently affects the other);
`structural_type_reader.py` (mirrors `wall_type_reader.py` for Structural
Columns/Architectural Columns/Structural Foundations); `selection_reader.py`
extended to also recognize `OST_StructuralFoundation`;
`auto_structural_dimension_command.py` (zero Revit imports, 10 fake-based
tests); `StructuralDimensionOptions.xaml` (style, offset, gap, mode radio, type
multi-select); `AutoStructuralDimension.pushbutton` (auto-detect, no selection
needed). **No new adapter geometry code was needed for column face
references** - `RevitReferenceProvider.faces_for()` already worked for
FamilyInstance columns since Phase 1 Stage 4, unchanged.

**Live-verified** against the real project (both transactions rolled back): a
view with 34 structural columns + 30 isolated pad footings + 18 grids (wall/strip
footings correctly excluded - they're `WallFoundation` elements, not
`FamilyInstance`, and don't belong in a column-grid row anyway). Continuous mode:
16 dimensions created, 0 errors, no grid reference in any of them. Grid+Column
mode (first version, later corrected below): 32 dimensions created (16 rows x
chain+overall), chain dimensions carried up to 42 references for the busiest row.

### Grid+Column mode corrected; drag-to-multiselect added (2026-07-06, same day)

Product owner tried the tool immediately and caught a real design mistake:
"Grid + Column" mode chained every column in a row into ONE continuous string -
wrong. What was actually asked: "dimension individual columns on both sides
(length and width) then measure from one face to grid then finish at the
opposite face and stop there and not continue as a string to other columns."
"Continuous strip" mode was confirmed working as-is.

The fix simplified the code rather than complicating it: dropped the custom
chain-building logic and reused, unchanged, the ORIGINAL Auto Dimension tool's
own per-element classification (`planner.py:plan_element_axis`) - called once
per column per axis, giving an isolated dimension that never touches another
column's references. The separate overall string per row (first column's outer
face -> last column's outer face) was confirmed correct and untouched.
`DimensionPlan.KIND_COLUMN_GRID_CHAIN` was removed (nothing produces it anymore -
individual dimensions carry `plan_element_axis`'s own kinds). The pushbutton now
keeps `Standard.offset_first_mm` (read by the reused function) in sync with
`structural_chain_offset_mm`, so one offset slider drives everything.

Same session, a second product owner request: replace the Ctrl+click
requirement on every multi-select type-filter list (wall types, structural
types) with click-and-drag. Shipped
`ui/views/listbox_drag_select.py:enable_drag_multiselect()` - layered on top of,
not replacing, the existing click/Ctrl+click/Shift+click behavior (a plain click
still falls through to WPF's default handling; only real dragging past a small
threshold triggers range-select). Wired into both existing type-filter lists.

**Live-verified** (real project, rolled back): the corrected Grid+Column mode
against the same 64-element view produced 144 dimensions (128 individual + 16
overalls), 0 errors, with **every dimension carrying at most 3 references** -
confirming nothing chains across columns anymore. Dimension count returned to
its exact pre-existing value (8) after rollback. The drag-select module and both
updated options windows import cleanly under the real IronPython 2.7 engine;
the interactive drag gesture itself needs live mouse input in a modal dialog,
which this testing channel can't reach - flagged to the product owner to try
directly. 155 unit tests total (planner + app command tests rewritten for the
corrected behavior).

### Overall dimension corrected to be per-column, not per-row (2026-07-06, same day)

The "overall" string added in the fix above still spanned first-to-last column
across a whole row - product owner: "I don't want it to be from the first
column on the grid to the last column, I want overall dimension on individual
columns just like the column from face to grid to face." Fixed: the overall is
now scoped to ONE column, matching the detail dimension it sits alongside - that
column's own two faces, no grid reference, placed further out (offset + gap)
than the detail. Row-grouping (`group_columns_by_row`) is no longer used by
"Grid + Column" mode at all - it's needed only by "Continuous strip" mode, which
remains unaffected. Every column now gets exactly 2 dimensions per resolvable
axis: detail (face -> grid -> face, or plain face-to-face with no grid nearby)
and overall (that same column's own two faces).

**Live-verified** (real project, rolled back): the same 64-element view produced
256 dimensions - exactly the theoretical maximum (64 elements x 2 axes x 2
dimensions each), confirming every element resolved on both axes with nothing
silently skipped. Every dimension still carries at most 3 references. Dimension
count returned to its exact pre-existing value (8) after rollback. 155 unit
tests total (planner + app command tests rewritten again for the corrected
scope).

### Collision avoidance shipped (2026-07-06, same day)

Product owner sent a screenshot of a small column at 1:82 scale: its detail and
overall dimensions' "0.10"/"0.10" and "0.20" text overlapping - "can you make it
to where it auto detects overlaps and pulls it out?" `Standard.collision_shift_mm`
and `collision_max_passes` had been reserved for exactly this back in Phase 0/1
but never wired up (explicitly deferred) - this is that feature, finally built
once a concrete case demanded it.

`domain/dimensioning/collision.py:resolve_collisions(plans, standard)` - pure,
generic, not scoped to columns: any two `DimensionPlan`s sharing an `axis` with
overlapping coordinate ranges get pushed at least `collision_shift_mm` apart, in
the outward direction implied by `default_side`, over up to
`collision_max_passes` rounds. Wired into `plan_structural_dimensions()` so
every mode benefits; written generically enough that the other three
dimensioning tools could adopt it later without changes to this module.

**Real bug caught via live testing before shipping**: the first implementation
only compared NEIGHBORING plans in a perp_pos-sorted list - missed real
collisions where an unrelated, non-overlapping plan's perp_pos happened to
numerically fall between two plans that DO overlap. Confirmed live: two
different columns' dimensions sat only 100mm apart (well under the 300mm
default shift) and were never even compared, because a third plan's perp_pos
value sat between them in the sort. Fixed by checking every same-axis pair
directly - trivial cost at real-world plan counts. Always pushes whichever of a
colliding pair sits further from what it measures even further out (never
pulls the nearer one in), guaranteeing convergence rather than oscillation.

**Live-verified** in the EXACT view from the screenshot
(`L0 - FOUNDATION COLUMNS SETTING OUT`, 1:82 scale, rolled back): worst-case
same-axis overlapping gap was 100mm before the fix, exactly 300mm (the
configured shift) after - confirmed via a full worst-case-gap scan across every
generated plan, not just the one pair in the screenshot. Also surfaced (and
disclosed, not silently fixed) a separate, pre-existing issue in this view: some
columns' resolved references were rejected by `NewDimension` ("Invalid number of
references") - unrelated to collision resolution, which only ever changes
`perp_pos`, never `refs`. Dimension count returned to its exact pre-existing
value (22) after rollback. 166 unit tests total (11 new for collision
resolution, including a regression test for the neighbor-only bug).

### Collision avoidance reverted (2026-07-06, same day)

Product owner tried it in Revit: "it's not working." Rather than keep
debugging a feature not earning its complexity in practice, reverted cleanly
rather than defending the sunk cost: `domain/dimensioning/collision.py`
deleted; `plan_structural_dimensions()` restored to directly returning
`_plan_individual_column_dimensions()`/`_plan_continuous_row_chains()` with no
post-processing pass. `Standard.collision_shift_mm`/`collision_max_passes`
(predating this attempt, from the original Phase 0/1 skeleton) are left as
unused fields, available as a starting point if collision avoidance is
revisited with a different approach - a fixed model-space shift not accounting
for the view's actual scale or the dimension style's real text size is the
likely reason 300mm wasn't visually sufficient at 1:82 even after the
detection bug was fixed. 155 unit tests total (the 11 collision-specific tests
removed with the module).

### Ribbon reorganized into proper panels + minimal icons (2026-07-06)

Product owner: arrange the ribbon into categorized panels like pyRevit's own
tabs, minimal icons from Lucide/Tabler/Icons8, then suggest what to build
next. All 6 tools had sat under one catch-all "Documentation" panel since
Phase 0, never revisited as the tool count grew.

Reorganized: new **Dimensioning** panel holds all four dimension tools
(`AutoDimension`, `AutoGridDimension`, `AutoWallOpeningDimension`,
`AutoStructuralDimension`); `WallLegend` moved to **Modeling** (a modeling
helper, not dimensioning); `CountSelected` moved to **Utilities** (a
diagnostic tool). `Documentation.panel` removed; tab and panel `bundle.yaml`
files updated with explicit layout order. `QAQC`/`AI`/`Settings` remain
reserved empty panels for their first tool.

Added minimal single-color line icons (96x96 transparent PNG) for all 5
previously-iconless buttons, matching the format of the existing `WallLegend`/
`About` icons: ruler (Auto Dimension), grid (Grid Dimensions), wall (Wall &
Openings), dot-grid representing columns at grid intersections (Structural
Dimensions), checklist (Count Selected) - sourced from Lucide (ISC) and Tabler
Icons (MIT) via their public CDN SVG packages, recolored to solid black.

**Real tooling problem solved along the way**: the available SVG-to-PNG
renderer (`svglib` + `reportlab`) ignores alpha on `fillColor` - an unfilled
SVG shape rendered as opaque black instead of transparent, no matter how the
color was set. Fixed with a two-pass difference-matting technique (render
once on white, once on black, derive per-pixel alpha from the difference) -
unaffected by the alpha bug since it forces unfilled shapes to match
whichever background is active in each pass, before computing the difference.

pyRevit needs a reload (or Revit restart) before the new layout/icons appear -
bundle files were edited on disk while Revit was running.

### Smart Dimension replaces Auto Dimension; Output window silenced (2026-07-06)

Product owner: redo the original Auto Dimension tool to auto-detect structural
vs architectural plans and dimension accordingly, same options-window
interface as the other three tools, renamed "Smart Dimension." Separately:
stop pyRevit's Output window popping up on every run - "I have to go close
them every time."

**Smart Dimension is a router, not a new algorithm.** It reads `view.Discipline`
(Revit's own Architectural/Structural/... setting - already visible in the
Properties panel) and hands off ENTIRELY to whichever of the suite's two
existing, already-tested tools matches: Structural discipline -> Structural
Dimensions' pipeline (`auto_structural_dimension_command`); anything else ->
Wall & Openings' pipeline (`auto_wall_opening_dimension_command`). Same options
window as whichever tool applies, same behavior as running that tool directly -
"smart" means detecting which existing tool fits, not inventing a third one.

`AutoWallOpeningDimension.pushbutton`'s wall-context-building logic
(`_element_info_from_wall`/`_wall_context`) was extracted to
`revit/adapter/wall_context_builder.py:build_walls_with_context()` once Smart
Dimension became a second consumer (ADR-0002) - a pure refactor, re-verified
live to produce identical output.

**Removed**: the original `AutoDimension.pushbutton` (box-select, one
dimension per element per axis against the nearest grid) - `auto_dimension_command.py`
and its tests deleted as genuinely dead code. `planner.py:plan_element_axis`
was KEPT since `column_grid_planner.py` still depends on it for each column's
detail dimension in Structural Dimensions.

**Output window fix**: root cause was `bkbim.core.logging.ConsoleSink`
printing every log line to stdout, which pyRevit auto-opens an Output window
for - entirely redundant with the `forms.alert()` result popup every command
already shows. Logger is now silent by default (no sinks registered);
`ConsoleSink` still exists for opt-in debugging via
`logging.configure(sinks=[ConsoleSink()])`.

**Live-verified** (real project, both transactions rolled back): confirmed
`view.Discipline` reads `Structural` for `L0 - FOUNDATION COLUMNS SETTING OUT`
and `Architectural` for `AR-19 - GROUND FLOOR GENERAL ARRANGEMENT PLAN`. Ran
both underlying branches directly against those views: Structural branch 107
created (16 already existing, 13 skipped), Architectural branch 86 created (0
already existing, 8 skipped) - both views' dimension counts returned to their
exact pre-existing values (22 and 0) after rollback.
`build_walls_with_context()` confirmed to produce identical output
post-extraction (49 walls with context). A logger call confirmed to produce
zero console output. 147 unit tests total.

### Smart Dimension becomes a picker; Beams + Slab Dimensions added (2026-07-06)

Product owner: Smart Dimension should show a CHOICE when clicked (Wall/Grids/
Structural/future tools), not silently auto-detect and run one. Also: add
beam dimensioning to Structural Dimensions ("dimensions between beams...
taking in their widths... going from beam to beam") and a new Slab Dimensions
tool - asked to be BOTH grid-referenced AND perimeter-style.

**Smart Dimension is now a picker, still zero new dimensioning logic.**
`forms.CommandSwitchWindow.show()` (pyRevit's own standard "pick one of these
options" dialog) presents the 4 tools as explicit choices, with the detected
view Discipline shown as a hint in the message rather than a silent auto-pick.
Whichever is chosen runs that tool's own options window and command exactly
as if clicked directly. A future tool needs one line in `CHOICES` plus a
`_run_<x>()` function.

**Beams needed almost no new code** - `column_grid_planner.plan_structural_dimensions()`
was already generic over any element with a resolvable axis-aligned bounding
box. Added `OST_StructuralFraming` to `structural_type_reader.STRUCTURAL_CATEGORIES`
and a "Beam" classification branch in `RevitSelectionReader` - that's the
entire change. Both existing modes (edge-grid-edge, continuous strip) apply to
beams unchanged; continuous strip is exactly "beam to beam, taking in their
widths" as asked.

**Slab Dimensions resolved the "BOTH grid-referenced AND perimeter" ask** by
reusing the existing "Grid + Column" mode as-is: detail (face-grid-face) +
overall (face-to-face) per axis, which for a rectangular slab covers all 4
sides, referenced to grids where available. Disclosed clearly (in the options
window's own header text) that an irregular slab's true outline is still only
approximated by its bounding box, not traced edge by edge - true perimeter
tracing for non-rectangular shapes is a materially larger feature not
attempted here. Shipped `slab_type_reader.py` (Floor isn't a `FamilyInstance`,
so type lookup goes through `GetTypeId()` instead of `.Symbol`),
`SlabDimensionOptions.xaml`/`.py` (identical fields to Structural Dimensions'
window), and `SlabDimension.pushbutton` - reuses
`auto_structural_dimension_command`/`column_grid_planner` completely
unchanged, just fed Floor elements.

**Real robustness bug caught live before shipping, affects all 4 dimensioning
tools, not just this feature**: `DimensionWriter.write()` built the
dimension's `Line` object BEFORE its own try/except block, so a degenerate
(near-zero-length) plan's "Curve length is too small for Revit's tolerance"
exception crashed the ENTIRE run instead of just that one plan being skipped -
hit live on a real slab. Fixed by moving line construction inside the try
block alongside `NewDimension` itself.

**Live-verified** (real project, all rolled back): `faces_for()` confirmed
correct on real beam geometry (200mm width x 10975mm length) and real Floor
geometry (21700mm x 11800mm slab). Continuous-strip mode on 19 real beams
produced dimension strings correctly alternating gap/200mm-width/gap. Full
Slab Dimensions run (Grid + Column mode) against 9 real slabs: 33 created, 1
degenerate plan skipped cleanly post-fix instead of crashing. All dimension
counts returned to their exact pre-existing values after rollback. 147 unit
tests total (beams/slabs reuse already-tested generic domain logic; no new
tests needed).

### Structural Dimensions gets a category picker (2026-07-06, same day)

Product owner, screenshot of the options window's type list showing
"200 x 300mm" / "200 x 200mm" / "200 x 300mm" with no indication which were
columns, beams, or footings: "this is confusing, I don't know what's what."
Asked to categorize the list, or better, pick a category first
(Column/Beam/Slab/Footing) and proceed from there - and floated folding Slab
Dimensions into the same button.

Shipped `revit/adapter/structural_dimension_flow.py` - the whole
collect-elements -> options-window -> run-command -> transaction flow for ONE
category, shared by `AutoStructuralDimension.pushbutton`,
`SlabDimension.pushbutton`, and `SmartDimension.pushbutton`'s Structural/Slab
choices, so all three stay in sync. Clicking Structural Dimensions now shows a
category picker first (`forms.CommandSwitchWindow`: Column / Beam / Footing /
Slab); the options window that follows only ever lists that one category's
types, and its title/subtitle/helper text now say which category explicitly
(e.g. "Structural Element Dimensions - Beam") rather than relying on the
filtered list alone to communicate it.

`structural_type_reader.py` narrowed from an all-categories-mixed function to
`list_structural_elements_by_category(doc, view, category)` + a reusable
`types_from_elements()` helper; the old all-categories functions removed as
dead code once every consumer moved to the category-scoped path.

**Live-verified** (real project, all rolled back): `list_structural_elements_by_category()`
confirmed to return ONLY the requested category (Column -> 68, all "Structural
Columns"; Beam -> 19, all "Structural Framing"; Footing -> 0 in this view,
correctly empty not erroring). Constructed the options window directly (no
modal shown, to keep automated testing non-blocking) with
`category_label="Beam"` and confirmed title/subtitle/helper text all correctly
say "Beam" and the type list contains exactly the one real beam type in the
view, no cross-category contamination. 147 unit tests total (no change - this
is Revit-import-only UI/adapter code).

### Branded category picker; per-category wording; 300mm defaults (2026-07-06)

Product owner tried the category picker: "I don't like the default pyRevit
interface when I click Structural Dimensions, make it nice." Also caught a
real copy-paste artifact - picking "Beam" still showed radio buttons reading
"Column edge - grid - column edge..." Also asked for a uniform 300mm default
offset across every tool.

Shipped `ui/views/CategoryPicker.xaml`/`category_picker.py` - a branded WPF
picker (same visual language as every options window) replacing pyRevit's
default `forms.CommandSwitchWindow` everywhere it was used: Structural
Dimensions' category picker AND Smart Dimension's top-level tool picker.
`structural_dimension_options.py` gained bespoke per-category wording
(Column/Beam/Footing) - title, subtitle, BOTH mode-radio descriptions, and
the type-list helper text are all genuinely written for that category, not a
shared template with the header swapped. Beam's wording explicitly mentions
"measuring beam to beam and taking in each beam's own width," matching the
original ask.

`Standard`'s three actively-used offset defaults (`offset_first_mm`,
`grid_chain_offset_mm`, `structural_chain_offset_mm`) changed from
800/1500/800mm to a uniform 300mm - gap fields left unchanged, only "offsets"
were asked for.

**Live-verified**: `default_standard()` confirmed to report 300.0 for all
three offset fields. Constructed the branded picker and the Beam/Column/
Footing options windows directly (no modal shown, keeping automated testing
non-blocking) and confirmed every category's title, subtitle, and both mode
radios are genuinely distinct - no leftover copy-paste text from any other
category. 147 unit tests total.

### Slab Dimensions: two independent modes; standalone pushbutton removed (2026-07-07)

Product owner: "recheck the slab dimension tool. I want two options, one
from grid to slab edges, and another measuring all edges of the slab. And
since its already in the structural dimension push button, having its own
pushbutton is seems useless." Slab Dimensions had been reusing
`MODE_GRID_AND_COLUMN`, which always bundles a detail (grid-referenced)
dimension together with an overall (edge-to-edge) one in the same run - not
the two separately-selectable options asked for.

Shipped `MODE_GRID_ONLY`/`MODE_OVERALL_ONLY` in `column_grid_planner.py`, via
`include_detail`/`include_overall` flags on the existing
`_plan_individual_column_dimensions` - no new domain logic beyond gating which
of the two dimension kinds gets emitted. `MODE_OVERALL_ONLY` places its
dimension at the plain offset (not offset+gap) since it's the only string in
the run and has nothing else to clear.

Rebuilt `SlabDimensionOptions.xaml`/`slab_dimension_options.py` around the two
new modes: "Grid to slab edges" and "All edges of the slab," dropping the
now-meaningless "Gap to overall string" field entirely (gap only matters when
detail and overall coexist in the same run, which Slab no longer does). The
offset field's label switches between "Offset from grid line (mm)" and
"Offset from slab edge (mm)" depending on which mode is selected, matching
the "personalize the contents of each window" precedent from the category
picker work.

Deleted the standalone `SlabDimension.pushbutton` entirely and removed it
from `Dimensioning.panel/bundle.yaml`'s layout - reaching Slab through
Structural Element Dimensions' category picker (or Smart Dimension) already
covered it, so the dedicated ribbon button was pure duplication. Smart
Dimension's own "Slab Dimensions" menu entry was kept, since the complaint
was specifically about the standalone pushbutton.

**Live-verified** (real project, rolled back): ran the full Slab Dimensions
pipeline against the project's one visible slab (18 grids) in both new modes
- `MODE_GRID_ONLY` and `MODE_OVERALL_ONLY` each created 2 dimensions (X + Y
axis) - dimension count before/after confirmed identical (0), no residue.
Constructed `SlabDimensionOptionsWindow` directly against the real slab types
and confirmed title, offset label, both radio labels, and the 300mm default
offset are all correct. Confirmed `structural_dimension_flow.CATEGORIES`
still includes `"Slab"`. Added 4 new unit tests for the two new modes; 151
unit tests total, zero regressions.

### Slab Dimensions rebuilt per-face; extension renamed; icons lightened; grid 2D/3D toggle added (2026-07-07, same-day follow-up)

The fix above only split `MODE_GRID_AND_COLUMN`'s bundled detail+overall into
two selectable modes - it still shared ONE grid (nearest the element's
CENTER) across both faces of an axis, via the reused per-axis
`plan_element_axis`. Product owner tried it: "I want the reference to be
taken from the closest grid to that specific slab corner and same for every
corner, not the center grid to the outmost edge." Also: "I don't want it on
just two sides, I want it on all sides of the slab, every single edge must
be measured... give me both options."

Rebuilt both modes genuinely per-FACE (4 faces, never merged):
`_plan_grid_to_each_edge` (MODE_GRID_ONLY) finds each face's own closest grid
independently, no shared center-grid, no "inside the span" classification at
all. `_plan_all_edges_no_grid` (MODE_OVERALL_ONLY) places each axis's
face-to-face span TWICE - once outside the low face, once outside the high
face - so all 4 physical edges get their own adjacent dimension. New
`DimensionPlan.KIND_SLAB_EDGE_TO_GRID` kind. `_plan_individual_column_
dimensions` (Column/Beam/Footing's MODE_GRID_AND_COLUMN) simplified back to
unconditional detail+overall now that the previous mode-split flags have no
other caller. Rewrote the 3 tests that asserted the old behavior, added 3
proving the fix (a wide test element with a decoy CENTER grid resolves each
face to its own near-edge grid, never the center one). 21 tests in
`test_column_grid_planner.py`, 158 total. Live-verified against the real
project's one visible slab in both modes, rolled back.

**Same message, four more asks, all shipped same day:**
1. **Extension renamed**: `BKDesigns.extension`/`BKDesigns.tab`/
   `BKDesigns.panel` -> `BKBIMTools.extension`/`BKBIMTools.tab`/
   `About.panel` - "should've been done a long time ago" (the ribbon tab
   itself already said "BK BIM Tools" since Phase 0; only the folders
   underneath still said "BKDesigns"). Fixed the one functional
   cross-extension reference (`revit-mcp-python.extension`'s hardcoded
   sys.path insert) and deleted every orphaned `*BKDesigns*` cache/dll.
   **Hit a real file lock** ("Device or resource busy") attempting the
   rename while Revit was still running with the extension loaded - asked
   the product owner to close Revit first; rename succeeded immediately once
   closed.
2. **Icons lightened**: all 6 tool icons recolored `#000000` -> `#333333`
   (every opaque pixel's RGB overwritten directly); the About panel's BK
   Designs logo left untouched.
3. **Category-picker icons**: `structural_category_icons.py` draws 4 small
   plain-WPF-shape pictograms (Column/Beam/Footing/Slab) at `#333333` - no
   image files, no network fetch. `category_picker.py` gained an optional
   `icon_factory` param, wired in only for Structural Element Dimensions'
   picker (not Smart Dimension's top-level one), matching the literal "this
   page" scope of the ask.
4. **Toggle Grid 2D/3D utility**: new `ToggleGridExtent.pushbutton`
   (Utilities panel) - flips every grid in the view between 2D
   (`DatumExtentType.ViewSpecific`) and 3D (`DatumExtentType.Model`) per end
   independently, a symmetric toggle. New `domain/models/grid_extent.py` +
   `domain/grids/ports.py` + `app/commands/toggle_grid_extent_command.py`
   (6 new tests) + `revit/adapter/grid_extent_reader.py`/`grid_extent_writer.py`.

**Real bug caught building the grid-toggle icon**: Lucide icons are
stroke-based (`stroke="currentColor"`, `fill="none"`); svglib does not
resolve the CSS keyword `currentColor`, so the icon rendered with zero
opaque pixels until the SVG was pre-processed to substitute a literal
`#000000` before `svg2rlg`. Icons8 icons (used elsewhere) never hit this
since they use explicit `fill` colors, not `currentColor` strokes.

Icon lightening, category-picker icons, and the grid-toggle utility were
**not yet live-verified** against a running Revit session - Revit stayed
closed after the rename to keep the folder move safe. Needs a fresh pyRevit
reload and a first real click-through before calling these done.

### Every-corner slab dimensioning; auto-fit windows; slab icon; ribbon findability fix (2026-07-07, same-day follow-up)

Product owner reopened Revit, tried the batch above, and sent 4 more items.

**Slab "Grid to slab edges" still wasn't right**: "I want it to take every
slab corner, not just the 4 sides." The per-face fix only placed each face's
dimension at ONE perpendicular offset, so a rectangular slab got 4 total
(really "4 sides," each dimension near only one of its two ends) - fixed by
placing each face's dimension at BOTH offsets (mirroring the technique
already used for "all edges" mode), up to 8 per slab. Live-verified: the
real slab went from 2 dimensions to 8 in the same view, rolled back cleanly.

**"I can't find the grid tool" - not a bug.** Confirmed live via
`extensionmgr.get_installed_ui_extensions()` that `ToggleGridExtent` parses
correctly under `Utilities.panel`. A brand-new pushbutton needs an explicit
pyRevit ▸ Reload to appear in the ribbon, even after a full Revit restart.

**Windows now auto-fit their content, still resizable**: switched all 5
option windows from fixed `Width`/`Height` to `SizeToContent="Height"` + a
fixed `Width`. Two real WPF bugs caught via a genuine live layout check
(`Show()` + dispatcher pump + `ActualWidth`/`ActualHeight`, not just visual
inspection): (1) `SizeToContent="WidthAndHeight"` made every wrapping
subtitle measure as one unbroken line (no width to wrap against), blowing
windows out to 800-1000px - fixed by keeping Width fixed. (2) A `Height="*"`
row holding REAL content (CategoryPicker's `ChoicesPanel`) collapses to ~0
height under SizeToContent - fixed by making that one row `Auto`; the other
4 windows' trailing spacer rows were confirmed empty, safe to leave as `*`.

**Slab icon redesigned**: from a plain thin bar (identical to Beam's) to a
wide flat top bar with two small downstand-beam rectangles at each end, per
the product owner's own sketch. Also fixed a stray WPF default focus
rectangle that was drawing oddly across the category picker's focused
button - `FocusVisualStyle="{x:Null}"`.

Added/rewrote tests for the corner-duplication fix (22 tests in
`test_column_grid_planner.py`, 159 total). Live-verified the slab fix and
all 5 windows' actual rendered sizes directly in the running session.

### Toggle Grid 2D/3D: two real bugs found by actually clicking it (2026-07-07, same day)

First, "I'm still not seeing the grid utility" - `Utilities.panel/
bundle.yaml` had an explicit `layout: [CountSelected]` (written when the
panel had just one button), which excludes anything not listed from the
ribbon even though it still parses correctly on disk - the earlier "just
needs a Reload" diagnosis checked the component tree, not the panel's own
layout list. Fixed by adding `ToggleGridExtent`; swept every other panel's
`bundle.yaml` against its actual folder contents - nothing else affected.

Second, once clicked: "0 grid(s) toggled between 2D/3D, 18 failed."
`Grid.SetDatumExtentTypeInView` doesn't exist on this Revit API version -
confirmed via live reflection that the getter really is
`GetDatumExtentTypeInView` but the setter is just `SetDatumExtentType` (no
"InView" suffix). Fixed the one call site. Live-verified against all 18 real
grids in a rolled-back transaction: toggled, re-read within the same
transaction to confirm the flip actually applied, toggled again and
confirmed every grid returned to its original state.

### "All edges of the slab" traces the REAL outline, not the bounding box (2026-07-07, same day)

Product owner sent a screenshot of a real notched/stepped slab footprint (a
rectangle with a rectangular notch cut from the bottom-middle) with the
whole perimeter traced in red: "I want dimensions to follow every slab
face." Every earlier version of this mode approximated the slab as its
axis-aligned bounding box (4 faces) - fine for a plain rectangle, silently
wrong for anything with a step or notch.

Shipped `OutlineEdge` (domain data: one real boundary segment's own axis,
coordinate, span, and outward sign) + `RevitReferenceProvider.
outline_edges_for()` (reads EVERY side face of a solid, not just the two
extremes per axis, using `PlanarFace.GetBoundingBox()`/`Evaluate()` for each
face's own real extent) + `slab_outline_planner.plan_slab_outline_dimensions`
(pure - for each edge, finds its two adjacent perpendicular edges by
matching shared corners exactly, dimensions the edge's own length referenced
to those neighbors' faces - the same "reference a face" technique used
everywhere else in this codebase, just applied per real corner) +
`auto_slab_outline_dimension_command` + a separate `_run_slab_outline`
pipeline in `structural_dimension_flow.py` (used only for `MODE_OVERALL_ONLY`;
Column/Beam/Footing and Slab's "Grid to slab edges" mode are unchanged).
Also fixed a minor existing bug in the same change: "All edges" mode
required grids to be present even though it never references them.

**Live-verified against the real notched slab** (rolled back): read its
actual geometry first and confirmed exactly 8 side faces, matching the
screenshot's shape - used these REAL coordinates as the unit test fixture,
not a synthetic guess. Ran the corrected pipeline: 8 dimensions created (one
per real edge, not the old 2), 0 errors. Inspected every created dimension's
actual value - 21700/11200/11200/4375/4375/12950/600/600mm - all
architecturally sensible. Dimension count returned to its exact
pre-existing value (0) after rollback. 173 unit tests total.

## Auto Mark (2026-07-08, Module 02, first Documentation "schedules" tool)

Product owner: "if i click Auto Mark, it will give me a bunch of
categories... display the family types and family names in use, dont
itemize every instance... sort it from largest to smallest and let me
select a prefix for the category... this tool will help me arrange my
schedules, which is the tool youll build next." First tool of the
Documentation panel's third group (legends/schedules), following the two
lines added the same day to separate dimension tools / legends / schedules.

Assigns the instance Mark parameter (`BuiltInParameter.ALL_MODEL_MARK`) -
confirmed via product-owner clarification that this needed to be the
per-instance Mark (unique value per placed element, e.g. D1/D2/D3), not
Type Mark (one value shared by every instance of a type) - the review
window's "group by family+type, don't itemize instances" display is purely
a UI simplification; every placed instance still gets its own value on Run.

New vertical slice, doc-wide (no view scoping, unlike every dimensioning
tool):
- `domain/marking/mark_planner.py` + `domain/models/mark_{instance,
  type_group,family_group}.py` - pure sort/numbering logic, zero Revit
  imports (ADR-0001). Types sorted largest-to-smallest per family by
  (dimension_a, dimension_b); instances within a type ordered by level then
  x/y then a stable id; numbering restarts at 1 per family/prefix. A family
  left blank is skipped. `tests/unit/test_mark_planner.py` (9 cases) caught
  a real bug during development - a missing-dimension sort key sorted
  first instead of last until a test caught it.
- `revit/adapter/mark_type_reader.py` - doc-wide FilteredElementCollector
  per category (Doors/Windows/Columns/Beams/Footings; Slabs deferred - no
  clean length/width for an irregular sketched shape), grouped by Symbol.
  Reuses the door/window Width/Height BuiltInParameter fallback lists
  already in `boq/extractors.py`, and extends the column B/H display-name
  fallback pairs already in `automation/columns.py` (adding "bf"/"d" for
  I-shaped beams) - Beams and Footings had no prior art for this, so those
  fallback lists are new.
- `revit/adapter/mark_writer.py` / `mark_flow.py` - plain `param.Set()`
  writer (no `IFailuresPreprocessor` needed, just IsReadOnly + try/except),
  Transaction owned by the flow per SAD Sec 4.4. First real consumer of
  `core/settings.py` (previously wired but unused) - remembers each
  family's prefix at the USER layer (`%APPDATA%\pyRevit\
  bkbim_auto_mark_prefixes.json`), deliberately not scoped to the current
  document since a prefix habit ("Single-Flush" -> "D") carries across
  projects.
- `app/commands/auto_mark_command.py` - aggregates marked/failed counts,
  tolerates individual write failures without aborting the run.
  `tests/unit/test_auto_mark_command.py` (5 cases) against a fake writer.
- `ui/views/auto_mark_options.py` + `.xaml` - one family group per row
  (built programmatically, same idiom as `category_picker.py`'s choice
  buttons - no data-bound repeating template exists elsewhere in this
  codebase yet), each with its own prefix TextBox and a live mark-range
  preview that recomputes as you type, scoped to that family only.
  Deliberately takes `dimension_a_label`/`dimension_b_label` as plain
  strings from the caller rather than importing `revit.adapter` directly,
  matching `structural_dimension_options.py`'s `type_name_fn`-callback
  convention for keeping the UI layer decoupled from Revit adapter
  specifics.

212 unit tests total (207 pre-existing + 9 mark_planner + 5 auto_mark_command,
run with plain CPython, no Revit required).

**Corrected same day, immediately after the above landed** (before any real
use): product owner: "for the tagging, if the family name and type is the
same, they should have the same mark." The original design gave every
PLACED INSTANCE its own unique number even within one type (D1, D2, D3 for
three identical doors); this reverses that - one mark per family+type,
shared by every instance of it (D1 for every instance of the largest type,
D2 for every instance of the next, etc.). Simplified the domain model at
the same time now that per-instance position no longer matters for
numbering: deleted `MarkInstance` entirely and `_instance_sort_key` from
`mark_planner.py` (dead code now that location/level don't drive anything);
`MarkTypeGroup.instance_refs` is now a plain list of ElementIds, not
wrapper objects; `mark_type_reader.py` no longer resolves each instance's
level/location at all (removed `_level_elevation`/`_location_xy`, which
only ever existed to feed the now-gone per-instance sort). Review window's
per-type preview now shows one mark, not a range. Tests rewritten to match
(`test_mark_planner.py`, `test_auto_mark_command.py`) - 211 unit tests
total (net -1: two location/ordering tests for behavior that no longer
exists were removed, replaced by ones proving identical-type instances
share a mark). **Live-verified against the real project** (rolled back):
marked a 25-instance door family (24 of one type, 1 of another) - all 24
came back with the identical mark, the 1 got a different one, confirmed by
reading `ALL_MODEL_MARK` back off the real elements before rollback.

## Auto Tag (2026-07-09, Module 03, second Documentation "schedules" tool)

Product owner: "add a section after the automark, to autotag the marked
items in selected views. give me options to select the tag i want, and the
views i want to tag stuff." Confirmed scope before building (product owner
picked the recommended default at each fork): one category per run (mirrors
Auto Mark/Structural Dimensions' own category-picker flow), skip elements
that already have a tag in a view (safe to re-run), and every plan/section/
elevation view selectable (not filtered down to "only views containing that
category").

Unlike Auto Mark (doc-wide, no view scoping - a Mark is one value per type
regardless of view), Auto Tag is view-scoped like the four dimensioning
tools, so it reuses their existing infrastructure directly instead of
building new UI: `view_selection_prompt.pick_target_views` for the "just
this view / pick multiple views" prompt, and `multi_view_batch.
run_across_views`/`alert_batch_results` for the per-view-Transaction /
combined-alert shape - zero new view-picking code needed.

New vertical slice:
- `domain/tagging/ports.py` - `IAlreadyTaggedChecker`/`ITagWriter`, same
  port-per-Revit-concern pattern as `domain/dimensioning/ports.py`. No
  dedicated planner module - unlike Auto Mark's family/type grouping, the
  actual logic here (tag what's untagged, skip what isn't) is a single
  pass, so `app/commands/auto_tag_command.py` does the loop directly,
  same "thin command, no domain module" shape as `toggle_grid_extent_command.py`.
- `revit/adapter/tag_type_reader.py` - reuses Auto Mark's own category set
  (`mark_type_reader.CATEGORIES`/`CATEGORY_BUILTIN_CATEGORIES`) so "Doors"
  means the same thing in both tools. Columns is the one category with two
  distinct host categories (architectural `OST_Columns`, structural
  `OST_StructuralColumns`), each with its own tag category (`OST_ColumnTags`/
  `OST_StructuralColumnTags`) - a Column Tag can't tag a structural column
  and vice versa. `list_tag_types` lists both tag categories' loaded types
  together (prefixed with the tag category name in the picker when more
  than one is present); `list_taggable_elements` only returns elements
  whose own host category matches the CHOSEN tag type's category, so a
  mismatched element is simply never handed to the writer rather than
  erroring.
- `revit/adapter/tag_writer.py` - `IndependentTag.Create(doc, typeId,
  viewId, reference, addLeader=False, TagOrientation.Horizontal, point)`.
  `point` resolution falls back through `Location.Point` ->
  `Location.Curve` midpoint (beams are curve-based, not point-based, unlike
  every other Auto Mark category) -> bounding-box center, so no category
  silently fails to resolve a placement point.
- `revit/adapter/already_tagged_checker.py` - collects every
  `IndependentTag` in the view via `GetTaggedLocalElementIds()` (Revit
  2022+ API; handles multi-reference tags) into one set, cached for the
  whole run - mirrors `existing_dimension_checker.py`'s "skip if already
  placed" convention for dimensions.
- `revit/adapter/tag_flow.py` - category picker -> `pick_target_views` ->
  tag-type options window -> `run_across_views`, one Transaction per view.
- `ui/views/auto_tag_options.py` + `.xaml` - a single tag-type ComboBox;
  nothing else to configure per run since view selection already happened.
- `BKBIMTools.tab/Documentation.panel/AutoTag.pushbutton` - added directly
  after `AutoMark` in `Documentation.panel/bundle.yaml`'s `layout:` list.
  Icon: Lucide "tags" (plural, two overlapping tag shapes) - deliberately
  different glyph from Auto Mark's single-tag icon so the two are visually
  distinct at a glance; rendered via the established svglib+reportlab
  recipe (`currentColor` replaced with a literal color first, alpha
  derived from a white-vs-black render pair), recolored `#333333`,
  confirmed every opaque pixel matches exactly.

`tests/unit/test_auto_tag_command.py` (6 cases: no elements, tags every
untagged element, skips already-tagged, a refused write is counted but
doesn't stop the run, a checker error is treated as not-tagged rather than
aborting, everything-already-tagged fails with a clear message) - all
against fakes, no Revit involved. 217 unit tests total (211 pre-existing +
6 auto_tag_command).

**Not yet live-verified** - no Revit session was open when this was built.
The riskiest assumptions (exact `BuiltInCategory` names for the four tag
categories, `IndependentTag.Create`'s modern signature, whether
`GetTaggedLocalElementIds()` is available) are all defensively coded
(`getattr(..., None)` fallbacks, try/except around every Revit call) but
have not been exercised against a real model yet - next step is a rolled-
back live test the next time a project is open, per this project's
standard verification discipline.

## Auto Mark & Tag combined button + ribbon regroup (2026-07-09, same day)

Product owner: "now i want an auto mark & tag pushbutton. this combines
the features of automark and autotag in one button. i still want to
retain the seperate buttons though however, i want you to arrange it
nicely. Automark and tag pushbutton first with a normal size icon and all,
then auto mark and auto tag become smaller push buttons stacked ontop of
eachother and to the right of the combined pushbutton. kinda like a
triangle arrangement."

`revit/adapter/mark_and_tag_flow.py` - pure sequencing, zero new business
logic: calls `mark_flow.run_auto_mark_flow` then, unless the user cancelled
or nothing existed for the category, `tag_flow.run_auto_tag_flow` for the
same category. Both flows stay exactly as they were - this module owns
none of their logic, just the order.

**Ribbon arrangement - discovered pyRevit's `.stack` bundle type** (not
previously used in this suite): a folder suffixed `.stack` (like
`.pushbutton`/`.panel`/`.pulldown`) is a container with no UI of its own -
its children render as small buttons stacked vertically within the parent
panel (confirmed by reading pyRevit's own source,
`pyrevitlib/pyrevit/extensions/components.py`'s `GenericStack`/`Panel.
contains()`: "stacks itself does not have any ui and its subitems are
displayed within the ui of the parent panel"). Moved the existing
`AutoMark.pushbutton`/`AutoTag.pushbutton` folders (via `git mv` for the
tracked one) into a new `MarkAndTagStack.stack`, with its own `bundle.yaml`
`layout: [AutoMark, AutoTag]` so Mark stacks above Tag - Documentation.
panel's own `layout:` now lists `AutoMarkAndTag` (normal-size, first) then
`MarkAndTagStack` (the small stacked pair, immediately to its right) -
renders as the requested "triangle": one big button, two small ones
stacked beside it.

Icon: Lucide "tag-plus" (a tag with a "+") for the combined button -
visually distinct from Auto Mark's "tag" and Auto Tag's "tags" icons while
still reading as related. Rendered via the same svglib+reportlab recipe
already used for Auto Tag's icon.

**Live-verified** (real project, Revit was open this time): ran the
underlying Auto Tag adapter code directly against real elements in rolled-
back transactions - confirmed every `BuiltInCategory` tag-category name
guessed earlier was correct (`OST_DoorTags`, `OST_WindowTags`,
`OST_ColumnTags`/`OST_StructuralColumnTags` - both present and listed
separately for Columns, `OST_StructuralFramingTags`,
`OST_StructuralFoundationTags`), `IndependentTag.Create`'s signature is
correct (20 real doors tagged), the `Location.Curve` midpoint fallback
works for curve-based elements (19 real beams tagged - beams aren't
point-based like doors/windows/columns), and `GetTaggedLocalElementIds()`
correctly detects re-tagging (a second run against the same 20 doors, same
transaction, correctly reported "everything already tagged" instead of
creating duplicates). Every transaction rolled back cleanly, confirmed by
re-counting `IndependentTag`s before/after. This retroactively confirms
the previous entry's "not yet live-verified" caveat for Auto Tag itself -
no changes were needed, every earlier assumption held. The combined flow's
own UI orchestration (`mark_and_tag_flow.py`) is thin sequencing on top of
two independently-proven flows and shows modal dialogs, so it isn't
callable headlessly through the MCP test channel - not yet click-tested by
an actual user run, unlike the adapter code underneath it.
