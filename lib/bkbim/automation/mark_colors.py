# -*- coding: utf-8 -*-
"""Colors Columns/Beams in a view (or view template) by their Mark, via real
Revit View Filters - not a one-off "color splash," a permanent, reusable
filter set (product owner, 2026-07-15: contractor-readability - "he'll see
a beam in the framing plan and go to the typical beam section details and
will automatically know what's what").

One ParameterFilterElement per distinct Mark ("Mark Color - Column - C9"),
matching BuiltInParameter.ALL_MODEL_MARK by an equals rule, scoped to the
relevant category. Colors are LIGHT/pastel (product owner: "nothing too
bold or vibrant") - fixed saturation/lightness in HSL, hue stepped by the
golden angle across marks sorted alphabetically for even, deterministic
distribution (same mark set -> same colors every re-run; no persistence
needed since it's derived purely from the sorted mark list itself).

IronPython 2.7.
"""

import colorsys
import math

import System
from pyrevit import DB

_GOLDEN_ANGLE = 0.61803398875  # fractional part of 1/phi - even hue spacing

# "Light... nothing too bold or vibrant" (product owner, 2026-07-15) -
# moderate saturation, high lightness, in HSL terms.
_SATURATION = 0.42
_LIGHTNESS = 0.80


def generate_mark_colors(marks):
    """marks: iterable of mark strings. Returns {mark: DB.Color}, evenly
    spaced pastel hues assigned in ALPHABETICAL mark order (deterministic -
    the same set of marks always gets the same colors, regardless of scan
    order).
    """
    ordered = sorted(set(marks))
    colors = {}
    for i, mark in enumerate(ordered):
        hue = (i * _GOLDEN_ANGLE) % 1.0
        r, g, b = colorsys.hls_to_rgb(hue, _LIGHTNESS, _SATURATION)
        colors[mark] = DB.Color(int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))
    return colors


# ---------------------------------------------------------------------------
# Reading marks
# ---------------------------------------------------------------------------

CATEGORY_COLUMN = u"Column"
CATEGORY_BEAM = u"Beam"

_CATEGORY_BUILTIN_CATEGORIES = {
    CATEGORY_COLUMN: (DB.BuiltInCategory.OST_StructuralColumns, DB.BuiltInCategory.OST_Columns),
    CATEGORY_BEAM: (DB.BuiltInCategory.OST_StructuralFraming,),
}


def collect_elements(doc, category):
    elems = []
    for bic in _CATEGORY_BUILTIN_CATEGORIES[category]:
        collected = DB.FilteredElementCollector(doc).OfCategory(bic).WhereElementIsNotElementType().ToElements()
        elems.extend([e for e in collected if isinstance(e, DB.FamilyInstance)])
    return elems


def marks_with_counts(elements):
    """Returns [(mark, count), ...] sorted by mark, for elements that have
    a non-blank Mark. Caller should warn separately about any unmarked
    elements (same "Auto Mark must run first" convention as Typical Views).
    """
    counts = {}
    for e in elements:
        p = e.LookupParameter(u"Mark")
        mark = (p.AsString() if p else None) or u""
        mark = mark.strip()
        if not mark:
            continue
        counts[mark] = counts.get(mark, 0) + 1
    return sorted(counts.items())


def unmarked_count(elements):
    n = 0
    for e in elements:
        p = e.LookupParameter(u"Mark")
        mark = (p.AsString() if p else None) or u""
        if not mark.strip():
            n += 1
    return n


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

def solid_fill_pattern_id(doc):
    for fp in DB.FilteredElementCollector(doc).OfClass(DB.FillPatternElement).ToElements():
        if fp.GetFillPattern().IsSolidFill:
            return fp.Id
    return None


def list_line_patterns(doc):
    """[(label, pattern_id), ...] - 'Solid' first (Revit's built-in solid
    line, not a document LinePatternElement, hence the special static id),
    then every loaded custom LinePatternElement, alphabetical.
    """
    out = [(u"Solid", DB.LinePatternElement.GetSolidPatternId())]
    patterns = DB.FilteredElementCollector(doc).OfClass(DB.LinePatternElement).ToElements()
    for lp in sorted(patterns, key=lambda p: p.Name.lower()):
        out.append((lp.Name, lp.Id))
    return out


