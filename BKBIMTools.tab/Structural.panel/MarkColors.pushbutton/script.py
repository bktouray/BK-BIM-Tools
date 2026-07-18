# -*- coding: utf-8 -*-
__title__ = u"Mark\nColors"
# NOTE: __author__/__authors__ must stay literal strings, never imported
# names - pyRevit reads them via static AST parsing (ast.literal_eval),
# which throws on anything that isn't a plain literal. This pyRevit build
# also has a real bug where it discards __author__ and only ever applies
# __authors__ (plural) - both are set here so this keeps working if that's
# ever fixed. See bkbim.core.branding.AUTHOR for the single source of truth
# these values must always match.
__author__ = u"Baboucarr Katim Touray"
__authors__ = [u"Baboucarr Katim Touray"]
__doc__ = u"""Colors columns or beams by their Mark using real View
Filters - one light pastel color per Mark, so a contractor can match a
beam or column in a plan straight to its Typical Detail Section. Run
Auto Mark first. Apply to specific views, or to a view template so every
view using it updates at once.
"""

from pyrevit import revit, DB, forms, script

import sys as _sys
for _m in [_n for _n in list(_sys.modules) if _n.startswith("bkbim.automation")]:
    del _sys.modules[_m]

from bkbim.automation.mark_colors import (
    CATEGORY_BEAM, CATEGORY_COLUMN, apply_mark_colors, collect_elements,
    generate_mark_colors, list_line_patterns, marks_with_counts, unmarked_count,
)
from bkbim.ui.views.category_picker import show_category_picker
from bkbim.ui.views.confirmation_dialog import show_confirmation
from bkbim.ui.views.mark_color_options import TARGET_TEMPLATE, show_mark_color_options
from bkbim.ui.views.result_dialog import show_result

logger = script.get_logger()
doc = revit.doc


def _name(el):
    try:
        return el.Name
    except Exception:
        return DB.Element.Name.__get__(el)


def _eligible_views():
    views = DB.FilteredElementCollector(doc).OfClass(DB.View).ToElements()
    real = []
    templates = []
    for v in views:
        if not isinstance(v, (DB.ViewPlan, DB.ViewSection, DB.View3D)):
            continue
        try:
            if not v.AreGraphicsOverridesAllowed():
                continue
        except Exception:
            continue
        if v.IsTemplate:
            templates.append(v)
        else:
            real.append(v)
    real.sort(key=lambda v: v.Name.lower())
    templates.sort(key=lambda v: v.Name.lower())
    return real, templates


def main():
    if doc is None:
        show_result(__title__, "No active Revit document.")
        return

    category = show_category_picker(
        __title__.replace("\n", " "),
        u"Pick which category to color by Mark.",
        [CATEGORY_COLUMN, CATEGORY_BEAM])
    if category is None:
        return

    elements = collect_elements(doc, category)
    if not elements:
        show_result(__title__, "No {0}s found in the model.".format(category.lower()))
        return

    mark_counts = marks_with_counts(elements)
    if not mark_counts:
        show_result(
            __title__,
            "No {0}s have a Mark yet.\n\nRun Auto Mark for {0}s first, then try again.".format(category),
        )
        return

    missing = unmarked_count(elements)
    if missing:
        proceed = show_confirmation(
            __title__,
            "{0} of {1} {2}(s) have no Mark and will be left uncolored.\n\n"
            "Continue anyway?".format(missing, len(elements), category.lower()),
            yes_text=u"Continue", no_text=u"Cancel")
        if not proceed:
            return

    colors = generate_mark_colors([m for m, _c in mark_counts])
    real_views, templates = _eligible_views()
    if not real_views and not templates:
        show_result(__title__, "No views or view templates in this project support graphic overrides.")
        return

    line_pattern_choices = list_line_patterns(doc)

    options = show_mark_color_options(
        __title__.replace("\n", " "),
        u"{0} distinct {1} Mark(s) found across {2} element(s).".format(
            len(mark_counts), category.lower(), len(elements)),
        mark_counts, colors, real_views, _name, templates, _name, line_pattern_choices)
    if options is None:
        return

    if options.target_mode == TARGET_TEMPLATE:
        if options.selected_template is None:
            show_result(__title__, "No view template selected.")
            return
        targets = [options.selected_template]
    else:
        if not options.selected_views:
            show_result(__title__, "No view(s) selected.")
            return
        targets = options.selected_views

    t = DB.Transaction(doc, "Mark Colors - {0}".format(category))
    t.Start()
    try:
        res = apply_mark_colors(
            doc, category, mark_counts, colors, targets,
            options.transparency, options.projection_weight, options.cut_weight,
            options.projection_pattern_id, options.cut_pattern_id)
        if res.views_applied == 0:
            t.RollBack()
        else:
            t.Commit()
    except Exception as e:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        logger.error("Mark Colors failed: {0}".format(str(e)))
        show_result(__title__, "Mark Colors failed:\n{0}".format(str(e)))
        return

    if res.views_applied == 0:
        msg = "No views were updated."
        if res.errors:
            msg += "\n\n" + "\n".join(res.errors[:5])
        show_result(__title__, msg)
        return

    show_result(
        __title__,
        "Mark Colors Complete.\n\n"
        "{0} filter(s) created, {1} updated, applied to {2} view(s)/template.".format(
            res.filters_created, res.filters_updated, res.views_applied))
    if res.errors:
        script.get_output().print_md("**Notes:** " + "; ".join(res.errors[:5]))


if __name__ == "__main__":
    main()
