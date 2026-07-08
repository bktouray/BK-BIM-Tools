# ADR-0003 — Extension Consolidation & Branding

- **Status:** Accepted (2026-07-05)
- **Deciders:** Product owner (BK Designs) + Lead Architect

## Context

Three extensions exist in the folder today:

- `AutoDims.extension` — the working dimensioning monolith (Module 01 logic).
- `BKDesigns.extension` — the branded shell (About panel, WallLegend tool, `lib/`,
  hooks); the established convention (per project memory) is that all new buttons live
  here, About/Settings first.
- `revit-mcp-python.extension` — the mature pyRevit Routes / MCP bridge for AI.

The product is **BK BIM Tools** by **BK Designs**. Fragmentation across three
extensions contradicts the "one unified suite" vision.

## Decision

1. **Consolidate into `BKDesigns.extension`** as the single suite container (honors
   the established memory convention).
2. **Fold `AutoDims` in** — its logic is refactored into `lib/bkbim/` under the
   layered architecture (see SAD); the old monolith is retired once at parity.
3. **Ribbon tab display name is "BK BIM Tools"** — brand-facing name on the tab, while
   the extension folder stays `BKDesigns.extension`.
4. **`revit-mcp-python.extension` stays a separate extension** (different engine,
   different lifecycle) but its MCP tools become thin callers of `bkbim.app` commands,
   so AI and ribbon execute the identical code path.

## Consequences

- **Positive:** one home, one brand, one command layer shared by ribbon + AI; honors
  existing convention; minimal disruption to the working MCP bridge.
- **Cost:** a migration step to move AutoDims logic into `BKDesigns.extension/lib`;
  the old `AutoDims.extension` is deprecated and eventually removed.
