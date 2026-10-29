# Master Filter

Open **BK BIM Tools > Utilities > Master Filter** in a Revit project.
Requires the repository's pyRevit / IronPython 2.7 setup and Revit 2026.

1. Choose Active view, Current selection, or Entire project. Current selection
   means the elements selected when the tool opened. Changing scope clears filters.
2. Select categories, families, types and levels with Ctrl/Shift. An empty list
   includes every value. Lists cascade left to right: category narrows family,
   family narrows type, and type narrows level. For example, choosing Doors shows
   only door families, door types and levels containing those doors. Parameter
   choices come from elements matching these selections. Multiple parent choices
   show their combined available values. Valid child selections are preserved;
   selections no longer available are cleared automatically. Added parameter rules
   remain until removed or cleared, even if their parameter leaves the picker.
   Choices within a list combine with OR; lists combine with AND.
   Clear filters restores all choices without changing scope.
3. Optionally add parameter rules and choose Match all rules or Match any rule.
   Instance and type parameters are separate, identified by parameter ID to avoid
   confusing parameters with duplicate names. Text rules use case-insensitive
   display values. Numeric comparisons require a number without a unit suffix,
   in the parameter's project display units (for example, 3000 for a length shown
   in millimeters). Integers use their stored numeric value, including Yes/No
   parameters (0/1). Missing parameters never match, including negative rules.
4. Preview matches. The preview lists the first 500, while the count and actions
   include all matches. Rules must be added with Add rule before they take effect.
5. Select matches replaces Revit's selection; Show in Revit also asks Revit to
   reveal the elements; Temporarily isolate applies temporary isolation in the
   active view and selects matches. Use Revit's Reset Temporary Hide/Isolate
   control or Undo to restore visibility. Cancel preserves selection and visibility.

Collection includes categorized placed elements in the host document, including
annotations, and excludes element types. Linked model contents are not traversed.
Active-view candidates follow Revit's view collector semantics and are not a
pixel-visibility test. Level means the element's API LevelId; elements without
that association appear under (No level). A family/type name selected from the
lists matches that name wherever it occurs, subject to other selected criteria.
Show/isolate support depends on Revit's active view and element visibility.

## Validation

Automated tests cover rule logic and the application result boundary off Revit.
The Revit API adapter and WPF UI require a live Revit 2026 smoke test:

- Open a plan with walls and doors on multiple levels; preview each scope.
- Combine category/type/level filters and compare IDs to known elements.
- Check instance Comments, type parameters, empty/missing values, and a length
  threshold using project units; exercise all/any rules.
- Confirm Select, Show, temporary isolation, Reset Temporary Hide/Isolate and Undo.
- Confirm Cancel and zero matches preserve the original selection; check an empty
  selection, a non-collectable view, and the suite's light/dark themes.
