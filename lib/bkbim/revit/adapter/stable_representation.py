# -*- coding: utf-8 -*-
"""Pure helpers for Revit Reference stable-representation surgery.

No `clr`/Revit imports here on purpose: this file must be importable and testable
under plain CPython (see tests/unit/test_reference_provider_helpers.py), even though
it only makes sense in a Revit context. Keeping it Revit-import-free is what makes
the riskiest string manipulation in the reference provider actually unit-testable
rather than only reachable through a live Revit session.
"""


def rewrite_stable_representation_element_id(stable, new_element_id_token):
    """Replaces the leading element-id token of a Reference's stable representation.

    Stable representations look like "12345:1:RVTLINK/0:2:1/..." - the first
    colon-delimited token is the element id. GetSymbolGeometry() gives a stable
    representation keyed to the family TYPE; NewDimension needs one keyed to the
    INSTANCE.
    """
    colon_idx = stable.index(":")
    return u"{0}{1}".format(new_element_id_token, stable[colon_idx:])


def element_id_token(element_id):
    """Returns the string token Revit's stable representation uses for an element id.

    ElementId.IntegerValue is gone in Revit 2026; .Value is the replacement (see
    revit2026-ironpython-quirks memory). Duck-typed so it works with any object
    exposing either attribute, real ElementId or a test double.
    """
    try:
        return str(element_id.Value)
    except AttributeError:
        return str(element_id.IntegerValue)


def reference_stable_key(doc, reference):
    """Returns a comparable string key for a Reference via its stable
    representation - used to detect whether two references point at the same
    underlying geometry (e.g. an existing dimension's reference vs. a freshly
    planned one). Verified live 2026-07-05: a just-written dimension's own
    references produce byte-identical keys to the plan that created them.
    """
    return reference.ConvertToStableRepresentation(doc)
