# -*- coding: utf-8 -*-
"""Shared family-symbol picker with an inline "Load family from file" option.

Every automation tool that needs the user to choose a loadable family (columns,
beams, footings, doors, windows...) should use pick_family_symbol so the user
can pull in a new .rfa on the spot if the one they want isn't loaded.

IronPython 2.7.
"""

from pyrevit import DB, forms

_LOAD_LABEL = u"⬇  Load family from file (.rfa)…"


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
            forms.alert("That family is already loaded (or could not be "
                        "loaded). Pick its type from the list.",
                        title="Load Family")
        return True
    except Exception as e:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        forms.alert("Could not load family:\n{0}".format(str(e)),
                    title="Load Family")
        return False


def pick_family_symbol(doc, categories, title):
    """Let the user pick a family type, with an option to load one from file.

    categories: list of DB.BuiltInCategory to list types from.
    Returns a FamilySymbol, or None if cancelled.
    """
    while True:
        symbols = collect_symbols(doc, categories)
        labels = sorted(symbols.keys())
        choice = forms.SelectFromList.show(
            [_LOAD_LABEL] + labels,
            title=title,
            default=(labels[0] if labels else _LOAD_LABEL),
            multiselect=False,
        )
        if not choice:
            return None
        if choice == _LOAD_LABEL:
            load_family_from_file(doc)
            continue  # re-list so the newly loaded types appear
        return symbols[choice]
