# Changelog

All notable changes to BK BIM Tools are recorded here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versioning is SemVer per module and
per suite (SAD §5 versioning).

## Visible exterior-wall prompt with a real Yes/No choice; simplified tooltips; fixed author attribution

Product owner: "for the selection of walls, make it a visible prompt, it is
kinda subtle... give me an option to say yes or no to dimension the exterior
walls or just do the conventional dimension." Separately: "summerize the
pushbutton descriptions, make it simple when I hover over them... make the
author for all of the push buttons and anything else I create Baboucarr
Katim Touray and hard code it so that no one can change it."

### Changed - exterior wall prompt
- `wall_selection_prompt.pick_exterior_walls` now shows the branded Yes/No
  picker first ("Yes, dimension exterior walls (3 strings)" / "No, just
  conventional dimensioning") - choosing No skips straight to normal
  dimensioning, no picking required. Choosing Yes shows a real
  `forms.alert()` popup explicitly telling the user it's time to select
  exterior walls, BEFORE the interactive `PickObjects` prompt starts - the
  previous version only had a subtle status-bar hint.

### Changed - tooltips
- Every pushbutton's `__doc__` (shown on ribbon hover) rewritten from a long
  multi-paragraph developer changelog (product-owner quotes, dates,
  implementation history) down to 1-3 plain sentences describing what the
  button actually does for a user.

### Fixed - author attribution, and a real pyRevit bug found along the way
- Every pushbutton's `__author__` changed to "Baboucarr Katim Touray".
- **Investigated "hard code it so no one can change it" first**: tried
  importing a shared `AUTHOR` constant and assigning `__author__ = AUTHOR` -
  confirmed via direct testing that pyRevit parses `__title__`/`__doc__`/
  `__author__` via STATIC AST parsing (`ast.literal_eval` on the assigned
  node), not by executing the script - an imported name throws
  `ValueError: malformed string` and would have broken every button's
  bundle parse. Reverted to a literal string in every file (required), with
  `bkbim.core.branding.AUTHOR` kept as the documented single source of
  truth these literals must always match, plus an explicit comment in every
  script.py warning against the import pattern.
- **Found a genuine bug in this pyRevit build while verifying**: its own
  `genericcomps.py` extracts `__author__` into a variable, then
  IMMEDIATELY overwrites that variable with the result of extracting
  `__authors__` (plural) - discarding `__author__` entirely, confirmed by
  reading the exact source line. Fixed by adding `__authors__ = [u"..."]`
  to every script.py alongside `__author__` (kept for forward-compatibility
  if this bug is ever fixed upstream). Also added `author:` to the About
  button's `bundle.yaml` (a different, unaffected parsing path).

### Verified live (real project)
- Constructed the new Yes/No prompt directly - both choices render
  correctly, window sizes to content (420x354).
- Re-parsed the extension via `extensionmgr.get_installed_ui_extensions()`
  and confirmed every one of the 8 buttons' `.author` now reads "Baboucarr
  Katim Touray" (all showed `None` before the `__authors__` fix, despite
  `__author__` being set correctly - proving the bug was real, not assumed).
  Also confirmed every button's tooltip reflects the new short text.
- Replicated pyRevit's exact `extract_param()` AST-parsing logic against all
  7 script.py files directly - confirmed zero parse failures.
- 188 unit tests total (no change - pushbutton scripts and this prompt are
  Revit-import-only, not unit-tested by convention).

## Exterior wall 3-string dimensioning: adjustable gap, real outward direction, and a proper selection prompt

Product owner tried the exterior perimeter feature live and sent 3 fixes:
"its having wayyy too much gap between the strings so give me control over
that, and another thing, I always want it to go towards the exterior of the
building. And for the selection, make it after I select the autodimension
walls and openings and after I select dimension styles and other stuff,
prompt me to select exterior walls."

