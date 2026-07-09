# BK BIM Tools — Product Requirements Document (PRD)

- **Product:** BK BIM Tools — *Professional Revit Automation & AI Productivity Suite*
- **Vendor:** BK Designs
- **Status:** Draft v0.1 (2026-07-05)

## 1. Vision

A unified, modular Revit productivity ecosystem for architects, structural/MEP
engineers, interior designers, and BIM coordinators worldwide. Auto Dimension is
Module 01 of a suite designed to grow to dozens of modules without re-architecture.
UX quality bar: Autodesk / Bluebeam / Enscape / Ideate / DiRoots.

## 2. Target users

Architects · Structural engineers · MEP engineers · Interior designers · BIM
coordinators · Construction & documentation teams · Engineering consultants.
International; multi-standard.

## 3. Product principles

1. **Deterministic core, AI as interface** — reproducible results; AI parameterizes
   existing commands.
2. **Every automatic behavior is configurable** — smart defaults, full override.
3. **Standards-driven** — BS/ISO/AIA + office-custom, no code changes to add a standard.
4. **One unified experience** — shared shell, consistent interaction across modules.
5. **Additive growth** — a new module never destabilizes existing ones.

## 4. Ribbon (tab: "BK BIM Tools")

| Panel | Buttons |
|---|---|
| Documentation | Auto Dimension, Auto Tags, Auto Sheets, Auto Views, Auto Sections, Auto Elevations, Auto Callouts, Auto Keynotes |
| Modeling | Walls, Doors, Windows, Rooms, Floors, Roofs, Stairs, Structural |
| QA/QC | Standards Check, Clash Review, Missing Tags, Reports |
| AI | BK AI Assistant, Natural Language Commands, Prompt Library, Office Standards AI |
| Utilities | Project Cleaner, Batch Rename, Family Utilities, View Manager |
| Settings | Preferences, Presets, Office Standards, Updates, Licensing, Help (**About/Settings first**) |

## 5. Module 01 — Auto Dimension (first deliverable)

### 5.1 Scope of targets
Exterior/interior walls, wall faces & centerlines, overall/chain dimensions, doors,
windows, structural & architectural columns, grids, rooms, slabs, roofs, stairs,
foundations, structural framing.

### 5.2 View support
Floor plans, RCPs, sections, elevations, detail views, dependent views, area plans
(where applicable). Architectural **and** structural drawings.

### 5.3 Smart filtering (all configurable/override-able)
Auto-ignore: hidden, demolished, temporary, curtain walls, linked models, in-place
families, annotation objects.

### 5.4 Existing-dimension modes (user-selectable)
Ignore · Update · Replace · Delete duplicates · Keep existing · Prompt.

### 5.5 Standards
BS · ISO · AIA · office-custom profiles; user-creatable standard profiles.

### 5.6 Presets
Unlimited, import/export; seed set: Residential, Commercial, Office, Apartment,
Hospital, Airport, Retail, Hotel, Industrial, Educational, Custom. Each preset stores
every configurable option and references a Standard.

### 5.7 Non-functional
Must comfortably process houses → apartment complexes → malls → hospitals → high-rises
→ industrial → campuses → airports. Progress reporting + cancellation required.

### 5.8 Acceptance (Module 01)
Feature parity with the existing `Auto Dims SC v5` monolith, plus: no `DEBUG` global,
structured logging, unit-tested engines, standards/preset-driven configuration, and a
WPF settings window on the shared shell.

## 5A. Module 02 — Auto Mark

Numbers doors, windows, columns, beams, and footings for schedules -
lives in the Documentation panel's third group, alongside legends and
future scheduling tools.

### 5A.1 Scope of targets
Doors, Windows, Columns, Beams, Footings (Slabs deferred - no clean
length/width equivalent for an irregular sketched shape).

### 5A.2 Flow
Pick a category -> review window groups every placed family type (not
every instance) under its family, with an editable prefix per family and a
live preview of the mark each type would get -> Run writes the instance
Mark parameter (`ALL_MODEL_MARK`) across every placed instance of that
category.

