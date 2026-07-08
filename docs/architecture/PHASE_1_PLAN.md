# Phase 1 — Vertical Slice: Auto Dimension

- **Status:** Draft v0.1 (2026-07-05)
- **Depends on:** Phase 0 (done, smoke-tested), [ADR-0001](../ADR/0001-python-engine-strategy.md)
  (corrected: IronPython 2.7.12), [ADR-0002](../ADR/0002-vertical-slice-first.md)
  (corrected: v5 is unverified third-party code).

## 0. What changed from the original framing

The original Phase-1 plan (folded into `docs/ROADMAP.md`) said "port `Auto Dims SC
v5` into domain/app/revit/ui" with "feature parity with v5" as the acceptance bar.
That framing assumed v5 was this team's validated prior work. It is not: it's a
1,182-line script found on GitHub, written by someone else, and the product owner
says **it doesn't work well**. Porting it faithfully would mean porting its bugs into
a nicer folder structure. That is not the goal.

**Revised goal:** build a correct, standards-driven Auto Dimension module from first
principles, engineered and verified against real Revit geometry - using v5 only as
(a) a map of the problem space (what cases a dimensioning tool must handle) and
(b) a source of specific, independently-verifiable Revit API techniques, salvaged
individually rather than wholesale.

## 1. What to salvage from v5 vs. discard

Read closely (see `AutoDims.extension/.../script.py`), here's the split:

### Worth salvaging (technique is sound, verify then reuse)
- **Symbol-geometry -> instance-reference conversion** (`_symbol_to_instance_ref`):
  `FamilyInstance.get_Geometry()` gives correct world coordinates but its face
  references don't work for `NewDimension`; the fix is to get references from
  `GetSymbolGeometry()` (stable, type-level) and rewrite the stable representation's
  element-id token from the type id to the instance id. This is a genuine, non-obvious
  Revit API technique worth keeping - but it must be independently re-verified in
  Phase 1 with a dedicated test (not assumed correct because v5 does it).
  Genuinely worth re-verifying: whether the "id64" ordinal in the stable string is
  always the first colon-delimited token across Revit versions, or whether the format
  can vary (e.g. for nested families, linked models).
- **Bubble-end detection via `IsBubbleVisibleInView`** for grid dimension chain
  placement direction - a reasonable, low-risk technique.
- **`IFailuresPreprocessor` for suppressing "not parallel" dimension-creation
  warnings** - the *pattern* is right (Revit needs a failure handler for dimension
  creation), but v5's specific policy (blanket-delete any element referenced by an
  Error-severity failure) is dangerous: it can silently delete elements it merely
  tried to reference, not just the malformed dimension. Phase 1 must scope deletion
  to elements the command itself just created, never pre-existing model elements.

### Worth treating as a known bug list, not a spec
- **Bounding-box-center heuristics** for side-picking (`_pick_side`) and nearest-grid
  matching assume simple rectangular, axis-aligned layouts. Curved walls, angled
  walls, and non-orthogonal grids are not handled - this is a likely source of the
  "doesn't work well" feedback and needs an explicit design decision (see open
  question below) rather than silent inheritance.
- **Fixed mm offsets regardless of view scale**, only partially compensated
  (`_displace_small_texts` adjusts text position, not the dimension line offset
  itself). A correct implementation ties offsets to the active Standard profile and,
  ideally, view scale.
- **Zone-based collision avoidance** (`_adjust_perp_for_collisions`) is a simple
  greedy heuristic with a fixed pass limit (3) and fixed shift (300mm) - can still
  produce overlapping dimensions in dense layouts. Needs real test cases, not
  inherited constants.
- **No unit tests of any kind.** Every one of the above heuristics has silently
  wrong behavior somewhere, undiscoverable from reading the code alone.

## 2. Correctness bar (replaces "feature parity with v5")

A dimension placement is correct when, for a given Standard profile:
1. Every reference in the dimension chain resolves to the intended physical face/
   centerline/grid (verified against the model, not just "a dimension was created").
2. Offset distances, chain ordering, and side placement match the active Standard's
   rules (BS/ISO/AIA/custom), not a hardcoded constant.
3. No dimension silently fails, and no failure handler deletes a pre-existing model
   element.
4. The result is reproducible - same inputs, same output - so it can be captured as a
   regression test once observed correct.

This bar is checked via the testing strategy in §5, not by eyeballing agreement with
v5's output.

## 3. Domain design (pure, Python-2.7-compatible per ADR-0001)

```
domain/geometry/        axis math, bbox, projection - ported from v5's math helpers
                         (mm_to_ft, bbox extraction) since these are simple and
                         version-independent; re-tested, not re-derived.
domain/models/
  element_info.py        replaces v5's ad-hoc dict (wall/column bbox + category)
  grid_info.py            replaces v5's grid dict (orientation, bubble end, coord)
  dimension_plan.py       NEW: {refs: [ReferenceHandle], line, label, kind} - the
                           planner's output; adapter is the only consumer that turns
                           this into doc.Create.NewDimension calls.
