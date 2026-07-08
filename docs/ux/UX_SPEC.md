# BK BIM Tools — UI/UX Specification

- **Status:** Draft v0.1 (2026-07-05)
- **Scope:** design tokens + shared shell layout + icon system + WPF component
  inventory. Deliberately **not** per-module pixel mockups — those are drawn against
  this token set as each module reaches its UI phase, so we don't spend visual-design
  effort on modules that don't exist yet.

Related: [SAD §4.5](../architecture/SAD.md#45-ui) · [PRD §4](../product/PRD.md#4-ribbon-tab-bk-bim-tools) ·
[ADR-0001](../ADR/0001-python-engine-strategy.md) (XAML-first, for the C# port).

---

## 1. Design principles

Modern · minimal · professional · engineering-focused · dark-mode compatible ·
consistent spacing · rounded corners where appropriate · responsive · low clutter.
Every module must feel like part of one application, not a collection of scripts —
this is enforced structurally by the shared shell (§3) and tokens (§2), not by
per-developer discipline.

## 2. Design tokens

Tokens live as a XAML `ResourceDictionary` (`ui/themes/Tokens.xaml`) so they port to
C# WPF with no translation step. Values below are the initial lock; refine visually
once the walking skeleton renders, but the *names* and *scale* should not change
(modules will bind to names).

### 2.1 Color

| Token | Light | Dark | Use |
|---|---|---|---|
| `Color.Brand.Primary` | `#1A56DB` | `#3B82F6` | Brand accents, primary buttons, active nav |
| `Color.Brand.PrimaryHover` | `#1E40AF` | `#60A5FA` | Hover/pressed states |
| `Color.Surface.Base` | `#FFFFFF` | `#121417` | Window background |
| `Color.Surface.Raised` | `#F7F8FA` | `#1B1F24` | Panels, cards |
| `Color.Surface.Sunken` | `#EDEFF2` | `#0D0F12` | Inset areas (preview pane) |
| `Color.Border.Default` | `#DFE3E8` | `#2A2F36` | Dividers, input borders |
| `Color.Text.Primary` | `#111417` | `#F0F2F4` | Headings, body |
| `Color.Text.Secondary` | `#5B6572` | `#9AA4B2` | Captions, descriptions |
| `Color.Text.Disabled` | `#AAB2BC` | `#5A6270` | Disabled controls |
| `Color.Status.Success` | `#1E9E5A` | `#34D399` | Run complete, valid |
| `Color.Status.Warning` | `#B98900` | `#FBBF24` | Non-fatal issues |
| `Color.Status.Error` | `#D13438` | `#F87171` | Failures |
| `Color.Status.Info` | `#1A56DB` | `#60A5FA` | Neutral status |

Modules never hardcode hex — always bind to a token. This is what makes dark mode
and future rebrands a token-file edit, not a per-view change.

### 2.2 Typography

| Token | Family | Size | Weight | Use |
|---|---|---|---|---|
| `Type.Display` | Segoe UI Semibold | 22 | 600 | Header module name |
| `Type.Title` | Segoe UI Semibold | 16 | 600 | Section titles |
| `Type.Body` | Segoe UI | 13 | 400 | Body text, labels |
| `Type.Caption` | Segoe UI | 11 | 400 | Descriptions, hints |
| `Type.Mono` | Cascadia Mono | 12 | 400 | Values, coordinates, logs |

Segoe UI is the safe default on Windows/Revit hosts; no custom font install
dependency. Revisit if brand guidelines later require a licensed typeface.

### 2.3 Spacing & radius (4px base grid)

| Token | Value |
|---|---|
| `Space.XS` | 4 |
| `Space.S` | 8 |
| `Space.M` | 16 |
| `Space.L` | 24 |
| `Space.XL` | 32 |
| `Radius.Control` | 6 |
| `Radius.Card` | 10 |
| `Radius.Window` | 12 |

### 2.4 Elevation
Two levels only: `Elevation.Flat` (borders, no shadow — default) and
`Elevation.Raised` (subtle shadow, for popovers/dropdowns). Avoid deep shadow stacks —
reads as dated, not premium.

## 3. Shared shell — `ModuleWindow`

Every module (above the "simple `forms`-tier" bar, see §5) renders inside one shell,
so consistency is structural:

```
┌───────────────────────────────────────────────────────────────────────────┐
│ HEADER   [BK logo]  BK BIM Tools  ›  {Module Name}                         │
│          {one-line module description}                                     │  Type.Display / Caption
├───────────┬───────────────────────────────────────────────────────────────┤
│ LEFT NAV  │  WORKSPACE                                                     │
│           │  ┌─────────────┐  ┌─────────────────────────────────────────┐ │
│ Documentation│ │  Preview   │  │  Options / Filters / Presets            │ │
│ Modeling  │  │  (image or │  │  (module-specific form, tokenized        │ │
│ QA/QC     │  │   live     │  │   controls: dropdowns, toggles, sliders) │ │
│ AI        │  │   snapshot)│  │  ▸ Advanced settings (expandable)         │ │
│ Utilities │  └─────────────┘  └─────────────────────────────────────────┘ │
│ Settings  │                                                               │
├───────────┴───────────────────────────────────────────────────────────────┤
│ FOOTER   [progress bar ───────────]  ETA: 00:12   Status: "Scanning..."   │
│          [Help]                                    [Cancel]  [Run]        │  Type.Body / Mono
└───────────────────────────────────────────────────────────────────────────┘
```

- **Header** — always shows brand + breadcrumb (`suite › module`) + description.
  Never module-customized beyond the description string.
- **Left nav** — the six ribbon panel categories; highlights current module's
  category; lets users jump to sibling tools without closing the window.
- **Workspace** — two-pane: preview (left, `Surface.Sunken`) + options
  (right, `Surface.Raised`). Advanced settings collapse by default (low clutter).
- **Footer** — progress + ETA + status message are **required bindings** on every
  command's `Result`/progress-report contract (SAD §4.4) — a module cannot opt out of
  showing progress.
- **Run/Cancel** — Cancel is always enabled once Run starts; commands must observe a
  cancellation token (ties to SAD §6 performance requirement).

### 3.1 View tiers (cost-managed UI investment, per your steer)

| Tier | When | Vehicle |
|---|---|---|
| **Tier 1 — Simple** | Single confirm/alert, one or two inputs | pyRevit `forms` (still WPF underneath; near-zero cost) |
| **Tier 2 — Standard** | Most modules: options + presets + run | `ModuleWindow` shell with a generated/simple options panel |
| **Tier 3 — Flagship** | Auto Dimension, AI Assistant, Dashboard | `ModuleWindow` shell + fully custom WPF content, live preview |

A module can graduate tiers later without a rewrite — the shell contract is the same.

## 4. Icon system

- Style: line icons, 2px stroke, 24×24 artboard, single accent color
  (`Color.Brand.Primary`) on transparent — matches your existing Icons8 convention
  (per [[bkdesigns-pushbutton-convention]]).
- Ribbon sizes: pyRevit requires 32×32 (large) and 16×16 (small) PNG; author at 24×24
  SVG (or source at Icons8) and export both raster sizes — SVG is the source of
  truth for a future in-app icon set / C# resource dictionary.
- One icon per module, one shared "BK BIM Tools" mark for the tab itself and the About
  button.
- Naming: `icon_{module-slug}_{size}.png` under each `.pushbutton/`; SVG masters kept
  in `ui/icons/svg/` for regeneration.

## 5. Interaction patterns (consistent across modules)

- Every destructive/irreversible action (Replace, Delete duplicates, Project Cleaner)
  requires an explicit confirm step — never a bare "Run".
- Every long-running command shows progress + supports Cancel (no exceptions).
- Errors render as a `Result.failure` message in the footer status line, never a raw
  Revit exception dialog (SAD §5 error strategy).
- Presets and Standards selectors are always in the same workspace position
  (top-right of the options pane) across modules, so users build muscle memory.

## 6. Dark mode

Driven entirely by swapping the `Tokens.xaml` color dictionary based on Revit's/OS
theme; no per-view dark-mode logic. Verify contrast on `Color.Text.Secondary` over
`Color.Surface.Sunken` in dark mode specifically — that pairing is the most likely to
fail contrast checks and should be checked once the shell first renders.
