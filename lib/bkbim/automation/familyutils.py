# -*- coding: utf-8 -*-
"""Shared family-symbol picker with an inline "Load family from file" option.

Every automation tool that needs the user to choose a loadable family (columns,
beams, footings, doors, windows...) should use pick_family_symbol so the user
can pull in a new .rfa on the spot if the one they want isn't loaded.

IronPython 2.7.
"""

from pyrevit import DB, forms

from bkbim.ui.views.family_symbol_picker import show_family_symbol_picker
from bkbim.ui.views.result_dialog import show_result


def _name(el):
    try:
        return el.Name
    except Exception:
        return DB.Element.Name.__get__(el)


def collect_symbols(doc, categories):
    """dict {"Family : Type" -> FamilySymbol} for the given BuiltInCategories."""
    out = {}
    for bic in categories:
        syms = (DB.FilteredElementCollector(doc).OfClass(DB.FamilySymbol)
                .OfCategory(bic).ToElements())
        for s in syms:
            out[u"{0} : {1}".format(_name(s.Family), _name(s))] = s
    return out


def load_family_from_file(doc):
    """Prompt for an .rfa and load it. Returns True if a load was attempted."""
    path = forms.pick_file(file_ext="rfa",
                           title="Load a Revit family (.rfa)")
    if not path:
        return False
    t = DB.Transaction(doc, "Load Family")
    t.Start()
    try:
        ok = doc.LoadFamily(path)
        t.Commit()
        if not ok:
            show_result(
                "Load Family",
                "That family is already loaded (or could not be "
                "loaded). Pick its type from the list.")
        return True
    except Exception as e:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        show_result("Load Family", "Could not load family:\n{0}".format(str(e)))
        return False


def pick_family_symbol(doc, categories, title):
    """Let the user pick a family type, with an option to load one from file.

    categories: list of DB.BuiltInCategory to list types from.
    Returns a FamilySymbol, or None if cancelled.
    """
    return show_family_symbol_picker(
        title,
        lambda: collect_symbols(doc, categories),
        lambda: load_family_from_file(doc),
    )
