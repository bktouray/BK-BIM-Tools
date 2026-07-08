# BK BIM Tools — Software Architecture Document (SAD)

- **Product:** BK BIM Tools — *Professional Revit Automation & AI Productivity Suite*
- **Vendor:** BK Designs
- **Status:** Draft v0.1 (2026-07-05)
- **Primary target:** Autodesk Revit 2026 (build 2026.4); forward-compatible by design.

Related decisions: [ADR-0001 Engine](../ADR/0001-python-engine-strategy.md) ·
[ADR-0002 Vertical slice](../ADR/0002-vertical-slice-first.md) ·
[ADR-0003 Consolidation](../ADR/0003-extension-consolidation.md).

---

## 1. Architectural goals & drivers

| Driver | Architectural response |
|---|---|
| 5–10 yr commercial lifespan | Clean layering; competitive IP isolated in pure, portable core. |
| Dozens of future modules | Additive module model; framework extracted, not speculated (ADR-0002). |
| Premium WPF UX | IronPython 2.7 (confirmed engine, ADR-0001) + XAML MVVM, shared window shell. |
| Deterministic + AI-driven | Deterministic core; AI parameterizes existing commands, never generates Revit code. |
| Future C# migration | Domain/app pure Python; XAML reused; adapter is the only rewrite. |
| Multi-standard (BS/ISO/AIA) | Data-driven Standards engine; standards are inputs, never embedded. |
| Multi-version Revit | API differences quarantined in `revit/version/`. |

## 2. Layered architecture

Dependencies point **inward only**. The Revit adapter *implements* interfaces the
domain *declares* (dependency inversion) — this is what makes the core engine-agnostic
and C#-portable.

```
Entry points   pushbutton script.py │ MCP tool │ hook        (thin shims, ~15 lines)
     │
Application    bkbim.app     Commands / use-cases, Transaction boundary, progress,
     │                        Result objects.  Ribbon AND AI invoke THIS layer.
Domain         bkbim.domain  PURE. Geometry, reference model, dimension strategy,
     │                        annotation strategy, standards. Emits PLANS, not effects.
Revit adapter  bkbim.revit   ONLY layer importing Autodesk.Revit. Model→domain read,
     │                        plan→element apply, version isolation.
Platform       bkbim.core    Settings, presets, logging, config, errors, result, units,
                              DI, licensing, telemetry. Depends on nothing.
UI             bkbim.ui      WPF views + viewmodels, shared shell, theming, icons.
```

**Dependency graph (no cycles):**
```
ui ──► app ──► domain ◄── revit (implements domain interfaces)
        │         ▲
        └────► core ◄──── (all depend on core; core depends on nothing)
entrypoints ─► app ;  mcp tools ─► app ;  hooks ─► app
```

## 3. Package structure (under `BKDesigns.extension/lib/bkbim/`)

```
bkbim/
├─ core/        settings presets logging config errors result units di licensing telemetry
├─ domain/
│  ├─ models/       element reference dimension_plan standard
│  ├─ geometry/     pure math: axes, bbox, projection, nearest, unit-space
│  ├─ references/   IReferenceProvider interface + selection strategy
│  ├─ dimensioning/ side-picking, snap/overall/chain planner, collision zones
│  ├─ annotation/   tag/keynote/legend planners (Module 02+)
│  └─ standards/    BS / ISO / AIA / custom profiles (data-driven)
├─ app/         commands/  auto_dimension_command.py  ... (one per use-case)
├─ revit/
│  ├─ adapter/      model_reader reference_provider dim_writer transaction failures
│  └─ version/      revit2026.py (+ future) — isolates API differences
└─ ui/          shell/ views/ viewmodels/ controls/ themes/ icons/
```

## 4. Layer responsibilities

### 4.1 Core (platform, cross-cutting)
- **Settings** — single-writer manager; layered resolution
  `defaults → office → user → project → session`. JSON-backed; interface allows
  future cloud sync with no call-site change. Modules never persist settings directly.
- **Presets** — serialized bundle of every configurable option for a module/suite;
  references a Standard; import/export = file round-trip.
- **Logging** — structured logger with sinks (pyRevit output, rotating file, future
  telemetry). Retires the monolith's `DEBUG` global and scattered `print_md`.
