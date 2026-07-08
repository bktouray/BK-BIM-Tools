# -*- coding: utf-8 -*-
"""Version-safe helpers shared by every automation tool.

Keep this module dependency-light: it must import cleanly under the
IronPython 2.7 engine pyRevit ships with. No f-strings, no Python 3 stdlib.
"""

from pyrevit import DB


def element_id_value(element_id):
    """Return the integer value of an ElementId across Revit versions.

    Revit 2025+ exposes .Value (int64); older versions use .IntegerValue.
    Revit 2026 removed .IntegerValue entirely.
    """
    try:
        return int(element_id.Value)
    except AttributeError:
        return int(element_id.IntegerValue)


def normalize_string(text):
    """Always return a stripped unicode string, tolerating odd encodings."""
    if text is None:
        return u"Unnamed"
    if isinstance(text, unicode):
        return text.strip()
    if isinstance(text, str):
        try:
            return text.decode("utf-8").strip()
        except (UnicodeDecodeError, AttributeError):
            return text.decode("latin-1").strip()
    try:
        return unicode(text).strip()
    except Exception:
        return u"Unnamed"


# ---------------------------------------------------------------------------
# Units. Revit's internal length unit is decimal feet. CAD geometry returned
# by GetInstanceGeometry() is already scaled into those internal feet, so the
# unit selector in the UI only matters for distances the *user* types in
# (extend margins, snapping tolerances, etc.).
# ---------------------------------------------------------------------------

_MM_PER_FOOT = 304.8
_INCH_PER_FOOT = 12.0


def to_feet(value, unit):
    """Convert a user-entered length in 'mm' | 'in' | 'ft' | 'm' to feet."""
    u = (unit or "ft").lower()
    if u in ("mm", "millimeter", "millimeters"):
        return float(value) / _MM_PER_FOOT
    if u in ("m", "meter", "meters"):
        return (float(value) * 1000.0) / _MM_PER_FOOT
    if u in ("in", "inch", "inches"):
        return float(value) / _INCH_PER_FOOT
    return float(value)


def feet_to(value_ft, unit):
    """Convert internal feet to the given display unit."""
    u = (unit or "ft").lower()
    if u in ("mm", "millimeter", "millimeters"):
        return float(value_ft) * _MM_PER_FOOT
    if u in ("m", "meter", "meters"):
        return (float(value_ft) * _MM_PER_FOOT) / 1000.0
    if u in ("in", "inch", "inches"):
        return float(value_ft) * _INCH_PER_FOOT
    return float(value_ft)


def column_letter(index):
    """0 -> 'A', 25 -> 'Z', 26 -> 'AA' ... for grid bubble labelling."""
    index = int(index)
    label = u""
    n = index + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        label = unichr(ord(u"A") + rem) + label
    return label