def _filter_name(category, mark):
    return u"Mark Color - {0} - {1}".format(category, mark)


def get_or_create_mark_filter(doc, category, mark):
    """Creates (or, if a same-named filter already exists, updates in
    place - safe to re-run, same convention as every other tool in this
    suite) a ParameterFilterElement matching Mark == `mark`, scoped to
    `category`'s categories.
    """
    name = _filter_name(category, mark)
    cat_ids = System.Collections.Generic.List[DB.ElementId]()
    for bic in _CATEGORY_BUILTIN_CATEGORIES[category]:
        cat_ids.Add(DB.ElementId(bic))

    mark_param_id = DB.ElementId(DB.BuiltInParameter.ALL_MODEL_MARK)
    rule = DB.ParameterFilterRuleFactory.CreateEqualsRule(mark_param_id, mark)
    element_filter = DB.ElementParameterFilter(rule)

    existing = DB.FilteredElementCollector(doc).OfClass(DB.ParameterFilterElement).ToElements()
    for pfe in existing:
        if pfe.Name == name:
            pfe.SetCategories(cat_ids)
            pfe.SetElementFilter(element_filter)
            return pfe

    return DB.ParameterFilterElement.Create(doc, name, cat_ids, element_filter)


def build_override(color, transparency, solid_fill_id, projection_weight, cut_weight,
                    projection_pattern_id, cut_pattern_id):
    ogs = DB.OverrideGraphicSettings()
    if solid_fill_id is not None:
        ogs.SetSurfaceForegroundPatternId(solid_fill_id)
        ogs.SetSurfaceForegroundPatternColor(color)
        ogs.SetCutForegroundPatternId(solid_fill_id)
        ogs.SetCutForegroundPatternColor(color)
    ogs.SetProjectionLineColor(color)
    ogs.SetCutLineColor(color)
    ogs.SetSurfaceTransparency(int(transparency))
    ogs.SetProjectionLineWeight(int(projection_weight))
    ogs.SetCutLineWeight(int(cut_weight))
    if projection_pattern_id is not None:
        ogs.SetProjectionLinePatternId(projection_pattern_id)
    if cut_pattern_id is not None:
        ogs.SetCutLinePatternId(cut_pattern_id)
    return ogs


class MarkColorResult(object):
    def __init__(self):
        self.filters_created = 0
        self.filters_updated = 0
        self.views_applied = 0
        self.errors = []


def apply_mark_colors(doc, category, mark_counts, colors, targets, transparency,
                       projection_weight, cut_weight, projection_pattern_id, cut_pattern_id):
    """mark_counts: [(mark, count), ...]. colors: {mark: DB.Color}.
    targets: list of View (already resolved - either the picked views, or
    every real view using the picked template plus the template itself,
    per apply_to_template_and_its_views()).
    """
    res = MarkColorResult()
    solid_fill_id = solid_fill_pattern_id(doc)

    filters_and_overrides = []
    existing_names = set(pfe.Name for pfe in
                          DB.FilteredElementCollector(doc).OfClass(DB.ParameterFilterElement).ToElements())
    for mark, _count in mark_counts:
        try:
            was_existing = _filter_name(category, mark) in existing_names
            pfe = get_or_create_mark_filter(doc, category, mark)
            if was_existing:
                res.filters_updated += 1
            else:
                res.filters_created += 1
            ogs = build_override(
                colors[mark], transparency, solid_fill_id, projection_weight, cut_weight,
                projection_pattern_id, cut_pattern_id)
            filters_and_overrides.append((pfe.Id, ogs))
        except Exception as e:
            res.errors.append(u"Mark {0}: {1}".format(mark, unicode(str(e))))

    for view in targets:
        try:
            for filter_id, ogs in filters_and_overrides:
                if filter_id not in view.GetFilters():
                    view.AddFilter(filter_id)
                view.SetFilterOverrides(filter_id, ogs)
            res.views_applied += 1
        except Exception as e:
            res.errors.append(u"View {0}: {1}".format(view.Name, unicode(str(e))))

    return res