### 5A.3 Numbering rule
One mark per family+type, shared by every instance of that type ("if the
family name and type is the same, they should have the same mark"). Per
family/prefix: types ordered largest-to-smallest by the category's
relevant dimension pair (Width x Height for Doors/Windows, B x H for
Columns/Beams, Length x Width for Footings) and numbered 1, 2, 3... -
every instance of type N gets that same mark. Numbering restarts at 1 per
family. A family left blank is skipped entirely.

### 5A.4 Scope notes
Doc-wide (every placed instance in the model, not view-scoped). Every run
overwrites existing Marks for every instance in the chosen category - no
partial/preserve mode. Per-family prefixes are remembered across runs and
projects (first real use of the suite's settings layer).

### 5A.5 Acceptance (Module 02)
Unit-tested numbering/sort logic (`tests/unit/test_mark_planner.py`,
`test_auto_mark_command.py`); live-verified against a real project file.

## 5B. Module 03 — Auto Tag

Tags marked doors, windows, columns, beams, or footings in whichever
view(s) the user picks - the natural next step after Auto Mark assigns
Marks. Lives in the Documentation panel's third group, right after Auto
Mark.

### 5B.1 Scope of targets
Same five categories as Auto Mark (Doors, Windows, Columns, Beams,
Footings) - one category per run, matching Auto Mark's own category
picker.

### 5B.2 Flow
Pick a category -> pick view(s) to run on (same multi-view picker every
dimensioning tool already uses) -> pick a tag family/type from what's
loaded in the project -> Run places one tag per untagged element of that
category, in every selected view.

### 5B.3 Duplicate handling
An element that already has a tag in a given view is skipped, not
re-tagged - safe to re-run as an "update," same convention the
dimensioning tools use for existing dimensions.

### 5B.4 Scope notes
View-scoped (unlike Auto Mark, which is doc-wide) - a Mark is one value
per type regardless of view, but a tag is a real annotation placed in one
specific view. Columns can resolve to either the architectural Column Tag
or the Structural Column Tag category depending on the element's own host
category; the tag-type list shows both when both are loaded, and only
elements matching the chosen type's category get tagged.

### 5B.5 Acceptance (Module 03)
Unit-tested tag/skip/fail counting logic (`tests/unit/test_auto_tag_command.py`);
live-verified against a real project file.

## 5C. Auto Mark & Tag (combined entry point)

A third way to run Modules 02/03: one pushbutton that runs Auto Mark
immediately followed by Auto Tag for the same category, so numbering and
tagging happen in a single pass. Pure orchestration on top of the existing
Auto Mark/Auto Tag flows - no new marking/tagging logic of its own.

### 5C.1 Ribbon arrangement
Three ways to invoke Modules 02/03 sit together in Documentation panel's
schedules group: the combined button (normal size, first) with the
individual Auto Mark and Auto Tag buttons stacked small immediately to its
right - a "triangle" layout, so all three are visible without opening a
menu.

### 5C.2 Acceptance
Live-verified against a real project file (rolled back) - see
docs/ROADMAP.md for the specific checks run.

## 6. Settings & presets (suite-wide)

Centralized manager; modules never manage settings independently. Domains: Themes,
Office Standards, Logging, Performance, AI, Developer Mode, Experimental Features,
Backup/Restore, Import/Export, future cloud sync.

## 7. AI (interface layer)

NL commands map to existing commands: e.g. "Dimension Level 2", "Dimension all
apartment units", "Dimension exterior walls only", "Dimension per British Standards",
"Dimension structural framing." Delivered through the existing MCP bridge. AI selects
and parameterizes commands; it does not generate Revit code.

## 8. Out of scope (now)

Cloud sync, commercial installer, DRM/licensing enforcement, C# rewrite — all have
architectural seams reserved (see SAD) but are deferred to later phases.

## 9. Success metrics (initial)

- Time-to-dimension a typical plan vs. manual (target: order-of-magnitude reduction).
- Correctness on the edge-case suite (§5 SAD) at 100%.
- Zero regressions across existing modules when adding a new one.
