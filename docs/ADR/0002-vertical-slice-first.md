# ADR-0002 — Vertical Slice First; Framework by Extraction

- **Status:** Accepted (2026-07-05); **corrected 2026-07-05** re: the AutoDims source.
- **Deciders:** Product owner (BK Designs) + Lead Architect

## Correction (2026-07-05)

The original version of this ADR called `AutoDims.extension` ("Auto Dims SC v5") "a
validated asset" with "proven logic." That was wrong. The product owner clarified:
**v5 was found on GitHub, written by someone else, and does not work well.** It is
third-party code of unverified quality, not this team's validated prior work.

This changes what Phase 1 is allowed to assume. The vertical-slice strategy itself
still holds (below), but the *substrate* is downgraded from "proven logic to port"
to "a candidate reference implementation to critically evaluate." Concretely:

- **Do not port v5 for feature parity.** Parity with a tool the owner says "doesn't
  work well" is not a meaningful acceptance bar.
- **Do extract validated Revit API technique from it where the technique itself is
  sound**, independent of whether the surrounding algorithm is correct — e.g. the
  symbol-geometry -> instance-reference conversion for family-instance dimension
  references is a real, hard-won Revit API pattern worth keeping regardless of bugs
  elsewhere in the file.
- **Phase 1 needs a correctness bar defined from first principles** (what a correct
  dimension placement actually looks like for BS/ISO/AIA, verified against real
  models) rather than "matches v5's output." See `docs/architecture/PHASE_1_PLAN.md`
  for how this is scoped.

## Context

The roadmap lists ~60 modules across Documentation, Modeling, QA/QC, AI, and
Utilities. The tempting approach is to build the shared platform (geometry engine,
standards engine, settings, DI, UI shell) first, then start modules. Speculative
frameworks built against imagined requirements are a leading cause of death for
ambitious tool suites: the abstractions are discovered to be wrong only when the
second real module refuses to fit them.

`AutoDims.extension` contains a 1,182-line third-party dimensioning script
(`Auto Dims SC v5`, sourced from GitHub) covering grid chains, snap/overall
dimensions, reference detection, and collision avoidance - useful as a map of the
*problem space* (what a dimensioning tool needs to handle) and a source of individual
Revit API techniques, but not as a source of trusted algorithms.

## Decision

Build **one complete vertical slice first** — build **Auto Dimension** through the
full layered architecture as the reference implementation — then **extract** the
shared platform from real, proven needs. The second module (**Auto Tags**) validates
each abstraction before it graduates into the shared platform. Framework by
extraction, never by speculation. Auto Dimension itself is engineered and tested from
first principles, using v5 only as a source of problem-space knowledge and select
Revit API techniques - not as a template to copy.

## Consequences

- **Positive:** every shared abstraction is justified by ≥2 real consumers; fastest
  path to a shippable, best-in-class Module 01 that is actually correct, not merely a
  cleaner-looking copy of a broken tool.
- **Cost:** more upfront design/testing work in Phase 1 than a straight port would
  have needed, since correctness must be established rather than assumed. This is the
  right tradeoff - a "clean" port of broken logic still produces wrong dimensions.
- **Rule:** nothing enters `bkbim.core`/shared `domain` until a second module needs it.