- **Config** — immutable, environment-aware (paths, feature flags, engine selection,
  MCP endpoint `127.0.0.1:48884`). Developer/deployment-facing; distinct from Settings.
- **Errors** — `BKBimError` hierarchy; domain raises, app wraps in `Result`.
- **Result[T]** — success/failure + user message + diagnostics. Crosses every boundary.
- **DI** — lightweight service locator; modules *ask* for settings/logger/license.
- **Licensing** — `ILicenseService` interface; Phase-1 no-op/local impl (see ADR-0001, ADR roadmap).

### 4.2 Domain (pure — the competitive IP)
- **Geometry engine** — math on domain types (points/vectors/bbox/axes); no Revit XYZ.
  Absorbs `mm_to_ft`, `_bbox`, nearest-element, side geometry from the monolith.
- **Reference model** — abstract `ReferenceHandle`; domain reasons about handles, not
  Revit `Reference` objects.
- **Dimension engine** — consumes elements/refs/grids → emits a `DimensionPlan`
  (which refs, which line, which label). No `NewDimension`. Absorbs `dim_along_axis`,
  snap/overall/chain decision tree, and the collision-zone reservation system.
- **Annotation engine** — generalization of the dimension pattern for tags/keynotes/
  legends (Module 02+).
- **Standards engine** — strategy + registry; `Standard` = named profile of offsets,
  tolerances, rounding, families, text rules. Ships BS/ISO/AIA; users add custom
  profiles without touching core (Open/Closed).

### 4.3 Revit adapter (the only Revit-coupled layer, the C# rewrite target)
- **Model reader** — Revit elements/grids → domain models. Absorbs
  `collect_grids_from_selection`, `collect_elements_from_selection`.
- **Reference provider** — implements `IReferenceProvider`; owns the hard-won
  reference logic (`get_faces`, `_symbol_to_instance_ref`, `get_grid_ref`), including
  the symbol-geometry → instance-ref trick.
- **Dimension writer** — executes a `DimensionPlan` inside one transaction; absorbs
  `make_dim`/`NewDimension`, `_displace_small_texts`.
- **Failures** — reusable, configurable `IFailuresPreprocessor` policy (promoted from
  the hardcoded `DimFailureSwallower`).
- **Version** — `revit2026.py` isolates quirks (e.g. `ElementId.Value` vs
  `.IntegerValue`, `Element.Name.GetValue`).

### 4.4 Application (use-cases)
One **Command** per user action (e.g. `AutoDimensionCommand`). Owns orchestration,
the Transaction boundary, progress reporting, cancellation, and returns a `Result`.
**Both the ribbon and the AI/MCP call this layer** — single source of truth for
"what the tool does."

### 4.5 UI
One **`ModuleWindow` shell** (Header → Left nav → Workspace: preview+options+presets →
Footer: progress+ETA+status+Run/Cancel/Help), consumed via MVVM. XAML-first because
XAML ports to C# WPF ~1:1. Tiered investment: pyRevit `forms` for simple tools, full
custom WPF only for flagships.

## 5. Cross-cutting strategies

- **Error handling:** domain raises typed → app wraps `Result` + owns rollback →
  adapter runs failure policy → entry point renders `Result` (never a raw stack trace).
- **Determinism & AI:** core is deterministic; NL request → intent → same `app`
  command with structured params. AI never runs generated Revit code.
- **Performance:** cache geometry per run; batch reads; minimise transactions (plan
  first, apply once); progress + cancellation are first-class in every command.
- **Versioning:** SemVer for suite and per-module; API diffs quarantined in
  `revit/version/`.

## 6. Testing

- **Unit** — pure `domain`/`core`, fast, off-Revit (the payoff of keeping them pure).
- **Integration** — against a fixture `.rvt` via the MCP bridge (pattern already
  present in `revit-mcp-python.extension/tests`).
- Every engine ships edge cases: grid-on-edge, grid-outside, in-place families,
  curtain walls, empty selection (several already encoded in v5 scenarios).

## 7. C# migration path

Domain + app port first (pure logic → C#, near-mechanical) · XAML reused · `revit/`
adapter rewritten against identical interfaces · core reimplemented behind same
contracts. Migrate module-by-module; a C# Auto Dimension can ship alongside Python
modules because they only ever communicate through `app` commands.