### Changed - gap is now adjustable, and smaller by default
- `Standard.wall_perimeter_gap_mm`'s default lowered from 1400mm to 700mm
  (matching every other tool's gap-field convention).
- `WallOpeningDimensionOptions.xaml`/`.py` gained a "Gap between exterior
  perimeter strings" slider+textbox, same pattern as the offset control -
  no longer only editable in code.

### Changed - each exterior wall now points toward its OWN exterior
- `auto_wall_opening_dimension_command.py` gained `_outward_side` /
  `_exterior_centroid`: computes the centroid of the WHOLE exterior-wall
  selection, then for each exterior wall, places all 3 of its strings on
  whichever side is further from that centroid - genuinely "outward" for
  every wall around the perimeter, not a single fixed `default_side` that
  only happened to be correct for walls on one side of the building.
  Non-exterior walls are completely unaffected, still using `default_side`
  as before. `wall_context_builder.py` now passes each wall's own
  `center_x`/`center_y` through for this comparison.

### Changed - selection moved to AFTER the options window
- The exterior-wall selection is no longer a pre-selection requirement.
  `AutoWallOpeningDimension.pushbutton` and `SmartDimension.pushbutton`'s
  Walls & Openings flow now show the options window FIRST (dimension
  style/offset/gap/wall types), and only after Run is clicked, prompt an
  interactive pick ("click exterior walls, then Finish - or Esc for none")
  via new `wall_selection_prompt.py` (`pick_exterior_walls`, wall-only
  `ISelectionFilter`). Pressing Escape or finishing with nothing picked is a
  normal outcome (every wall falls back to today's single-string behavior),
  not an error.

### Verified live (real project, rolled back)
- Constructed the updated options window directly: renders at 460x616 with
  the new Gap slider defaulting to 700mm.
- Ran the full pipeline against 29 real exterior-type walls in a real mixed
  view: 88 dimensions created, 0 errors, dimension count returned to its
  exact pre-existing value (0) after rollback.
- 6 new unit tests directly proving the outward-side math: two exterior
  walls on opposite sides of a synthetic building placed their strings on
  opposite sides (never both on the same side, which the old fixed-side
  logic would have done); a lone exterior wall falls back to `default_side`
  correctly (no divide-by-zero/arbitrary pick); non-exterior walls confirmed
  unaffected by the exterior centroid. 188 unit tests total.

## Exterior walls get a 3-string perimeter dimension (openings / perpendicular walls / overall)

Product owner, with a reference sketch of the standard French/European
perimeter-dimensioning convention: "I want 3 different strings going around
the footprint of the building to dimension the exterior walls. The first
string (closest to the wall) to measure the openings... the middle string to
take the start and end point of the wall and every wall attached to that
wall perpendicularly... then the third string to go above them all taking
the whole wall length."

### Investigated first
- Tried Revit's own `WallType.Function` (Exterior/Interior) to auto-detect
  which walls should get this treatment - checked live against a real mixed
  view: all 63 walls reported `Interior`, none tagged `Exterior`. Wall type
  names (`NEO_ARC_WALL_W3A_200MM_CMU_HOLLOW...`, `WC2_150MM...`) don't
  distinguish it either. Also checked whether a matching floor slab's real
  outline (reusing the outline-tracing work) could infer the footprint - the
  view has 9 separate slab pieces that don't correspond 1:1 to the wall
  footprint. Asked the product owner directly rather than guessing; decided
  on manual pre-selection: whatever walls are selected when the tool runs
  are treated as "exterior perimeter," everything else keeps today's
  single-string behavior.

### Added
- `wall_run_planner.py` gained `plan_wall_perpendicular_chain` (middle
  string - wall-end to wall-end, with every perpendicular/crossing wall's
  own reference as an intermediate point, ONE continuous chain that never
  splits, unlike the existing opening string) and `plan_wall_overall`
  (outer string - just the wall's own two end faces, no intermediate refs).
  Both reuse the exact same crossing-wall detection/reference data the
  existing opening string already computes - no new geometry-reading code.
  New `DimensionPlan.KIND_WALL_PERPENDICULAR_CHAIN`/`KIND_WALL_OVERALL` kinds.
- `Standard.offset_second_mm` (long unused, confirmed dead since Phase 0/1)
  renamed to `wall_perimeter_gap_mm` and put to real use: the spacing
  applied twice (String1->2, String2->3) to push each string progressively
  further out. Same 1400mm default.
- `wall_context_builder.build_walls_with_context` gained an
  `exterior_wall_ids` param; each wall's context dict gained `is_exterior`.
- `auto_wall_opening_dimension_command.run` builds the 2 extra strings for
  any wall flagged `is_exterior`, appended to whatever the existing opening
  string(s) already produced - non-exterior walls are completely unaffected.
- `AutoWallOpeningDimension.pushbutton` and `SmartDimension.pushbutton`'s
  Walls & Openings flow now read the user's CURRENT selection before doing
  anything else, and pass matching Wall elements through as
  `exterior_wall_ids` - select the exterior walls first, then run; select
  nothing and every wall behaves exactly as before.
- 12 new unit tests (5 in `test_wall_run_planner.py` for the two new domain
  functions, 4 in `test_auto_wall_opening_dimension_command.py` for the
  command-level wiring including a crossing-wall case, plus the renamed
  `wall_perimeter_gap_mm` field's existing coverage in `test_standard.py`).
  185 unit tests total.

### Verified live (real project, rolled back)
- Ran the full pipeline against a real mixed view (63 walls) with 5 real
  exterior-type walls flagged: 103 dimensions created vs. 93 with none
  flagged - exactly the expected +10 (5 walls x 2 extra strings each).
- Inspected one exterior wall with no openings/crossings: 3 separate
  dimension objects, all measuring the same 5500mm span (correct - nothing
  to differentiate them on this particular wall), confirming they're
  genuinely 3 distinct Dimension elements, not 1 merged/duplicated one.
- Ran against 10 real exterior walls with actual openings and crossings:
  33 dimensions, values ranging 250mm-11600mm, all architecturally
  plausible (opening widths, inter-wall spacings, overall lengths).
- Dimension count returned to its exact pre-existing value (0) after every
  rollback.

## Auto-Detect: option to skip column dimensions

Product owner, same-day follow-up: "for the autodetect option, i want an
option to do or not do column dimensions." Auto-Detect previously always
ran column dimensioning when columns were detected, with no way to opt out
short of picking a category manually instead.

### Changed
- `_run_auto_detect` now asks once, via the branded category picker
  ("Yes, include columns" / "No, skip columns"), but ONLY when columns are
  actually detected in the view - nothing to ask about otherwise. Grids and
  walls are unaffected - they still always run automatically when present.
  Cancelling this prompt aborts the whole Auto-Detect run (matches every
  other cancel-a-picker convention in this suite).

### Verified live
- Constructed the new prompt directly and confirmed both choices render
  correctly ("Yes, include columns" / "No, skip columns"), window sizes to
  content correctly (420x340).
- 173 unit tests total (no change - Revit-import-only pushbutton script).

## Smart Dimension gains Auto-Detect for mixed working-drawing views

Product owner: "sometimes i have walls and columns in the same view like a
working drawing... i usually have blockwork, plasterboard, openings and
grids dimensioned... i want the tool to autodetect what is in the view,
what to dimension and what not to. and i want it to always autodimension
grids if they're present." Previously Smart Dimension required picking ONE
category and coming back to the menu for each other one - no way to cover a
mixed view in a single pass.

### Added
- New `AUTO_DETECT` choice in `SmartDimension.pushbutton` (`_run_auto_detect`),
  listed first in the picker. Scans the view for grids, walls, and columns
  (structural + architectural) and runs each detected category's own
  existing flow in turn - grids ALWAYS run if any are present (never
  conditional on walls/columns also being there), walls and columns each
  run only if present. Beams/footings/slabs are deliberately NOT included -
  matches the literal "walls and columns in the same view" scope; those stay
  reachable via Structural Elements/Slab Dimensions directly.
- Each detected category still shows its own options window (dimension
  style, offset, wall/column type multi-select) exactly as it would if
  clicked directly - cancelling one just skips it and moves on to the next,
  it doesn't abort the whole run. Blockwork/plasterboard (separate wall
  elements per the project's per-layer modeling convention) are covered
  automatically since the Wall & Opening options window already defaults to
  every wall type selected.

### Verified live (real project, rolled back)
- Found a real mixed view ("L1 - GROUND FLOOR C.F.L": 18 grids, 63 walls,
  34 structural columns) and ran the full detect -> grids -> walls ->
  columns sequence end to end: 8 grid dimensions, 93 wall/opening
  dimensions, 136 column dimensions, 0 errors. Dimension count returned to
  its exact pre-existing value (0) after rollback.
- 173 unit tests total (no change - this is a Revit-import-only pushbutton
  script, not unit-tested by convention, consistent with the rest of this
  project's entrypoints).

## Investigated: angled/curved slab edges - confirmed a hard Revit API limitation, no code change

Product owner: "ITS NOT WORKING FOR IRREGULAR SLABS, ONLY FOR HORIZONTAL AND
VERTICAL. UPDATE ALL DIMENSION TOOLS TO WORK WITH SLANTED LINES TOO, CURVES
AND ARCS... USE ARC LENGTH AND RADIUSES WHERE NECESSARY." Investigated
thoroughly against the real model before writing any code (this project's
established discipline for judgment calls) - conclusion: **not achievable
with Revit's public API in this environment**, confirmed by direct testing,
not assumption. No source files were changed as a result of this
investigation; the outline-tracing tool already does the right thing (skips
angled/curved edges rather than guessing wrong at them).

### What was checked
- Surveyed the real project first: 16/17 floors are fully rectilinear, all
  18 grids are orthogonal, 235/237 walls are orthogonal. Exactly ONE floor
  in the whole project is genuinely irregular - it has several straight
  edges at different angles plus 3 separate arc (`CylindricalFace`) segments.
- `Document.Create`'s full method list has exactly one dimension-creation
  method, `NewDimension(view, Line, references[, type])` - no
  `NewRadialDimension` or any Arc-accepting overload exists. True arc-length
  or radius dimension OBJECTS cannot be created via this API at all.
- Tested whether a straight, angled edge could at least be measured via the
  same "reference two neighboring faces" technique that works for every
  rectilinear corner in this codebase. Confirmed live, multiple ways (face
  references, edge references, isolating away from any arc-neighbor
  confound, all inside one transaction to rule out staleness): Revit's
  witness-line projection requires the reference geometry to be roughly
  perpendicular to the dimension's own direction. At a non-90-degree
  corner, this is unavoidable - the result is either a degenerate
  "-304.8mm" sentinel value or a plausible-looking but WRONG number (a real
  2300mm edge measured as 5672.5mm). `dim.Curve` on the degenerate case
  comes back as an unbound (invalid) curve - the "dimension" isn't
  meaningfully created at all, just doesn't throw.
- Also tested the product owner's own suggestion - "use the aligned
  dimension tool, point to point, corner to corner" - directly. Same
  result: whatever Revit's own Aligned Dimension ribbon command does
  internally isn't exposed through the one documented `NewDimension` API
  path available here.

### Decision
Product owner, once the finding was clear: leave angled/curved edges
unlabeled - matches the tool's current behavior exactly (dimensions the
orthogonal portions correctly, silently skips anything angled or curved).
The one alternative that WAS verified to give correct values - computing
each edge's real length/radius directly from geometry and placing it as a
`TextNote` instead of a live Dimension - was offered and declined.

**Lesson for any future attempt**: don't retry the "reference two
neighboring faces/edges" witness technique for non-perpendicular geometry -
this is now conclusively verified broken, not merely unexplored. A future
attempt would need either a fundamentally different Revit mechanism (none
found in this API surface) or the TextNote-based accurate-but-non-live
annotation approach.

## "All edges of the slab" traces the REAL outline, not the bounding box

Product owner sent a screenshot of a real notched/stepped slab footprint
(a rectangle with a rectangular notch cut from the bottom-middle - like an
upside-down "H"), with the whole perimeter traced in red: "edge to edge is
still not working as I want it to... I want dimensions to follow every slab
face." Every earlier iteration of this mode approximated the slab as its
axis-aligned bounding box (4 faces) - correct for a plain rectangle, silently
wrong for anything with a step or notch, since the bounding box simply
doesn't have that information.

### Added
- `domain/models/outline_edge.py` (`OutlineEdge`) - one straight, axis-aligned
  boundary segment: its own face-normal axis, coordinate, real span (not the
  bounding box's), and outward-facing sign.
- `revit/adapter/reference_provider.py` gained `outline_edges_for(element)` -
  reads EVERY planar side face of an element's solid (not just the two
  extremes per axis, contrast with `faces_for`), using
  `PlanarFace.GetBoundingBox()`/`Evaluate()` to read each face's own real
  extent. Curved/diagonal side faces are skipped, matching this codebase's
  existing axis-aligned-only scope.
- `domain/dimensioning/slab_outline_planner.py`
  (`plan_slab_outline_dimensions`) - pure, no Revit imports. For each real
  edge, finds its two ADJACENT PERPENDICULAR edges (the ones sharing its two
  corners) by matching coordinates exactly, and dimensions the edge's own
  length referenced to those two neighbors' own faces - the same
  "reference a face" technique used everywhere else in this codebase,
  applied per real corner instead of per bounding-box extreme. New
  `DimensionPlan.KIND_SLAB_OUTLINE_EDGE` kind.
- `app/commands/auto_slab_outline_dimension_command.py` - zero Revit
  imports, mirrors the other app commands' structure (skip-if-exists,
  scoped failure counting). 7 new fake-based tests.
- `structural_dimension_flow._run_slab_outline` - a SEPARATE pipeline from
  the shared `_run_command`/`auto_structural_dimension_command` (which stays
  unchanged for Column/Beam/Footing and Slab's "Grid to slab edges" mode),
  used only when `options.mode == MODE_OVERALL_ONLY`. Never needs grids at
  all - fixed an existing minor bug in the same change where "All edges"
  mode required grids to be present even though it never referenced them.

### Verified live (real project, rolled back)
- Read the product owner's actual notched slab's real geometry directly:
  confirmed it has exactly 8 side faces (not 4), matching the screenshot's
  shape exactly (a rectangle with a rectangular notch removed from the
  bottom-middle) - used these REAL coordinates as the unit test fixture, not
  a synthetic guess.
- Ran the full corrected pipeline against this slab in a rolled-back
  transaction: 8 dimensions created (one per real edge, not the old 2 for
  the bounding box), 0 skipped, 0 errors. Inspected every created
  dimension's actual value: 21700/11200/11200/4375/4375/12950/600/600mm -
  all architecturally sensible (the two portions of the bottom edge on
  either side of the notch, the notch's own width and two short side jogs).
  Dimension count returned to its exact pre-existing value (0) after
  rollback.
- 173 unit tests total.

## Toggle Grid 2D/3D: two real bugs fixed, now working end to end

Product owner tried Toggle Grid 2D/3D twice, hitting a different bug each
time. First: "I'm still not seeing the grid utility." Root cause:
`Utilities.panel/bundle.yaml` had an explicit `layout: [CountSelected]`
(written when the panel had only one button) - pyRevit treats a panel's
`layout:` as the exhaustive list of what to show in the ribbon, so
`ToggleGridExtent` was silently excluded even though it parsed correctly on
disk. Fixed by adding it to that list. Swept every other panel's
`bundle.yaml` against its actual folder contents - nothing else was affected.

Second, after the button appeared and was clicked: "0 grid(s) toggled
between 2D/3D, 18 failed." Root cause: `grid_extent_writer.py` called
`Grid.SetDatumExtentTypeInView(...)`, which doesn't exist on this Revit API
version - `AttributeError`. The GETTER really is
`GetDatumExtentTypeInView`, but the SETTER is just `SetDatumExtentType` (no
"InView" suffix), confirmed via live reflection (`dir()`/`help()`) against
the real `Grid` object. Same `(datumEnd, view, extentMode)` signature
otherwise. Fixed the one call site.

**Live-verified** (real project, rolled back): ran the corrected writer
against all 18 real grids in a rolled-back transaction - toggled Model ->
ViewSpecific, re-read within the same transaction to confirm the flip
actually applied (not just "no exception"), ran it again and confirmed every
grid returned to its original state. 159 unit tests total (unaffected - the
bug was Revit-adapter-only code, not unit-tested under CPython by
convention).

## Every-corner slab dimensioning; auto-fit windows; slab icon; ribbon findability fix

Product owner tried the previous batch and sent 4 more items: (1) "make the
windows auto fit everything in the window, I don't want to be manually
adjusting everytime but still make it adjustable"; (2) Slab Dimensions'
"Grid to slab edges" mode should "take every slab corner, not just the 4
sides"; (3) "I can't find the grid tool" (Toggle Grid 2D/3D); (4) the Slab
category-picker icon "looks the same as the beam" - asked for "two small
downstanding beams on each side" instead.

### Changed - every slab corner, not just 4 sides
- `column_grid_planner._plan_grid_to_each_edge` (MODE_GRID_ONLY) now places
  each face's grid-referenced dimension at BOTH perpendicular offsets, not
  just one - up to 8 dimensions per rectangular slab (2 faces per axis x 2
  corner-positions) instead of 4, so every corner gets its own witness
  dimension. Live-verified: the real project's one visible slab went from 2
  dimensions (old bug) to 8 (this fix) in the same view.
- Rewrote/added tests accordingly; 22 tests in `test_column_grid_planner.py`,
  159 total.

### Fixed - windows now auto-fit their content
- All 5 WPF option windows (`CategoryPicker`, `StructuralDimensionOptions`,
  `SlabDimensionOptions`, `GridDimensionOptions`,
  `WallOpeningDimensionOptions`) switched from a fixed `Width`/`Height` to
  `SizeToContent="Height"` with a fixed `Width` - height now always fits the
  actual content (no more manual resize-to-see-everything), width stays
  fixed and adjustable via the resize grip.
- **Two real WPF bugs hit and fixed while building this**: (1) first attempt
  used `SizeToContent="WidthAndHeight"`, which made every `TextWrapping="Wrap"`
  subtitle measure as one unbroken line (no width to wrap against) - blew
  windows out to 800-1000px wide. Fixed by keeping `Width` fixed and only
  auto-sizing height. (2) A `Grid.RowDefinition Height="*"` row that holds
  REAL content (the category picker's `ChoicesPanel`) collapses to ~0 height
  under `SizeToContent`, since a Grid can't compute a proportional share of
  infinite available space - only an empty trailing spacer row should ever
  be `"*"`. Fixed by changing that one row to `Auto`. Both caught via a live
  WPF layout check (`Show()` + dispatcher pump + `ActualWidth`/`ActualHeight`),
  not just visual inspection.

### Changed - slab icon
- `structural_category_icons._slab_glyph` redesigned: a wide flat top bar
  (the slab) with two small rectangles hanging below at each end (downstand
  beams), replacing the plain thin bar that was visually identical to the
  Beam glyph.
- `CategoryPicker.xaml`'s `ChoiceButton` style gained
  `FocusVisualStyle="{x:Null}"` - the default WPF dashed focus rectangle was
  drawing oddly across whichever button had keyboard focus, visible in the
  product owner's screenshot as a stray blue mark on the Beam button.

### Investigated - "can't find the grid tool"
- Not a bug: confirmed live via `extensionmgr.get_installed_ui_extensions()`
  that `ToggleGridExtent` parses correctly as a `PushButton` under
  `Utilities.panel`. A brand-new pushbutton needs an explicit pyRevit ▸
  Reload to appear in the ribbon even after a full Revit restart - the
  underlying file tree was already correct, the ribbon UI just hadn't been
  rebuilt yet.

## Slab Dimensions rebuilt per-face; extension renamed; icons lightened; grid 2D/3D toggle added

Product owner follow-up the same day as the previous entry: the "Grid to slab
edges" mode still shared ONE grid (nearest the element's center) across both
faces of an axis - "I want the reference to be taken from the closest grid to
that specific slab corner and same for every corner, not the center grid to
the outmost edge." And "All edges of the slab" only produced 2 dimensions
(one per axis) against 4 physical sides - "I don't want it on just two
sides, I want it on all sides of the slab, every single edge must be
measured... give me both options." Same message also asked for 4 unrelated
items: rename the extension to "BK BIM Tools," lighten every non-logo icon,
add small icons to the Structural Element Dimensions picker, and a new
utility to toggle grids between 2D and 3D.

### Changed - Slab Dimensions, genuinely per-face this time
- `column_grid_planner.py`: `MODE_GRID_ONLY` and `MODE_OVERALL_ONLY` rebuilt
  from scratch as per-FACE (4 faces: min_x/max_x/min_y/max_y), never
  per-axis-shared. `_plan_grid_to_each_edge` finds each face's own closest
  grid of matching orientation independently. `_plan_all_edges_no_grid`
  places each axis's face-to-face span twice (once outside each face) so all
  4 sides get their own witness dimension. New `DimensionPlan.
  KIND_SLAB_EDGE_TO_GRID` kind (log messages only). `_plan_individual_column_
  dimensions` (MODE_GRID_AND_COLUMN, Column/Beam/Footing) simplified back to
  its unconditional form now that the previous `include_detail`/
  `include_overall` split has no other caller.
- Rewrote the 3 unit tests that asserted the old per-axis-shared behavior;
  added 3 that prove the fix directly (closest-to-face, not closest-to-center;
  all-4-sides placement). 21 tests in `test_column_grid_planner.py`, 158 total.

### Changed - extension renamed
- `BKDesigns.extension` -> `BKBIMTools.extension`, `BKDesigns.tab` ->
  `BKBIMTools.tab`, `BKDesigns.panel` -> `About.panel`. The ribbon tab
  already displayed "BK BIM Tools" since Phase 0; only the folders/panel
  underneath still said "BKDesigns."
- Fixed the one functional cross-extension reference:
  `revit-mcp-python.extension/revit_mcp/selection.py`'s hardcoded
  `sys.path.insert` now points at `BKBIMTools.extension/lib`.
- Deleted every orphaned `*BKDesigns*` cache/dll file under
  `%APPDATA%\pyRevit\2026\`.

### Changed - icons
- All 6 tool `icon.png` files recolored from pure `#000000` to `#333333`
  (every opaque pixel's RGB overwritten directly, alpha untouched). The
  About panel's BK Designs logo (multi-color brand asset) is untouched.

### Added - category-picker icons
- `structural_category_icons.py`: 4 plain-WPF-shape pictograms (Column,
  Beam, Footing, Slab) at `#333333`, no image files or network fetch needed.
  `category_picker.py` gained an optional `icon_factory` param; wired in
  only for Structural Element Dimensions' picker, not Smart Dimension's
  top-level one.

### Added - Toggle Grid 2D/3D utility
- New `ToggleGridExtent.pushbutton` (Utilities panel): flips every grid in
  the current view between 2D (`DatumExtentType.ViewSpecific`) and 3D
  (`DatumExtentType.Model`), per grid end independently - a symmetric
  toggle, so running it twice returns everything to its original state.
- New layer: `domain/models/grid_extent.py` (`toggle_extent`,
  `GridExtentInfo`), `domain/grids/ports.py` (`IGridExtentWriter`),
  `app/commands/toggle_grid_extent_command.py` (6 new fake-based tests),
  `revit/adapter/grid_extent_reader.py`/`grid_extent_writer.py`.

### Fixed
- Building the grid-toggle icon hit a real bug: Lucide icons are
  stroke-based (`stroke="currentColor"`, `fill="none"`) and svglib does not
  resolve the CSS keyword `currentColor` - the icon rendered with zero
  opaque pixels until the SVG was pre-processed to substitute a literal
  `#000000` before calling `svg2rlg`.

### Verified live (real project)
- Slab per-face fix: ran the corrected pipeline against the project's one
  visible slab (18 grids) in both modes, rolled back.
- The extension rename hit a real file lock ("Device or resource busy") while
  Revit was still running with the extension loaded; resolved by asking the
  user to close Revit first, then renaming succeeded immediately.
- Icon lightening, category-picker icons, and the grid-toggle utility were
  NOT yet live-verified against a running Revit session in this same batch -
  Revit stayed closed after the rename; needs a fresh pyRevit reload and a
  first real click-through.

## Slab Dimensions: two independent modes; standalone pushbutton removed

Product owner: "recheck the slab dimension tool. I want two options, one
from grid to slab edges, and another measuring all edges of the slab. And
since its already in the structural dimension push button, having its own
pushbutton is seems useless." Slab Dimensions previously reused
`MODE_GRID_AND_COLUMN`, which always bundled a detail (grid-referenced)
dimension together with an overall (edge-to-edge) one - not what was asked
for.

### Added
- `column_grid_planner.py` gained `MODE_GRID_ONLY` and `MODE_OVERALL_ONLY` -
  the same per-element machinery as `MODE_GRID_AND_COLUMN`, split into two
  independently selectable modes via new `include_detail`/`include_overall`
  flags on `_plan_individual_column_dimensions`. `MODE_OVERALL_ONLY` places
  its dimension at the plain offset (not offset+gap) since there's no detail
  string it needs to clear when used alone.
- 4 new unit tests covering both new modes plus the offset-placement
  difference (`test_column_grid_planner.py`), all passing alongside the
  existing 16 (20 total, zero regressions).

### Changed
- `SlabDimensionOptions.xaml`/`slab_dimension_options.py` rebuilt around the
  two new modes: "Grid to slab edges" (`MODE_GRID_ONLY`) and "All edges of
  the slab" (`MODE_OVERALL_ONLY`), replacing the old bundled-mode radios.
  Dropped the "Gap to overall string" field entirely - neither mode uses it,
  since gap only matters when detail and overall coexist. The offset field's
  label now switches text ("Offset from grid line (mm)" / "Offset from slab
  edge (mm)") depending on which mode is selected.
- `structural_dimension_flow.py`'s `_run_slab` updated to the new
  `show_slab_dimension_options` signature (no gap parameter).

### Removed
- Standalone `SlabDimension.pushbutton` deleted entirely (script.py,
  icon.png) - redundant now that Structural Element Dimensions' category
  picker already reaches Slab in one click. Removed from
  `Dimensioning.panel/bundle.yaml`'s `layout:` list. Smart Dimension's
  direct "Slab Dimensions" menu entry was kept (the complaint was about the
  standalone ribbon button, not Smart Dimension's own menu).

### Verified live (real project)
- Imported the updated modules directly in the live Revit session; confirmed
  `MODE_GRID_ONLY`/`MODE_OVERALL_ONLY` exist and `default_standard()` still
  reports 300mm offsets.
- Ran the full Slab Dimensions pipeline against the real project's one
  visible slab (18 grids) in both new modes inside a rolled-back
  transaction: `MODE_GRID_ONLY` -> 2 dimensions created (X + Y axis),
  `MODE_OVERALL_ONLY` -> 2 dimensions created; dimension count before/after
  confirmed identical (0), no residue.
- Constructed `SlabDimensionOptionsWindow` directly against the real slab
  types and confirmed: title "BK BIM Tools - Slab Dimensions", offset label
  defaults to "Offset from grid line (mm)", radios read "Grid to slab edges"
  / "All edges of the slab", offset slider defaults to 300.0.
- Confirmed `structural_dimension_flow.CATEGORIES` still includes `"Slab"`.
- 151 unit tests total.

## Branded category picker; per-category wording; 300mm default offsets

Product owner tried the new category picker: "I don't like the default
pyRevit interface when I click Structural Dimensions, make it nice." Also
caught a real copy-paste artifact - picking "Beam" still showed mode radio
buttons reading "Column edge - grid - column edge..." Also asked for a
uniform 300mm default offset across every tool (was 800/1500/800mm depending
on tool), and reconfirmed Slab should be reachable from Structural Dimensions
(already was, from the same-day category picker work).

### Added
- `ui/views/CategoryPicker.xaml`/`category_picker.py` - a branded WPF picker
  (same visual language as every options window: "BK BIM TOOLS" caption,
  brand-blue accents, hoverable choice buttons) replacing pyRevit's default
  `forms.CommandSwitchWindow` everywhere it was used (Structural Dimensions'
  category picker, Smart Dimension's top-level tool picker).
- `structural_dimension_options.py` gained a `_CATEGORY_TEXT` dict with fully
  bespoke wording per category (Column/Beam/Footing) - window title, subtitle,
  BOTH mode-radio descriptions, and the type-list helper text are all written
  for that specific category, not a shared template with only the header
  swapped. Beam's wording explicitly mentions "measuring beam to beam and
  taking in each beam's own width," matching the original ask.

### Changed
- `Standard`'s three actively-used offset defaults (`offset_first_mm`,
  `grid_chain_offset_mm`, `structural_chain_offset_mm`) changed from
  800/1500/800mm to a uniform 300mm. Gap fields (`grid_chain_gap_mm`,
  `structural_chain_gap_mm`, both 700mm) and the unused `offset_second_mm`
  were left as-is - only "offsets" were asked for.

### Verified live (real project)
- Confirmed `default_standard()` now reports 300.0 for all three offset
  fields, with gap fields unchanged at 700.0.
- Constructed the branded category picker directly (no modal shown, to keep
  automated testing non-blocking): 4 choice buttons present (Column, Beam,
  Footing, Slab).
- Constructed the Beam/Column/Footing options windows directly and confirmed
  each one's title, subtitle, and BOTH mode-radio labels are genuinely
  category-specific (e.g. Beam's continuous-mode radio explicitly says
  "taking in each beam's width," Column's says "column-to-column," Footing's
  says "footing-to-footing") - no leftover copy-paste text from any other
  category.
- 147 unit tests total (no change - this is Revit-import-only UI code).

## Structural Dimensions gets a category picker - "I don't know what's what"

Product owner, screenshot of the Structural Element Dimensions options window:
its "Types to dimension" list showed "200 x 300mm" / "200 x 200mm" /
"200 x 300mm" with no indication which were columns, beams, or footings -
"this is confusing, I don't know what's what." Asked to either categorize the
list or, better, pick a category (Column/Beam/Slab/Footing) up front and
proceed from there - and floated folding Slab Dimensions in too.

### Added
- `revit/adapter/structural_dimension_flow.py` - the whole collect-elements ->
  options-window -> run-command -> transaction flow for ONE category, shared
  by `AutoStructuralDimension.pushbutton`, `SlabDimension.pushbutton`, and
  `SmartDimension.pushbutton`'s Structural/Slab choices, so all three stay in
  sync. Clicking "Structural Dimensions" now shows a category picker first
  (`forms.CommandSwitchWindow`: Column / Beam / Footing / Slab) - the options
  window that follows only ever lists types from that ONE category, so
  "200 x 300mm" can no longer be ambiguous.
- `structural_type_reader.py` narrowed to `list_structural_elements_by_category(doc, view, category)`
  (replacing the old all-categories-mixed-together function) + a reusable
  `types_from_elements()` helper.
- `StructuralDimensionOptionsWindow`/`show_structural_dimension_options()`
  gained an optional `category_label` - when given, the window's title,
  subtitle, and type-list helper text all say which category is being
  dimensioned (e.g. "Structural Element Dimensions - Beam"), not just an
  implicitly-filtered list with no explicit confirmation.

### Removed
- `list_structural_elements_in_view()`/`list_structural_types_in_view()`
  (all-categories-mixed versions) - genuinely dead code once every consumer
  moved to the category-scoped path.

### Verified live (real project, all rolled back)
- `list_structural_elements_by_category()` confirmed to return ONLY the
  requested category's elements (Column -> 68 elements, all category name
  "Structural Columns"; Beam -> 19, all "Structural Framing"; Footing -> 0 in
  this particular view, correctly empty rather than erroring).
- Constructed `StructuralDimensionOptionsWindow` directly (without showing the
  modal, to avoid blocking automated testing) with `category_label="Beam"` and
  confirmed the title, subtitle, and helper text all correctly say "Beam," and
  the type list contains exactly the one real beam type in the view
  ("200 x 300mm") - no other categories' types mixed in.
- 147 unit tests total (no change - this is Revit-import-only UI/adapter code,
  consistent with the rest of the suite).

## Smart Dimension becomes a picker; Beams + Slab Dimensions added

Product owner: Smart Dimension should show a CHOICE (Wall/Grids/Structural/
future tools) when clicked, not silently auto-pick based on discipline. Also:
add beam dimensioning to Structural Dimensions ("dimensions between beams...
taking in their widths... going from beam to beam"), and a new Slab Dimensions
tool. Asked for Slab Dimensions to be BOTH grid-referenced per-axis AND
perimeter-style - resolved by reusing the existing "Grid + Column" mode
unchanged (detail + overall per axis), which for a rectangular slab covers all
4 sides referenced to grids where available; disclosed that an irregular
slab's true outline is still approximated by its bounding box, not traced
edge by edge (a larger feature not attempted here).

### Added
- **Smart Dimension redesigned as a picker**: `forms.CommandSwitchWindow.show()`
  presents "Walls & Openings" / "Grid Dimensions" / "Structural Elements" /
  "Slab Dimensions" as explicit choices (with the detected view Discipline
  shown as a hint in the message, not a silent auto-pick). Whichever is chosen
  runs that tool's own options window and command exactly as if its own
  button had been clicked. Adding a future dimensioning tool needs one new
  entry in `CHOICES` plus a `_run_<x>()` function - no other wiring.
- **Beams** added to Structural Elements: `structural_type_reader.STRUCTURAL_CATEGORIES`
  gained `OST_StructuralFraming`; `RevitSelectionReader` classifies them as
  "Beam". Zero new domain logic - `column_grid_planner.plan_structural_dimensions()`
  is already generic over any element with a resolvable axis-aligned bounding
  box, so beams just become another type in the existing type filter and both
  existing modes (edge-grid-edge / continuous strip) apply unchanged.
- **Slab Dimensions** (`SlabDimension.pushbutton`, new): `revit/adapter/slab_type_reader.py`
  (Floor isn't a FamilyInstance, so type lookup goes through `GetTypeId()`
  instead of `.Symbol`); `ui/views/SlabDimensionOptions.xaml`/`.py` (same
  fields as Structural Dimensions' options window - style, offset, gap, mode,
  type filter); reuses `auto_structural_dimension_command`/`column_grid_planner`
  completely unchanged, just fed Floor elements instead of columns.
  `RevitSelectionReader` extended to classify `OST_Floors` as "Slab".

### Fixed (found via live testing before shipping)
- **A degenerate (near-zero-length) dimension plan crashed the ENTIRE run**,
  not just that one plan - `DimensionWriter.write()` built the dimension's
  `Line` object BEFORE entering its own try/except, so Revit's "Curve length
  is too small for Revit's tolerance" exception propagated uncaught out of
  the whole command. Hit live on a real slab. Fixed by moving line
  construction inside the try block, alongside `NewDimension` itself - this is
  a general robustness fix benefiting all four dimensioning tools, not just
  Slab Dimensions, since any of them could in principle hit a degenerate span.

### Verified live (real project, all transactions rolled back)
- `RevitReferenceProvider.faces_for()` confirmed working on real beam geometry:
  one real beam measured 200mm width x 10975mm length across its two axes.
  Continuous-strip mode on 19 real beams produced dimension strings correctly
  alternating gap/200mm-width/gap - exactly "beam to beam, taking in their
  widths."
  `faces_for()` also confirmed working on real Floor (slab) geometry (a
  21700mm x 11800mm slab measured correctly on both axes).
  Full Slab Dimensions pipeline (Grid + Column mode) against 9 real slabs:
  33 dimensions created, 1 degenerate plan skipped cleanly (post-fix) instead
  of crashing the run. All views' dimension counts returned to their exact
  pre-existing values after rollback. 147 unit tests total (no new tests
  needed - beams/slabs reuse already-tested generic domain logic; the new
  UI/adapter code is Revit-import-only, consistent with the rest of the suite).

## Smart Dimension replaces Auto Dimension; output window silenced

### Added
- **Smart Dimension** (`SmartDimension.pushbutton`, replaces the original
  `AutoDimension.pushbutton`): reads the current view's `Discipline` property
  (Revit's own Architectural/Structural/... setting) and routes entirely to
  whichever existing, already-tested pipeline matches - `auto_structural_dimension_command`
  for a Structural-discipline view, `auto_wall_opening_dimension_command` for
  everything else. Not a third dimensioning algorithm: it's a router that
  shows the SAME options window (Structural Dimensions' or Wall & Openings',
  whichever applies) and produces the SAME result as running that tool
  directly - "smart" means picking the right existing tool automatically, not
  reinventing one.
- `revit/adapter/wall_context_builder.py:build_walls_with_context()` -
  extracted from `AutoWallOpeningDimension.pushbutton`'s script.py once Smart
  Dimension became a second consumer of the identical wall-context-building
  logic (ADR-0002: shared helper once a 2nd consumer exists). Pure refactor -
  behavior unchanged, re-verified live to confirm it still produces identical
  output after extraction.

### Removed
- The original `AutoDimension.pushbutton` (box-select, one dimension per
  element per axis against the nearest grid) is retired - `auto_dimension_command.py`
  and its tests deleted, now genuinely dead code. `planner.py:plan_element_axis`
  is KEPT - it's still a live dependency of `column_grid_planner.py`'s
  per-column detail dimensions in Structural Dimensions.

### Fixed
- pyRevit's Output window was popping up on every single dimensioning run,
  duplicating information already shown in the `forms.alert()` result popup -
  "I have to go close them every time." Root cause: `bkbim.core.logging`'s
  `ConsoleSink` printed every log line to stdout, which pyRevit auto-opens an
  Output window for. Fixed by making the logger silent by default (no sinks
  registered) - `ConsoleSink` still exists and can be re-enabled for live
  debugging via `logging.configure(sinks=[ConsoleSink()])`, it's just no
  longer wired in automatically.

### Verified live (real project, all transactions rolled back)
- `view.Discipline` correctly read as `Structural` for
  `L0 - FOUNDATION COLUMNS SETTING OUT` and `Architectural` for
  `AR-19 - GROUND FLOOR GENERAL ARRANGEMENT PLAN`.
- Ran both of Smart Dimension's underlying branches directly against those two
  real views: Structural branch created 107 dimensions (16 already existing,
  13 skipped); Architectural branch created 86 (0 already existing, 8
  skipped) - both views' dimension counts returned to their exact
  pre-existing values (22 and 0 respectively) after rollback.
- Confirmed `build_walls_with_context()` produces identical output
  post-extraction (49 walls with context on the same real view).
- Confirmed a logger call produces zero console output post-fix.
- 147 unit tests total (8 removed with `auto_dimension_command.py`).

## Ribbon reorganized into proper panels + minimal icons for every button

Product owner: arrange the ribbon into categorized panels like pyRevit's own
tabs, with minimal icons (Lucide/Tabler/Icons8), then suggest what to build
next. All 6 tools had been sitting under one catch-all "Documentation" panel
since Phase 0 - never revisited even as the tool count grew to 6.

### Changed
- New **Dimensioning** panel: `AutoDimension`, `AutoGridDimension`,
  `AutoWallOpeningDimension`, `AutoStructuralDimension` - the four dimension
  tools, grouped together.
- `WallLegend` moved into the (previously empty) **Modeling** panel - it's a
  modeling helper, not a dimensioning tool.
- `CountSelected` moved into the (previously empty) **Utilities** panel - a
  diagnostic tool, not dimensioning.
- `Documentation.panel` removed (empty after the moves above). Tab-level
  `bundle.yaml` layout updated to list `Dimensioning` in its place; `Modeling`/
  `Utilities` panel `bundle.yaml`s updated with explicit button layout order.
  `QAQC`/`AI`/`Settings` stay as reserved empty panels (pyRevit hides a panel
  with no buttons) for when their first tool lands.

### Added
- Minimal single-color line icons for all 5 previously-iconless buttons (96x96
  transparent PNG, matching the existing `WallLegend`/`About` icons' format):
  `AutoDimension` (ruler, Lucide), `AutoGridDimension` (grid, Lucide),
  `AutoWallOpeningDimension` (wall, Tabler), `AutoStructuralDimension` (dot
  grid - columns at grid intersections, Tabler), `CountSelected`
  (checklist, Lucide). Sourced from Lucide (ISC license) and Tabler Icons (MIT
  license) via their public CDN-hosted static SVG packages, recolored to
  solid black and rendered to transparent PNG locally (no design tool needed).

### Notes
- SVG-to-PNG conversion needed a real fix, not just a library choice: the
  installed rendering backend (`svglib` + `reportlab`'s `rlPyCairo`) ignores
  alpha on `fillColor` (a `fill="none"` shape rendered as opaque black instead
  of transparent) - worked around by rendering each icon twice (once on a
  white background, once on black) and computing per-pixel alpha from the
  difference between the two, which is unaffected by that backend quirk since
  unfilled shapes are forced to literally match whichever background is
  active in each pass before the difference is taken.
- No pyRevit reload was performed as part of this change (bundle files were
  edited on disk while Revit was running) - a pyRevit reload or Revit restart
  is needed before the new panel layout and icons appear.

Product owner tried the fix below in Revit: "it's not working." Rather than
keep debugging a feature that isn't earning its complexity, reverted cleanly:
`domain/dimensioning/collision.py` deleted, `plan_structural_dimensions()`
restored to calling `_plan_individual_column_dimensions`/
`_plan_continuous_row_chains` directly again, with no post-processing pass.
155 unit tests (the 11 collision-specific tests removed with the module).

`Standard.collision_shift_mm`/`collision_max_passes` are left in place (they
predate this attempt, from the original Phase 0/1 skeleton) but remain unused
- still available as a starting point if collision avoidance is revisited with
a different approach later (e.g. one that accounts for the view's actual scale
and the dimension style's real text size, rather than a fixed model-space
shift, which is the likely reason 300mm wasn't visually enough at 1:82 scale
even once the detection bug itself was fixed).

## Collision avoidance: overlapping dimensions now auto-detected and pushed apart (reverted, see above)

Product owner, screenshot of a small column at 1:82 scale: two dimensions'
"0.10"/"0.10" and "0.20" text overlapping each other - "can you make it to
where it auto detects overlaps and pulls it out?"

### Added
- `domain/dimensioning/collision.py:resolve_collisions(plans, standard)` - pure,
  generic (not scoped to columns): any two `DimensionPlan`s sharing an `axis`
  with overlapping `[line_coord_lo, line_coord_hi]` ranges get pushed at least
  `collision_shift_mm` apart (in the outward direction implied by
  `default_side`), repeated up to `collision_max_passes` times. Both fields were
  reserved on `Standard` back in Phase 0/1 for exactly this and never wired up
  until now (see ROADMAP's "explicitly deferred" list) - built once a concrete
  case demanded it, not guessed at up front.
- Wired into `column_grid_planner.plan_structural_dimensions()` - every mode's
  output goes through it before being returned. Written generically so the
  other three dimensioning tools could adopt it later without changes to this
  module.

### Fixed (caught via live testing against the real project, before shipping)
- **First implementation only compared NEIGHBORING plans in a perp_pos-sorted
  list** - missed real collisions where an unrelated, non-overlapping plan's
  perp_pos happened to numerically fall between two plans that DO overlap.
  Confirmed live: two different columns' dimensions sat only 100mm apart (well
  under the 300mm `collision_shift_mm` default) and were never even compared.
  Fixed by checking every same-axis pair directly (not just sorted neighbors) -
  trivial cost at real-world plan counts (up to a few hundred). Always pushes
  whichever of a colliding pair sits further from what it measures even
  further out (never pulls the nearer one in), so perp_pos only moves in one
  direction across passes - guaranteed to converge, never oscillate.

### Verified live (real project, all transactions rolled back)
- Reproduced the exact reported scenario in the exact view from the screenshot
  (`L0 - FOUNDATION COLUMNS SETTING OUT`, 1:82 scale): before the fix, the
  worst-case same-axis overlapping gap between two real dimensions was 100mm;
  after, exactly 300mm (the configured `collision_shift_mm`) - confirmed via a
  full worst-case-gap scan across all generated plans, not just the one pair
  spotted in the screenshot.
  In this view, some columns' resolved reference sets were rejected by
  `NewDimension` ("Invalid number of references") - unrelated to collision
  resolution (which only ever changes `perp_pos`, never `refs`); this was
  disclosed to the product owner as a separate, pre-existing edge case worth a
  dedicated look, not silently fixed or hidden.
  Dimension count in the view returned to its exact pre-existing value (22)
  after rollback. 166 unit tests total (11 new for collision resolution,
  including a regression test for the neighbor-only bug).

## Structural Dimensions: "overall" corrected to be per-column, not per-row

### Fixed
- The overall dimension in "Grid + Column" mode (added in the previous fix,
  below) spanned first-to-last column across an entire row - product owner:
  "I don't want it to be from the first column on the grid to the last column,
  I want overall dimension on individual columns just like the column from face
  to grid to face." Fixed: the overall is now scoped to ONE column, same as the
  detail dimension it sits alongside - that column's own two faces, no grid
  reference, placed further out (offset + gap) than the detail dimension. This
  removed the need for row-grouping in this mode entirely - `group_columns_by_row`
  is now used only by "Continuous strip" mode, which was and remains unaffected.
  Every column now gets exactly 2 dimensions per resolvable axis: a detail (face
  -> grid -> face, or plain face-to-face if no grid is nearby) and an overall
  (that same column's own two faces).

### Verified live (real project, rolled back)
- Same 64-element view (34 columns + 30 footings): 256 dimensions created -
  exactly the theoretical maximum (64 elements x 2 axes x 2 dimensions each),
  confirming every element resolved on both axes with nothing silently skipped.
  Every dimension still carries at most 3 references (2 for every overall, 2-3
  for every detail depending on whether a grid was found nearby) - confirms
  nothing spans more than one column anywhere. Dimension count in the view
  returned to its exact pre-existing value (8) after rollback. 155 unit tests
  total (planner + app command tests rewritten again for the corrected scope).

## Structural Dimensions: Grid+Column mode corrected; drag-to-multiselect everywhere

### Fixed (product owner tried the new tool same day, caught immediately)
- **"Grid + Column" mode was chaining every column in a row into ONE continuous
  string** (column-edge -> grid -> column-edge -> grid -> ... across the whole
  row) - wrong. The actual ask: "dimension individual columns on both sides
  (length and width) then measure from one face to grid then finish at the
  opposite face and stop there and not continue as a string to other columns."
  Fixed by dropping the custom chain-building logic entirely and reusing,
  unchanged, the original Auto Dimension tool's own per-element classification
  (`planner.py:plan_element_axis`) - now called once per column per axis,
  producing an isolated dimension (near face -> grid -> far face) that never
  touches another column's references. The separate overall string per row
  (first column's outer face -> last column's outer face) was confirmed correct
  and left as-is. "Continuous strip" mode was confirmed working and untouched.
- `Standard.offset_first_mm` (read by the reused `plan_element_axis`) is now
  kept in sync with `structural_chain_offset_mm` by the pushbutton, so the
  single offset slider in the options window drives both the individual
  per-column dimensions and the overall string consistently.
- `DimensionPlan.KIND_COLUMN_GRID_CHAIN` removed (no longer produced by
  anything - individual per-column dimensions now carry `plan_element_axis`'s
  own kinds: `KIND_OVERALL`/`KIND_SNAP_ON_EDGE`/`KIND_INSIDE_CHAIN`/
  `KIND_OUTSIDE_CHAIN`).

### Added
- `ui/views/listbox_drag_select.py:enable_drag_multiselect()` - click-and-drag
  multi-select for any `SelectionMode="Extended"` ListBox, layered on top of
  (not replacing) the existing click/Ctrl+click/Shift+click behavior: a plain
  click still falls through to WPF's own default handling; only once the
  cursor moves past a small threshold while the button stays held does it start
  selecting every item the cursor passes over (product owner: "make it possible
  to just drag a selection box and select multiple instead of using Ctrl" -
  applies to every type-filter list in the suite, not just this one). Wired into
  both `WallOpeningDimensionOptions`' wall-type list and
  `StructuralDimensionOptions`' structural-type list.

### Verified live (real project, all transactions rolled back)
- Corrected Grid+Column mode against the same 34-column/30-footing/18-grid
  view: 144 dimensions created (128 individual + 16 overalls), 0 errors. Every
  created dimension has at most 3 references - confirmed nothing is chained
  across columns anymore (previously, the buggy version produced dimensions
  with up to 42 references). Dimension count in the view returned to its exact
  pre-existing value (8) after rollback.
- `listbox_drag_select.py` and both updated options modules confirmed to import
  cleanly under the real IronPython 2.7 engine (the interactive drag gesture
  itself needs a live mouse in a modal dialog, which isn't reachable through
  this testing channel - flagged to the product owner to try directly).
- 155 unit tests total (planner + app command tests rewritten for the
  corrected per-column behavior).

## Auto Dimension for Structural Elements (columns, footings) - new tool

Product owner: auto-dimension structural columns/footings in plan, with two modes
used in different situations - "sometimes I want column edge to grid to column
edge, and an overall dimension... in other cases I measure from column to column
attached on a grid in a continuous dimension strip without referencing the
grids." Checked published structural-drafting conventions before designing
(gridlines conventionally align to column centerlines; continuous dimension
strings from column faces/centerlines to grid lines is documented standard
practice - see [Eng-Tips](https://www.eng-tips.com/threads/standards-for-gridline-layout-and-dimensioning-on-structural-drawings.430738/),
[ARCHLOGBOOK](https://docs.archlogbook.co/01-industry-basics/plan-annotations),
[Rafn](https://www.rafn.com/2022/12/2022q4-dimensioning02/)).

### Added
- `DimensionPlan.KIND_COLUMN_GRID_CHAIN` / `KIND_COLUMN_ROW_CHAIN` /
  `KIND_COLUMN_OVERALL`; `Standard.structural_chain_offset_mm`/`gap_mm` (kept
  independent of Grid Dimensions' own offset/gap fields, so tuning one tool never
  silently changes the other).
- `domain/dimensioning/column_grid_planner.py` (pure, 17 unit tests): groups
  columns/footings into "rows" by proximity to a grid line (same grouping
  mechanism for BOTH modes) - `MODE_GRID_AND_COLUMN` alternates each column's
  near/far face with its own nearest CROSSING grid across the whole row (reusing
  the on-edge/inside/outside-of-span classification `planner.py:plan_element_axis`
  already established, scoped down to merge many columns' segments into one
  chain instead of one dimension per column), plus a separate overall string
  further out (first column's outer face -> last column's outer face) - same
  near-string + overall-further-out convention Grid Dimensions uses.
  `MODE_CONTINUOUS_NO_GRID` uses the identical row grouping but emits only column
  faces, never a grid reference, and adds no overall string (the chain's own
  span already is one).
- `revit/adapter/structural_type_reader.py` - lists Structural Columns,
  Architectural Columns, and Structural Foundations present in a view, for a
  type multi-select filter (mirrors `wall_type_reader.py`).
- `revit/adapter/selection_reader.py` extended to also recognize
  `OST_StructuralFoundation` (labeled "Footing"), alongside its existing
  Wall/Column handling - same nested-instance skip applied.
- `app/commands/auto_structural_dimension_command.py` (zero Revit imports, 10
  fake-based tests) + `ui/views/StructuralDimensionOptions.xaml` (style, offset,
  gap, mode radio, type multi-select) + `AutoStructuralDimension.pushbutton`
  (auto-detect grids + structural elements from the current view, no selection
  needed).
- **No new adapter-level geometry code was needed for column face references** -
  `RevitReferenceProvider.faces_for()` already worked for FamilyInstance columns
  since Phase 1 Stage 4 (the symbol->instance-ref conversion technique,
  validated back then against a real 200mm structural column) and needed zero
  changes here.

### Verified live (real project, both transactions rolled back)
- Real view with 34 structural columns + 30 isolated pad footings + 18 grids
  (wall/strip footings correctly excluded - they're `WallFoundation` elements,
  not `FamilyInstance`, and don't belong in a column-grid row anyway).
- `MODE_CONTINUOUS_NO_GRID`: 16 dimensions created, 0 skipped, 0 errors - no grid
  reference in any of them.
- `MODE_GRID_AND_COLUMN`: 32 dimensions created (16 rows x chain+overall), 0
  skipped, 0 errors - overall dimensions read 21700mm/12950mm/3150mm (plausible
  real bay spans), each with exactly 2 references (first-to-last outer face);
  chain dimensions carried up to 42 references for the busiest row.
- Confirmed the view's dimension count returned to its exact pre-existing value
  (8) after both rollbacks - zero residue.

## Parts-based Core mode reverted - product owner chose the layer-modeling path instead

After the Parts-based Core mode below shipped and was live-verified, the product
owner also asked (separately) whether core-face referencing was possible
**without** creating Parts, since Revit's own Tab-to-select-core-face works
interactively with no Parts involved. Investigated live: found that Revit does
track the exact core-boundary coordinates internally (degenerate marker solids
sit precisely at the arithmetic core-layer boundary), but every face and edge on
that marker geometry has `Reference = None` - not usable for `NewDimension` via
the public API. Also found a genuine `Line` reference at the core centerline, but
it's a centerline (and for a symmetric wall, indistinguishable from the overall
wall centerline), not a face - not what's needed for real clear-opening/structural
dimensioning. Re-confirmed `HostObjectUtils.GetSideFaces`'s `ShellLayerType` truly
only has Interior/Exterior. Conclusion: Revit's interactive Tab-pick uses internal
hit-testing not exposed through the public geometry API; Parts remain the only
API-accessible mechanism found for a real core-face `Reference`.

Given that, the product owner decided to switch to the **per-layer wall modeling
convention** (blockwork/plaster/tile as separate wall elements) instead of
requiring per-wall "Create Parts" as a prerequisite - this is the same convention
the wall-type filter (see "Split-at-crossing dimensions; wall-type filter" below)
was already built for, so no new mechanism is needed to support it.

**Removed:**
- `revit/adapter/wall_core_resolver.py` deleted.
- `WallOpeningDimensionOptions.xaml`/`.py`: the "Reference from" Core/Finish radio
  choice removed; window restored to its pre-Core-mode size and row layout.
- `AutoWallOpeningDimension.pushbutton/script.py`: restored to its pre-Core-mode
  state (no resolution step, no Parts-related skip/report messaging).

128 unit tests still pass after the revert (none depended on the removed
adapter, consistent with other Revit-import adapters never being unit-tested
under plain CPython).

## Core vs finish wall-face referencing - resolved via Revit Parts (superseded, see above - reverted 2026-07-06)

Product owner pushed back a third time on the earlier "investigated, not shipped"
conclusion below, citing their own Revit temporary dimensions as concrete proof that
referencing a wall's core faces is achievable ("like in the temporary dimensions, i
have it going from the faces of core"). That evidence was taken seriously rather
than dismissed, leading to a deeper investigation that found the real mechanism.

### Investigated (via reflection + live experiments, all rolled back)
- Re-confirmed a compound wall's own fused solid geometry never exposes a face at
  an internal core/finish boundary (re-scanned both axes, tried
  `Options.IncludeNonVisibleObjects = True`, checked materials) - the original
  conclusion about the wall's OWN geometry was correct as far as it went.
- Reflected across `Wall`, `HostObjectUtils` (`GetSideFaces` only distinguishes
  Interior/Exterior, no Core option), `DimensionReferenceOptions` (dead end - no
  public constructors/properties), and a broad search of every loaded Revit
  assembly for a Wall+Core/Centerline type - nothing dedicated exists.
- Checked all 335 real dimensions in the actual project; the 127 referencing real
  walls all use `ElementReferenceType.REFERENCE_TYPE_SURFACE`, same as this code
  produces - no special reference type is in play.
- **Root cause found**: Revit's native **Parts** feature
  (`PartUtils.CreateParts`) splits a compound wall into one independent element
  per layer, each with its own genuine, referenceable `Solid` geometry landing
  exactly on the layer's arithmetic boundary. This is almost certainly what
  Revit's own temporary dimensions use for "core face" behavior.

### Added
- `revit/adapter/wall_core_resolver.py:resolve_dimension_source(doc, wall, mode)` -
  "finish" mode returns the wall itself (unchanged behavior); "core" mode finds the
  wall's core-layer Part (via `PartUtils.HasAssociatedParts`/`GetAssociatedParts`
  matched against `CompoundStructure`'s core layer material ids), or `None` if the
  wall has no Parts yet. Deliberately does **not** create Parts on the user's
  behalf - that's a persistent, visible modeling decision (affects
  schedules/quantities) left to the user's own "Create Parts" action, not a side
  effect of clicking a dimension button.
- Resolution is wired in at the pushbutton (adapter) layer, not the app command:
  `wall_core_resolver.py` imports `PartUtils`, so per ADR-0001 (zero Revit imports
  below the adapter layer) it can't live in `auto_wall_opening_dimension_command.py`.
  The app command itself needed no changes - it already treats `wall_ref` as an
  opaque handle, so resolving it to a Part before building `walls_with_context`
  was enough. Both the MAIN wall's own end/opening faces and each CROSSING wall's
  thickness faces are resolved through the same function, so a crossing wall also
  breaks at its own core face in "core" mode.
- `WallOpeningDimensionOptions.xaml`/`.py`: a "Reference from" Core/Finish radio
  choice, defaulting to Finish (unchanged behavior). Walls with no Parts in Core
  mode are skipped and reported by count in the completion alert, never silently
  dimensioned from finish faces instead.

### Verified (live, real project, all transactions rolled back)
- A wall with no Parts: `resolve_dimension_source(..., "core")` correctly returns
  `None`.
- Same wall after `PartUtils.CreateParts`: resolves to its actual core Part.
- `wall_run_faces()` on the resolved core Part (same function used for whole
  walls, unchanged): wall span read as 4950mm (core-to-core) vs. 4900mm
  finish-to-finish on the same wall, and its hosted door's opening span read as
  exactly 1200mm - matching the door's own `Width` parameter exactly.
- `faces_for()` on the resolved core Part (the function used to resolve a
  CROSSING wall's thickness faces): 200mm core thickness vs. 250mm finish-to-finish
  on the same wall - confirms a crossing break also lands on the core face in
  Core mode.

## Wall & Opening Dimension: style + spacing options

### Added
- `WallOpeningDimensionOptions.xaml` + `wall_opening_dimension_options.py` -
  dimension style dropdown + one offset slider/textbox, wired into
  `AutoWallOpeningDimension.pushbutton`.
- `revit/adapter/dimension_type_reader.py:list_linear_dimension_types()` - shared
  by both Grid Dimensions and Wall & Opening Dimension.

### Fixed (found via live testing before shipping)
- The dimension-style dropdown listed every `DimensionType` (Linear, Angular,
  Radial, SpotElevation, ...) with no filtering. Picking a non-linear one crashed
  every dimension creation ("The dimension type is a non-linear dimension type").
  Fixed by filtering to `DimensionStyleType.Linear` only - applied to **both**
  pushbuttons, since the bug existed identically in each.

### Investigated, not shipped (disclosed rather than guessed around)
- Product owner asked for a "core vs finish wall faces" option at wall ends.
  Investigation found this doesn't reduce to a simple geometric check: at the
  jambs already validated, a near-duplicate face turned out to be an unrelated
  threshold detail; a scan of 25 real walls for an end-cap candidate found a 75mm
  gap matching neither layer's real finish thickness, consistent with a
  T-junction artifact from an intersecting wall rather than a core/finish
  difference. Root cause: compound-structure layers are a thickness-direction
  concept, while finish-vs-core extension at a wall's end depends on wall-join
  resolution, an unrelated and harder problem. Deferred pending dedicated
  investigation rather than shipped as an unreliable toggle.

### Verified
- Live end-to-end: 5 dimensions created using a deliberately non-default linear
  style and a non-default 1500mm offset, 0 errors, cleanly rolled back. 37 of the
  project's dimension types confirmed Linear-usable.

## Crossing-wall breaking; core-referencing investigated further

### Added
- `domain/dimensioning/crossing_wall_detector.py:find_crossing_walls()` - pure
  perpendicular-crossing detection with dedup for near-coincident duplicate
  crossings. 11 new unit tests. Wired into `auto_wall_opening_dimension_command.py`
  and the pushbutton entry point (builds `ElementInfo` for every wall in the view
  and passes candidates per main wall). No new adapter method needed - reuses the
  already-validated `faces_for()`.

### Fixed (found via live testing against the real crossing case)
- A partition crossing a wall can be modeled as two separate wall elements (one on
  each side), both independently detected as "crossing" with coordinates differing
  only in the ~10th decimal place - would have fed near-duplicate references into
  the same dimension. Fixed with a dedup pass in `find_crossing_walls` (~3mm
  tolerance).
- A crossing wall's own face can coincide almost exactly with the *main* wall's own
  end face (a T-junction near a corner) - produced two spurious ~0mm segments.
  Fixed with a general coincident-point dedup pass in `plan_wall_run` itself (one
  place covering every break source, not a special case per pairwise scenario).

### Investigated, not shippable (confirmed, not just deferred)
- "Take all dimensions from the core" - checked `HostObjectUtils.GetSideFaces`
  (Interior/Exterior only) + `CompoundStructure` layer widths; this computes the
  core boundary's coordinate correctly (validated against the Structure layer's
  declared 200mm width), but Revit dimensions need a real geometric `Reference`,
  and the core/finish layer seam is bonded internally in these wall solids - no
  exposed face exists there to reference (confirmed on a second, independent wall).
  This is a hard limitation of Revit's fused compound-wall geometry, not something
  more investigation alone resolves - stays out of scope.

### Verified
- Live end-to-end against the exact real wall where both duplicate-reference bugs
  were found: clean 8-ref/7-segment result,
  `[250, 1500, 250, 2300, 250, 950, 250]`mm summing to the wall's real 5750mm
  length, the two 250mm segments matching the two real crossing walls' own
  thickness. 117 unit tests total.

## Split-at-crossing dimensions; wall-type filter (core/finish, take 2)

Product owner feedback after trying crossing-wall breaking: don't show the
crossing wall's thickness as a segment - split into separate dimensions instead.
Also revealed the real path to core-vs-finish control: a modeling convention with
each wall layer as its own separate element, which sidesteps the "core has no
exposed face" limitation entirely.

### Changed
- `wall_run_planner.py`: `plan_wall_run` -> `plan_wall_runs`, now returns
  `list[DimensionPlan]` (one per contiguous run between crossings) instead of one
  chain. A crossing wall's own thickness is never part of any chain. 11 rewritten
  unit tests.
- `auto_wall_opening_dimension_command.py` writes every plan per wall (N crossings
  -> N+1 dimensions).

### Added
- `revit/adapter/wall_type_reader.py:list_wall_types_in_view()` +  wall-type
  multi-select `ListBox` in `WallOpeningDimensionOptions.xaml` (default: all
  selected). Non-selected wall types are excluded entirely, including as crossing
  candidates - this is how "dimension from the core" is achieved once wall layers
  are modeled as separate elements, since it needs no core/finish face detection
  at all - just a type filter.

### Fixed (found live while building the wall-type lister)
- `OST_Walls` can include non-`Wall` elements (a `FamilyInstance`, likely a
  curtain panel, raised `AttributeError` on `.WallType`). Fixed with an explicit
  `isinstance(w, Wall)` guard in the lister and the main pushbutton's wall
  collection (2 of 59 raw elements in the test view were non-Wall).

### Verified
- Split behavior: the real wall with 2 crossings now produces 3 separate
  dimensions (1500/2300/950mm), no crossing-thickness segment, cleanly rolled
  back.
- Wall-type filter: 57 real walls correctly narrowed to 12 when filtered to one
  type; this view already has a wall type named "0.025 PLASTER," confirming the
  product owner has begun the layer-separated modeling this feature supports.
- 120 unit tests total.

## Skip already-placed dimensions - safe to re-run

Product owner: skip a location that's already dimensioned instead of redoing
everything, so re-running is safe to use as an "update." Real gap: none of the
three dimensioning tools checked for existing dimensions before creating new
ones.

### Added
- `domain/dimensioning/ports.py:IExistingDimensionChecker` +
  `revit/adapter/existing_dimension_checker.py:RevitExistingDimensionChecker` -
  one shared mechanism, reused by all three app commands. Matches a planned
  dimension's two endpoint references against existing dimensions' references via
  stable-representation keys (`stable_representation.py:reference_stable_key`).
  Matches on endpoints only (not full internal content), matching what was asked:
  skip if placed, don't try to detect content changes.
- All three app commands gained a third result counter, `already_existing`,
  alongside `created`/`skipped` - the completion alert now shows exactly what an
  "update" run did.
- A checker exception fails open (dimension still gets created normally), not
  closed.

### Design decision
- No separate "Update Dimensions" button. Skip-if-existing is now the default
  everywhere, so the three existing buttons already function as the requested
  update workflow - a new button would do the same thing.

### Verified
- Ran the real wall/opening command twice in a row against the same real wall:
  first run created 3 dimensions; second run reported 0 created / 3 already
  existing, with the dimension count in the view unchanged (3, not 6). Cleanly
  rolled back. 128 unit tests total.

## Unreleased — Phase 1 groundwork (Stages 1-2)

### Added
- `docs/architecture/PHASE_1_PLAN.md` - Auto Dimension built from first principles,
  not ported from v5 (see ADR-0002 correction below).
- `domain/geometry/units.py`, `domain/models/element_info.py` (`ElementInfo`),
  `domain/models/grid_info.py` (`GridInfo`), `domain/standards/standard.py`
  (`Standard` profile). 14 new unit tests (38 total).

### Fixed (found via live smoke test against Revit 2026, same day)
- `"{:.1f}".format(x)` raised `ValueError: Precision not allowed in integer format
  specifier` under IronPython 2.7 when `x` is a plain `int` (CPython silently casts;
  IronPython 2.7 does not). Fixed with explicit `float(...)` casts in
  `ElementInfo.__repr__` / `GridInfo.__repr__`; regression tests added.

### Corrected
- **ADR-0002**: product owner confirmed v5 fails across all axes ("start from
  scratch"); no dedicated test project available, so Phase 1 correctness is judged
  by professional judgment + incremental live testing, not a fixture file.

### Added (Stage 3 - dimension planner)
- `domain/models/dimension_plan.py` (`DimensionPlan`), `domain/models/axis_faces.py`
  (`AxisFaces`), `domain/dimensioning/planner.py` (`plan_element_axis`). Deliberately
  simple per product owner direction: fixed default side, no collision avoidance, no
  multi-row overalls. 18 new unit tests (56 total), all passing under both CPython
  and the live IronPython 2.7 engine.
- `Standard.default_side` field added (replaces v5's per-element side-picking
  heuristic with one fixed, configurable value).

### Added (Stage 4 - reference provider)
- `domain/references/ports.py` (`IReferenceProvider`),
  `revit/adapter/reference_provider.py` (`RevitReferenceProvider`),
  `revit/adapter/stable_representation.py` (pure symbol->instance-ref string helper,
  deliberately kept Revit-import-free so it's genuinely unit-testable). 5 new tests
  (61 total).
- **Live-verified against the real open project** (not just import checks): created
  and rolled back real dimensions from both a wall (250mm, solid-face path) and a
  structural column (200mm, family-instance symbol->instance-ref path) inside a
  transaction. Confirms the hardest Revit API technique in this codebase actually
  works on this model, not merely that it runs without raising.

### Fixed (found while wiring up Stage 4)
- `reference_provider.py` originally defined `rewrite_stable_representation_element_id`
  inline, but the file does `clr.AddReference(...)` at module scope - meaning the
  function was unreachable (and untestable) under plain CPython despite being pure
  string logic. Extracted into `stable_representation.py`, which has zero Revit
  imports, before any test relying on the false "pure" claim shipped.

### Added (Stage 5 - dimension writer + failure policy)
- `revit/adapter/dimension_writer.py` (`DimensionWriter`), `revit/adapter/failure_policy.py`
  (`ScopedFailurePolicy` - deletes only elements explicitly registered as created by
  this command, fixing v5's blanket-delete-on-any-error behavior). Verified live:
  200mm dimension created and rolled back cleanly, zero errors/warnings from the
  policy.

### Incident (disclosed in full)
- A live-verification test for Stage 5 called `t.Commit()` instead of `t.RollBack()`,
  creating a real, permanent 200mm dimension in the product owner's actual project
  file. Caught immediately, confirmed unambiguous identity (only dimension in the
  view, exact matching value), deleted it, and verified zero dimensions remained.
  Process fix: every exploratory live-Revit test now uses `RollBack()`, no
  exceptions.

## Phase 1 Stages 6-7 - Auto Dimension is real and working

### Added
- `domain/dimensioning/ports.py` (`ISelectionReader`, `IDimensionWriter`,
  `IFailureTracker`); `revit/adapter/selection_reader.py` (`RevitSelectionReader`);
  `app/commands/auto_dimension_command.py` (zero Revit imports, 6 new unit tests,
  67 total); `Documentation.panel/AutoDimension.pushbutton` - a real, working ribbon
  button.
- Shipped UI at Tier 1 (box-select + alert) rather than the originally-planned
  Tier 2 WPF options panel - deliberate, to validate the engine before investing in
  UI polish. See ROADMAP.md for the full reasoning.

### Verified
- Stage 7: ran the full command against a real bounded selection (4 real grids, 5
  real walls, 3 real columns) from the product owner's actual project, inside a
  rolled-back transaction. Result: 16 dimensions created, 0 skipped, 0 errors, 0
  warnings, every value inspected and architecturally sensible. Cleanly rolled back,
  verified zero dimensions remained.
- **Phase 1 (all 7 stages) is complete.**

## Grid Dimensions feature - same-day follow-up

### Added
- `DimensionPlan.KIND_GRID_SEQUENTIAL`/`KIND_GRID_OVERALL`;
  `domain/dimensioning/grid_chain_planner.py` (`plan_grid_chains`,
  `compute_bounding_span`); `DimensionWriter` now accepts an optional
  `dimension_type`; `revit/adapter/element_naming.py` (`type_name`, a shared,
  more-robust type-name resolver); `app/commands/auto_grid_dimension_command.py`;
  first real WPF window (`ui/views/GridDimensionOptions.xaml` +
  `grid_dimension_options.py` - dimension style dropdown, slider+textbox spacing
  controls); `AutoGridDimension.pushbutton`. 6 new unit tests (88 total).

### Fixed (found before shipping)
- `plan_grid_chains` originally used one perpendicular span for both grid
  orientations - wrong on any non-square building, since vertical grids need the
  Y-extent and horizontal grids need the X-extent. Fixed to accept `x_span`/`y_span`
  separately; added a regression test that deliberately poisons the wrong span to
  prove it's never used.
- `Element.Name.GetValue()` (previously recorded as the fix for `WallType.Name`)
  does not work reliably for `DimensionType` - inconsistent live. New
  `type_name()` helper tries `SYMBOL_NAME_PARAM` first, with the old fixes as
  fallbacks.

### Verified
- Rendered the product owner's two reference PDFs (architectural + structural) and
  confirmed the two-string, all-sides convention matched exactly what was already
  designed - no changes needed.
- Live-verified the full feature against the real project: 8 dimensions created
  (2 orientations x 2 sides x 2 strings), 0 skipped/errors, user-adjusted spacing
  (1000mm/500mm) and an explicitly chosen dimension style both applied correctly,
  values architecturally sensible. Cleanly rolled back, zero remained afterward.
- Verified the WPF options window without `ShowDialog()` (which would hang
  headlessly): XAML loads, elements bind, slider<->textbox sync both directions,
  out-of-range clamps, invalid text falls back safely.

## Grid Dimensions - usability fixes (same-day, after first real use)

Product owner tried it and reported: box-select felt like unwanted friction (wanted
grids auto-detected), and the options window "can't expand" so some content wasn't
visible.

### Fixed
- **Real layout bug, not just a missing feature**: the "Gap to overall string" row
  in `GridDimensionOptions.xaml` was pinned to a fixed 20px row height while its
  actual content (label + slider + textbox) needs ~55-60px - WPF clips content in
  fixed-height rows rather than growing them, so this row was genuinely cut off.
  Rewrote the row structure to one `Auto` row per control block with margin-based
  spacing instead of dedicated fixed-pixel spacer rows (removes the exact class of
  mismatch that caused this), plus a trailing `*` row so extra space goes below the
  content instead of stretching it oddly. Also set `ResizeMode="CanResizeWithGrip"`
  (was `NoResize`) with sane `MinWidth`/`MinHeight`, so the window can be resized at
  all - verified live: `ResizeMode`, min sizes, and the fixed row's `Auto` height
  all confirmed via direct WPF object inspection (not just visual reading of the
  XAML).
- **`AutoGridDimension.pushbutton` no longer prompts a box-select.** Grids, walls,
  and columns are now auto-detected via `FilteredElementCollector` scoped to the
  active view - click the button, options window opens immediately. Domain/app
  layers needed zero changes (`selection_reader.read()` already accepted any list of
  Revit elements regardless of how they were gathered).

### Verified
- Live end-to-end with the real fixes: auto-detected all 111 dimensionable elements
  in the active view (18 grids, 59 walls, 34 columns) with no user selection step,
  ran the full command, got 8 correctly-placed dimensions, 0 errors, cleanly rolled
  back.

## Auto Dimension for Walls and Openings

### Added
- `DimensionPlan.KIND_WALL_RUN`; `domain/dimensioning/wall_run_planner.py`
  (`plan_wall_run`); `RevitReferenceProvider.wall_run_faces()` + new
  `IWallRunReader` port; `revit/adapter/opening_reader.py`
  (`group_openings_by_host`); `app/commands/auto_wall_opening_dimension_command.py`;
  `AutoWallOpeningDimension.pushbutton` (auto-detect, Tier 1). 13 new unit tests
  (101 total).

### Investigated before writing orchestration code (a real, load-bearing finding)
- The door/window family's own geometry gives an imprecise frame/casing extent
  (~1280mm for a real door whose actual `DOOR_WIDTH` is 1200mm) - NOT the same as
  the true rough opening. The wall's OWN cut geometry gives the exact match
  instead, confirmed to the millimeter against the door's real location and width,
  and again for a 2000mm window. Jamb references for wall-run dimensioning now
  come exclusively from the wall's own geometry.
- Compound (multi-layer) walls produce near-duplicate reveal faces per opening
  (core vs. finish layer). Resolved by matching each opening to its closest
  bracketing face pair by the opening's own known location, rather than attempting
  to geometrically deduplicate layer artifacts.

### Verified
- Full dimension creation (not just face detection) against the validated
  door+window wall: 775/2000/750/1200/175mm segments, summing exactly to the
  wall's real 4900mm length, matching both openings' true widths precisely.
  Rolled back cleanly.
- Broader test against 10 real walls: 8 created, 2 skipped defensively, 0 errors -
  including a 14-reference/13-segment chain for a 6-window facade with a
  symmetric, architecturally plausible pattern. Cleanly rolled back.

## 0.1.0 — 2026-07-05 — Phase 0 foundation walking skeleton

### Added
- Full design backbone: SAD, PRD, ROADMAP, UX_SPEC, PHASE_0_PLAN, and ADR-0001/0002/0003
  under `docs/`.
- Ribbon tab renamed to **"BK BIM Tools"**; panel folders added for Modeling, QA/QC,
  AI, Utilities, Settings (ADR-0003 consolidation).
- `lib/bkbim` package skeleton: `core`, `domain`, `app`, `revit`, `ui`.
- `bkbim.core`: `Result`, `BKBimError` hierarchy, structured logging (console + stubbed
  file sink), immutable `Config` (MCP endpoint `127.0.0.1:48884`), layered
  `SettingsStore` (defaults→office→user→project→session), minimal DI `ServiceContainer`.
- `bkbim.domain`: `SelectionSummary` model, `IElementReader` port (first
  dependency-inversion seam per SAD §2).
- `bkbim.revit.adapter.model_reader.RevitElementReader` — implements `IElementReader`
  against a live `UIDocument`; stubbed `revit/version/revit2026.py` for future API-quirk
  isolation.
- `bkbim.app.commands.count_selected_command` — walking-skeleton use-case; template
  for every future command (DI-resolve → call port → return `Result`).
- `Documentation.panel/CountSelected.pushbutton` — Tier-1 UI shim calling the command.
- `revit-mcp-python.extension`: `/selection/count/` route + `count_selected_elements`
  MCP tool, calling the identical `count_selected_command.run()` the ribbon uses.
- 24 unit tests for `bkbim.core`/`app` (pure Python, no Revit dependency), run via
  `python -m pytest tests/unit`.

### Fixed (found via live smoke test against Revit 2026, same day)
- `bkbim/__init__.py` raised `SyntaxError` under the real engine (non-ASCII em-dash
  without a declared source encoding). Added `# -*- coding: utf-8 -*-` headers
  suite-wide as a guardrail.
- `revit_mcp/selection.py` assumed `sys.path` is shared across pyRevit extensions;
  it is not. Now explicitly adds `BKDesigns.extension/lib` to `sys.path`, computed
  relative to its own file location.
- `bkbim.core.config`'s default `engine` label corrected from `"ironpython3"` to
  `"ironpython2.7"` to match the confirmed live engine.

### Corrected
- **ADR-0001**: the assumed engine was IronPython 3.4; the actual, confirmed engine
  on this installation is **IronPython 2.7.12**. All Revit-facing/domain/core code
  must stay Python-2.7-compatible (no type hints, no f-strings) until/unless a newer
  engine is confirmed available.
- **ADR-0002**: `Auto Dims SC v5` (`AutoDims.extension`) is third-party code found on
  GitHub, not this team's validated work, and is known by the product owner not to
  work well. Phase 1's bar is no longer "feature parity with v5" - see
  `docs/architecture/PHASE_1_PLAN.md`.

### Notes
- No Auto Dimension logic was ported in this release — `AutoDims.extension` remains
  the working tool until Phase 1 ships a first-principles replacement.
