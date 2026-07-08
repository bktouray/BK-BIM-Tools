# Phase 0 — Foundation: Task Plan

- **Status:** Draft v0.1 (2026-07-05)
- **Goal (per [ROADMAP](../ROADMAP.md)):** stand up `bkbim.core`, the consolidated
  extension skeleton, and a walking-skeleton tool that proves the full
  entrypoint→app→domain→revit→ui stack — **before** any Auto Dimension logic is
  ported. No dimensioning logic moves in this phase.
- **Exit criteria:** an empty shell tool runs end-to-end through all five layers;
  ADRs are in place (done); MCP bridge calls one real `app` command.

Walking-skeleton choice (locked): **"Count Selected Elements"** — trivial by design.
Its only job is to prove wiring, not to be useful. Complexity is deferred to Phase 1.

---

## Task sequence

### 0.1 — Extension skeleton & consolidation (ADR-0003)
1. Create `lib/bkbim/` package skeleton under `BKDesigns.extension/` with empty
   `core/`, `domain/`, `app/`, `revit/`, `ui/` packages (`__init__.py` only).
2. Rename ribbon tab display in `BKDesigns.extension/BKDesigns.tab/bundle.yaml` (or
   equivalent) to **"BK BIM Tools"**; confirm folder name stays `BKDesigns.tab`
   (folder names don't have to match display titles in pyRevit).
3. Add panel folders per PRD §4: `Documentation.panel`, `Modeling.panel`,
   `QAQC.panel`, `AI.panel`, `Utilities.panel`, `Settings.panel` (empty except
   existing `About.urlbutton`, `WallLegend.pushbutton` relocated if needed).
4. Leave `AutoDims.extension` in place, untouched, until Phase 1 parity is reached —
   do not delete or disable the working tool prematurely.

### 0.2 — `bkbim.core` (platform layer)
5. `core/result.py` — `Result[T]` (success/failure, message, diagnostics).
6. `core/errors.py` — `BKBimError` base + a couple of concrete subtypes.
7. `core/logging.py` — structured logger, sinks: pyRevit output first; file sink
   stubbed but wired.
8. `core/config.py` — immutable config: MCP endpoint (`127.0.0.1:48884` per
   `CLAUDE.md`), engine selection, paths.
9. `core/settings.py` — layered settings manager (defaults→office→user→project→
   session), JSON-backed, minimal schema (just enough for the skeleton tool).
10. `core/di.py` — minimal service locator wiring settings/logger/config.
11. Unit tests for 5–10 above (pure Python, no Revit — first proof that the "pure
    core" rule is real).

### 0.3 — Domain contracts (no logic yet, just seams)
12. `domain/models/` — minimal `SelectionSummary` model (id list + count) for the
    walking skeleton only. Real domain models (Element, Reference, DimensionPlan,
    Standard) are **Phase 1** work, not Phase 0.
13. Define `IElementReader` interface in `domain/` (or a `ports/` sub-module) that the
    revit adapter will implement — first concrete instance of the dependency-inversion
    pattern from the SAD.

### 0.4 — Revit adapter (thin, for the skeleton only)
14. `revit/adapter/model_reader.py` — implements `IElementReader.count_selected()`
    against `uidoc.Selection`. This is intentionally trivial.
15. `revit/version/revit2026.py` — created empty/stubbed now; real quirk isolation
    starts in Phase 1 when actual API differences are ported in.

### 0.5 — Application layer
16. `app/commands/count_selected_command.py` — the one walking-skeleton use-case:
    calls `IElementReader` (via DI) → returns `Result[SelectionSummary]`. This is the
    template every future command copies.

### 0.6 — UI (Tier 1, per UX spec §3.1)
17. Simplest possible: a pyRevit `forms` alert showing the count — **not** the full
    `ModuleWindow` shell yet. The shell (UX_SPEC §3) is validated in Phase 1 against a
    real module (Auto Dimension settings), where there's enough content to justify it.
18. Entry point: `Documentation.panel/CountSelected.pushbutton/script.py` — ~10 lines,
    imports and calls the Phase-0 command only.

### 0.7 — MCP integration proof
19. Add one MCP tool in `revit-mcp-python.extension` that invokes
    `count_selected_command` through `bkbim.app` (not duplicating the logic) —
    proves "ribbon and AI call the same command" end to end, cheaply.

### 0.8 — Wrap-up
20. Update `docs/ROADMAP.md` status table (Phase 0 → done) and note actual vs.
    planned deviations.
21. Write `docs/CHANGELOG.md` entry: "0.1.0 — Phase 0 foundation walking skeleton."

---

## Explicit non-goals for Phase 0

- No porting of `Auto Dims SC v5` logic (that's all of Phase 1).
- No Standards/Presets engine content (stubs only where a seam is needed).
- No `ModuleWindow` shell implementation (Tier 1 only).
- No licensing machinery beyond the `ILicenseService` interface existing on paper —
  not even a no-op implementation is required yet.
- No CI enforcement of the "no Revit import below adapter" rule yet — manual review
  is sufficient at this scale; automate once a second contributor is on the codebase.

## Definition of done

Running the `CountSelected` pushbutton in Revit 2026 shows an alert with the correct
count, sourced through `core→app→domain-contract→revit-adapter`, logged via
`core.logging`, and the same result is obtainable by asking the MCP-connected AI to
"count the selected elements." That single thread proves the architecture is real,
not aspirational — everything in Phase 1 builds on top of it with confidence.