domain/references/
  ports.py                IReferenceProvider interface: faces_for(element, axis),
                           grid_reference(grid) - abstracts what v5's get_faces /
                           get_grid_ref do, without Revit types leaking into domain.
domain/dimensioning/
  side_picker.py           port of _pick_side, re-specified: input is grid positions
                           + element bbox, output is a side; unit-testable in
                           isolation with synthetic grid/element fixtures.
  planner.py               port of dim_along_axis's decision tree (on-edge / inside
                           E-G-E / outside chain), returning DimensionPlan objects
                           instead of calling NewDimension directly.
  collision.py             port of the zone-reservation system, parameterized (no
                           hardcoded 300mm/3-pass constants - these become Standard
                           profile fields).
domain/standards/
  standard.py              NEW: offsets, tolerances, collision-shift step, rounding,
                           per-profile - replaces v5's module-level constants
                           (OFFSET_1_MM, ZERO_TOL_MM, etc).
```

## 4. Revit adapter design

```
revit/adapter/
  model_reader.py (extend)  reads walls/columns/grids into ElementInfo/GridInfo,
                             replacing collect_elements_from_selection /
                             collect_grids_from_selection.
  reference_provider.py     implements IReferenceProvider; owns get_faces-equivalent
                             logic including the symbol->instance-ref conversion.
  dimension_writer.py        turns a DimensionPlan into doc.Create.NewDimension calls
                             inside one transaction; owns _displace_small_texts
                             equivalent.
  failure_policy.py          configurable IFailuresPreprocessor: scoped to elements
                             created in this transaction, never blanket-deletes.
```

## 5. Testing strategy (this is the load-bearing part of Phase 1)

- **Unit tests (pure, no Revit)** for everything in `domain/`: side-picking,
  planner decision tree, collision zones, standards profile resolution - using
  synthetic `ElementInfo`/`GridInfo` fixtures covering the scenarios v5's own
  docstring names (grid inside element, grid on edge, grid outside element) *plus*
  cases v5 doesn't handle (curved/angled walls, non-orthogonal grids, dense
  layouts triggering multiple collision passes).
- **Integration tests** via the MCP bridge (pattern already in
  `revit-mcp-python.extension/tests/integration`) against a small fixture `.rvt`
  with known-good expected dimension placements, so "correct" is captured once and
  regression-checked forever after - not re-eyeballed each time.
- **Manual verification pass in Revit** (like the Phase 0 smoke test) before calling
  any milestone done: run the real command against the product owner's actual
  project files, not just the fixture, since that's where "doesn't work well" was
  originally observed.

## 6. Product owner input (2026-07-05)

Asked directly: v5 is broken across **all** of references, placement, crashes, and
complex-layout handling ("all of them tbh, you might wanna start from scratch"). No
single reference project file is available; Phase 1 correctness is judged against
general professional-dimensioning judgment, verified incrementally in the product
owner's live Revit session (already available via `execute_revit_code` - the same
mechanism that smoke-tested Phase 0) rather than a single fixture file.

**Consequence:** v5 is downgraded further than §1 originally allowed. Nothing is
"salvaged" as code. The symbol-geometry -> instance-reference technique and the
`IFailuresPreprocessor` pattern in §1 are kept only as *documented Revit API facts
worth knowing about* (they describe real API behavior, not v5's judgment calls) -
Phase 1 re-derives and re-tests them independently rather than adapting v5's
implementation. Every heuristic that involves a judgment call (side-picking,
offsets, collision handling) is designed fresh in Phase 1, and - critically - the
big early design decisions (how side-picking should work, how offsets should scale,
what "correct" looks like for a given layout) should be reviewed with the product
owner before being coded as final logic, not invented in isolation. Inventing
unvalidated heuristics alone is exactly how v5 ended up "not working well."

## 7. Staged breakdown (sequenced, each stage independently testable)

1. **Domain models + geometry** - `ElementInfo`, `GridInfo`, geometry helpers. Unit
   tests only, no Revit.
2. **Standards profile** - `Standard` dataclass-equivalent + BS default profile
   (offsets/tolerances only; full BS/ISO/AIA catalog is Phase 3).
3. **Side-picker + planner (pure logic)** - the decision tree, fully unit-tested
   against synthetic fixtures before touching Revit at all.
4. **Reference provider (Revit adapter)** - the hardest part; dedicated tests for
   the symbol->instance-ref conversion against real family instances.
5. **Dimension writer + failure policy (Revit adapter)** - turns plans into real
   dimensions; scoped failure handling.
6. **App command + UI (Tier 2 per UX_SPEC)** - wires it together behind the
   `ModuleWindow` shell for the first time, with a real options panel (existing
   dimension mode, standard selector).
7. **Manual verification against the product owner's real project files.**

Each stage ends with passing tests before the next starts - matches the Phase-0
discipline (24/24 tests, then a live smoke test) that just caught two real bugs
before they reached production.
