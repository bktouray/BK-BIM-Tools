# ADR-0004 — MEP Platform: Vertical Slice = Sanitary Drainage First

- **Status:** Accepted (2026-07-09); **paused 2026-07-10** in favor of Water Supply
- **Deciders:** Product owner (BK Designs) + Lead Architect
- **Supersedes nothing; extends** [ADR-0002](0002-vertical-slice-first.md) into the MEP module.

## Update 2026-07-10 — active slice switched to Water Supply

By the time this ADR's Sanitary Drainage slice reached a real pushbutton
(room pick, wall confirm, live-tested end-to-end against real fixtures),
the product owner asked to shelve Sanitary Drainage/Sewage for now and
switch focus to **Water Supply (Cold Water first, Hot Water alongside it)**,
specifically because it's simpler: pressure-fed (no slope/gravity math),
the office's pipe types are already loaded (Valsir PEXAL Brass), and one
concrete office convention was given directly - every valve sits at exactly
1800mm above its level (`Standard.mep_valve_height_mm`).

This does not undo the reasoning above for why Sanitary was chosen as the
*first* slice (it forced the harder routing/sizing problems early) - the
multi-segment elbow-routing shape and real Piping-API fitting creation that
Water Supply now depends on were built and live-verified specifically
*because* Sanitary's slice had already proven the simpler single-segment
case first. Water Supply is picking up a framework that's more ready for it
than it would have been if built first. Sanitary Drainage itself is paused,
not abandoned - its pushbutton, domain logic, and 261+ passing tests stay in
the codebase - and resumes whenever the product owner returns to it.

**What Water Supply explicitly does NOT get yet, matching this ADR's own
"don't invent it without asking" rule:** a fixture-unit-based pipe sizing
method (BS 8558 / BS EN 806-3 or otherwise) - undecided, not guessed. Slice
1 of Water Supply sizes each segment from the fixture's own connector
diameter, the same disclosed simplification Sanitary Drainage started with
before any Standard-driven sizing engine existed.

## Context

The long-term goal is one unified MEP platform: Sanitary, Cold Water, Hot Water,
Vent, Storm, Grey/Black Water, Rainwater Harvesting, Fire Protection, Medical Gas,
Gas, Hydronic, HVAC Ductwork, Cable Trays, Electrical Conduits — all sharing one
routing/rule/fitting/sizing/validation framework, with a Building Intelligence
Engine underneath and an AI orchestration layer on top.

A first pass at scoping this asked for the complete platform design up front —
every engine, every discipline, a 10-step wizard — before any code. ADR-0002
already answered this question for the suite as a whole: speculative frameworks
built against imagined requirements are a leading cause of death for ambitious
tool suites, because the abstractions are discovered to be wrong only when a real
second consumer refuses to fit them. Every module shipped so far (Auto Dimension,
Grid Dimensions, Wall & Opening Dimension, Structural Dimensions, Auto Mark) was
corrected at least once by the product owner trying it against a real project —
routing engines for 15 MEP disciplines are a much larger, much less legible
problem than dimension placement, which makes premature generalization here more
dangerous, not less.

## Decision

Treat MEP the same way Documentation was treated: **build one real system
end-to-end first — Sanitary Drainage — then extract the shared routing/rule/
sizing/validation framework once a second discipline (Cold Water is the leading
candidate) actually needs it.** Sanitary was chosen over Cold Water as the first
slice specifically because it is the *harder* case (slope, DFU-based sizing,
gravity-only routing, branch/vent interaction) — proving the shared abstractions
against the hard case first means Cold Water, Vent, and Storm are more likely to
fit them later without rework, matching the same logic ADR-0002 used for why
Auto Dimension (not a simpler tool) became Module 01's reference implementation.

The full software design document requested (Building Intelligence Engine, Rule
Engine, Routing Engine, Connector Detection, Geometry Engine, Fitting Engine,
Validation Framework, Preview Framework, full 10-step wizard, AI layer for all
disciplines) is **not built now.** [`MEP_SAD.md`](../architecture/MEP_SAD.md)
designs only what Sanitary Drainage's vertical slice needs, using the *shape* of
each requested engine so the abstractions generalize later, but implementing only
the Sanitary-specific behavior behind each one.

## Consequences

- **Positive:** Sanitary Drainage can reach a real, live-tested, working state
  (same bar as every other shipped module: unit-tested domain + verified against
  the product owner's actual project) without months of speculative design first.
  Every abstraction that does get built (Routing, Rule, Sizing) is justified by
  Sanitary's real requirements, not a guess about what Cold Water or HVAC will
  need — matching ADR-0002's "nothing enters shared code until a second module
  needs it" rule.
- **Cost:** Building Sanitary first does not validate the framework's fit for
  pressure-fed systems (Cold/Hot Water), fully mechanical systems (HVAC), or
  non-pipe systems (Cable Trays, Conduits) until those slices are actually built.
  Some rework of `domain/mep/routing` and `domain/mep/sizing` at the Cold Water
  slice should be expected and budgeted for, not treated as a planning failure.
- **Explicitly deferred, not designed at all yet:** HVAC Ductwork, Cable Trays,
  Electrical Conduits, Fire Protection, Medical Gas, Gas, Hydronic — these get
  their own vertical slice and their own extraction pass later. The 10-step
  Generation Wizard, the Family Mapping persistence system, and the full
  Building Intelligence Engine (linked models, worksets, design options, phases,
  existing stacks/shafts detection) are also deferred until a real slice
  demands each piece — see `MEP_SAD.md` §8 for the full explicit non-goals list.
- **Rule (mirrors ADR-0002):** nothing graduates from `domain/mep/<sanitary
  concept>` into a shared `domain/mep/routing|sizing|validation` module used by
  more than one discipline until a second real discipline's command is being
  built and needs it.
