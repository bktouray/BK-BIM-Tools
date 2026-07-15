# -*- coding: utf-8 -*-
"""Runs the full Wall & Openings dimensioning flow (pick view(s) -> collect
wall types across them -> options window -> exterior-wall mode -> one
Transaction per view) - shared by AutoWallOpeningDimension.pushbutton and
Smart Dimension's Walls & Openings path so both stay in sync (mirrors
structural_dimension_flow.py's shared-flow pattern, and fixes the
near-duplicate bodies those two scripts used to carry independently).

Multi-view batching (product owner, 2026-07-08: "I sometimes have different
views with a similar drawing, I want an option where I can select the views
I want to apply similar dimension styles") reuses ONE options window across
every selected view - same dimension style, wall types, offsets, and
exterior-wall mode applied identically everywhere - then runs each view in
its own Transaction inside one TransactionGroup, so the whole batch undoes
as a single step but one view's failure doesn't roll back the others.

Manual exterior-wall picking (PickObjects) only works in Revit's currently
active view, so it stays available for a single-view run but drops to
Auto-detect/Skip for a multi-view run (product owner's explicit choice:
"auto-detect on every view" for batch mode).

`target_views` is an optional pre-resolved override (skips the "pick
view(s)" prompt entirely) - added 2026-07-08 so SmartDimension's Auto-Detect
mode can force this flow to stay on the single current view, instead of
adding its own "pick views?" prompt on top of Auto-Detect's own scan.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector, Transaction, Wall
from pyrevit import forms

from bkbim.app.commands import auto_wall_opening_dimension_command
from bkbim.core.tool_memory import recall, remember
from bkbim.revit.adapter.dimension_type_reader import list_linear_dimension_types
from bkbim.revit.adapter.dimension_writer import DimensionWriter
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.existing_dimension_checker import RevitExistingDimensionChecker
from bkbim.revit.adapter.exterior_wall_detector import detect_exterior_walls
from bkbim.revit.adapter.failure_policy import ScopedFailurePolicy
from bkbim.revit.adapter.multi_view_batch import alert_batch_results, run_across_views
from bkbim.revit.adapter.reference_provider import RevitReferenceProvider
from bkbim.revit.adapter.stable_representation import element_id_token
from bkbim.revit.adapter.view_selection_prompt import pick_target_views
from bkbim.revit.adapter.wall_context_builder import build_walls_with_context
from bkbim.revit.adapter.wall_selection_prompt import (
    AUTO_DETECT,
    SKIP_EXTERIOR,
    pick_exterior_perimeter_style,
    pick_exterior_walls,
)
from bkbim.revit.adapter.wall_type_reader import list_wall_types_in_view
from bkbim.ui.views.category_picker import show_category_picker
from bkbim.ui.views.options_memory import to_remembered
from bkbim.ui.views.wall_opening_dimension_options import show_wall_opening_dimension_options

_TRANSACTION_LABEL = u"Auto Dimension Walls & Openings"
_OFFSET_KEY = u"wall_opening_dimension.offset_mm"
_GAP_KEY = u"wall_opening_dimension.gap_mm"
_STYLE_KEY = u"wall_opening_dimension.dimension_type_name"
_TYPES_KEY = u"wall_opening_dimension.selected_wall_type_names"


def run_wall_dimension_flow(doc, uidoc, view, standard, title, target_views=None):
    """Runs collect -> pick view(s) -> options -> exterior-wall mode -> one
    Transaction per view -> one combined summary alert.
    """
    target_views = target_views or pick_target_views(doc, view, title)
    batch = len(target_views) > 1

    combined_wall_types = {}
    for v in target_views:
        for wt in list_wall_types_in_view(doc, v):
            combined_wall_types.setdefault(element_id_token(wt.Id), wt)

    if not combined_wall_types:
        forms.alert(u"No walls found in the selected view(s).", title=title)
        return

    default_offset_mm = recall(_OFFSET_KEY, default=standard.offset_first_mm, doc=doc)
    default_gap_mm = recall(_GAP_KEY, default=standard.wall_perimeter_gap_mm, doc=doc)
    default_style_name = recall(_STYLE_KEY, doc=doc)
    default_type_names = recall(_TYPES_KEY, doc=doc)

    dimension_types = list_linear_dimension_types(doc)
    options = show_wall_opening_dimension_options(
        dimension_types, list(combined_wall_types.values()), type_name, default_offset_mm, default_gap_mm,
        default_dimension_type_name=default_style_name,
        default_selected_wall_type_names=default_type_names)
    if options is None:
        return  # user cancelled

    standard.offset_first_mm = options.offset_mm
    standard.wall_perimeter_gap_mm = options.perimeter_gap_mm
    remember(_OFFSET_KEY, options.offset_mm, doc=doc)
    remember(_GAP_KEY, options.perimeter_gap_mm, doc=doc)
    if options.dimension_type is not None:
        remember(_STYLE_KEY, to_remembered(
            options.dimension_type, type_name, lambda dt: element_id_token(dt.Id)), doc=doc)
    remember(_TYPES_KEY, [
        to_remembered(wt, type_name, lambda t: element_id_token(t.Id)) for wt in options.selected_wall_types],
        doc=doc)
    selected_type_keys = set(element_id_token(wt.Id) for wt in options.selected_wall_types)

    resolve_exterior = _build_exterior_resolver(doc, uidoc, batch, title)

    results = run_across_views(
        doc, target_views, _TRANSACTION_LABEL,
        lambda v: _run_one_view(doc, v, selected_type_keys, resolve_exterior, options, standard))
    alert_batch_results(results, title)


def _build_exterior_resolver(doc, uidoc, batch, title):
    """Decides ONCE (not per-view) how exterior walls - and their perimeter
    dimension style - get resolved for this run. Returns
    resolve(view, dimensionable_walls) -> (exterior_wall_ids, exterior_perimeter_dimension_type).
    """
    if not batch:
        def resolve(v, dimensionable_walls):
            return pick_exterior_walls(uidoc, doc, v, dimensionable_walls, title)
        return resolve

    choice = show_category_picker(
        title,
        u"Also dimension exterior walls with the extra perimeter strings "
        u"across every selected view? Manual picking only works in a single "
        u"active view, so batch runs use auto-detection instead.",
        [AUTO_DETECT, SKIP_EXTERIOR])

    if choice == AUTO_DETECT:
        exterior_style = pick_exterior_perimeter_style(doc, title)

        def resolve(v, dimensionable_walls):
            return detect_exterior_walls(doc, v, dimensionable_walls), exterior_style
    else:
        def resolve(v, dimensionable_walls):
            return set(), None
    return resolve


def _walls_in_view(doc, view):
    raw = FilteredElementCollector(doc, view.Id).OfCategory(
        BuiltInCategory.OST_Walls).WhereElementIsNotElementType().ToElements()
    return [w for w in raw if isinstance(w, Wall)]


def _run_one_view(doc, v, selected_type_keys, resolve_exterior, options, standard):
    walls = _walls_in_view(doc, v)
    dimensionable_walls = [w for w in walls if element_id_token(w.WallType.Id) in selected_type_keys]
    if not dimensionable_walls:
        return v.Name, u"No walls match the selected wall type(s)."

    exterior_wall_ids, exterior_perimeter_dimension_type = resolve_exterior(v, dimensionable_walls)

    walls_with_context = build_walls_with_context(
        doc, v, dimensionable_walls, exterior_wall_ids=exterior_wall_ids)
    if not walls_with_context:
        return v.Name, u"No dimensionable walls found in this view."

    reference_provider = RevitReferenceProvider(doc, v)
    writer = DimensionWriter(
        doc, v, dimension_type=options.dimension_type,
        exterior_perimeter_dimension_type=exterior_perimeter_dimension_type)
    existing_dimension_checker = RevitExistingDimensionChecker(doc, v)
    failure_tracker = ScopedFailurePolicy()

    t = Transaction(doc, u"{0} ({1})".format(_TRANSACTION_LABEL, v.Name))
    opts = t.GetFailureHandlingOptions()
    opts.SetFailuresPreprocessor(failure_tracker)
    t.SetFailureHandlingOptions(opts)
    t.Start()
    try:
        result = auto_wall_opening_dimension_command.run(
            walls_with_context, reference_provider, reference_provider,
            existing_dimension_checker, writer, failure_tracker, standard)
    except Exception as e:
        t.RollBack()
        return v.Name, u"Error:\n{0}".format(str(e))

    if result.success:
        t.Commit()
    else:
        t.RollBack()
    return v.Name, result.message
