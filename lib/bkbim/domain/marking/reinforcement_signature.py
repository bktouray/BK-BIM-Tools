# -*- coding: utf-8 -*-
"""Normalizes Tekla-Structural-Designer-style reinforcement description
strings into a clean, comparable "signature" - used to tell whether two
elements of the same size genuinely have the same reinforcement, or
different (product owner, 2026-07-14: "differentiate it using the
reinforcement in that column and size").

Raw TSDI/NV text (confirmed live against the product owner's real model)
mixes real design data with a Tekla-internal bar-group id that must be
discarded, or the same real design gets miscounted as many different ones:

    TSDI_RC_Bars   "4H12-206"                          (id "206" is noise)
    TSDI_RC_Links  "H8-25-100"                          (id "25" is noise, "100" is the real spacing)
    TSDI_RC_Links  "H8-32-100, 2H8-33-100"              (comma = extra link group; "2H8" leg-count IS real)
    TSDI_RC_Top    "L 2H12-1 (25.00%); C 2H12-8"        ("L"/"C"/"R" zone + curtailment % both real)
    TSDI_RC_Links  "C H8-275 (2 legs, 100.00%)"         (beam format: no id, legs/pct suffix real)
    NVRebarSetting "H12-150."                           (footing format: no id, trailing period to strip)

Confirmed with the product owner (2026-07-14) using real examples from
their own model: normalize away only the internal id, keep diameter,
spacing, leg-count, zone, and curtailment % as real differentiators.

Pure, zero Revit imports (ADR-0001) - plain string parsing, unit-testable
under CPython.
"""

import re

_BAR_GROUP_RE = re.compile(r"^(\d*H\d+)(?:-\d+)?$")
_LINK_GROUP_RE = re.compile(r"^(\d*H\d+)-(\d+)(?:-(\d+))?$")
_ZONE_PREFIXES = (u"L", u"C", u"R")

# Reinforcement data-source tiers (product owner, 2026-07-15: "how do i
# know if it is using tekla exported text, nv rebar or modelled rebar?
# make me notice that difference when marking") - the 3-tier priority
# order itself (modeled Rebar first, then exported text, then no data)
# lives in mark_type_reader.py's readers; these are just the labels a
# reader tags its result with, surfaced in AutoMarkOptions' preview so the
# source is visible per group, not silently blended into one signature
# string. "Tekla Text" (TSDI_RC_*, columns/beams) and "Naviate Text"
# (NVRebarSetting, footings) are kept as two distinct labels, not one
# generic "exported text" - they're genuinely different export sources in
# this project, not just different parameter names for the same thing.
SOURCE_MODELED_REBAR = u"Modeled Rebar"
SOURCE_TEKLA_TEXT = u"Tekla Text"
SOURCE_NAVIATE_TEXT = u"Naviate Text"
SOURCE_NONE = u"No Rebar Data"


def normalize_bar_group(token):
    """'2H12-1' -> '2H12' (strips the trailing Tekla bar-group id, if any).
    Any percentage/other suffix must already be split off by the caller -
    this only handles the bare '<count>H<dia>[-<id>]' token.
    """
    token = (token or u"").strip()
    m = _BAR_GROUP_RE.match(token)
    return m.group(1) if m else token


def _split_trailing_paren(text):
    """'2H12-1 (25.00%)' -> ('2H12-1', ' (25.00%)'). No paren -> ('2H12-1', '')."""
    idx = text.find(u"(")
    if idx == -1:
        return text.strip(), u""
    return text[:idx].strip(), u" " + text[idx:].strip()


def _normalize_bar_subgroup(token):
    base, suffix = _split_trailing_paren(token)
    return normalize_bar_group(base) + suffix


def normalize_main_bars_string(raw):
    """Normalizes a main-bar (longitudinal) reinforcement string - a plain
    column-style single group ('4H12-206'), a beam-style zone-prefixed,
    semicolon-separated list ('L 2H12-1 (25.00%); C 2H12-8;
    R 2H12-16 (25.00%)'), and/or comma-separated extra bar groups within
    one zone, each with its OWN independent curtailment % ('C 2H12-36,
    2H12-32 (70.00%)' - a real format seen on beam bottom bars, where the
    2nd group is curtailed and the 1st isn't). Percentages/zones/counts are
    kept (real data); only the trailing Tekla bar-group id is stripped.
    """
    if not raw:
        return u""
    zone_segments = [s.strip() for s in raw.split(u";") if s.strip()]
    out = []
    for seg in zone_segments:
        zone = None
        rest = seg
        parts = seg.split(u" ", 1)
        if len(parts) == 2 and parts[0] in _ZONE_PREFIXES:
            zone, rest = parts[0], parts[1]
        subgroups = [_normalize_bar_subgroup(g) for g in rest.split(u",")]
        normalized = u", ".join(subgroups)
        out.append(u"{0} {1}".format(zone, normalized) if zone else normalized)
    return u"; ".join(out)


def normalize_link_group(token):
    """'H8-25-100' -> 'H8@100c/c' (middle id dropped, last number is the
    real spacing). 'H8-275' (no id, e.g. beam format) -> 'H8@275c/c'.
    Trailing punctuation ('H12-150.') is stripped before matching.
    """
    token = (token or u"").strip().rstrip(u".")
    m = _LINK_GROUP_RE.match(token)
    if not m:
        return token
    dia, a, b = m.group(1), m.group(2), m.group(3)
    spacing = b if b is not None else a
    return u"{0}@{1}c/c".format(dia, spacing)


def normalize_links_string(raw):
    """Normalizes a stirrup/link reinforcement string. Handles all three
    real formats: plain column groups ('H8-25-100', optionally comma-
    separated extra groups like '..., 2H8-33-100'), zone-prefixed beam
    groups with a legs/percentage suffix ('C H8-275 (2 legs, 100.00%)',
    optionally semicolon-separated per zone), and footing single-group
    ('H12-150.'). Leg-count differences (plain 'H8' vs '2H8') and
    percentages are kept as real differentiators; only Tekla's internal
    bar-group id is dropped.
    """
    if not raw:
        return u""
    segments = [s.strip() for s in raw.split(u";") if s.strip()]
    out = []
    for seg in segments:
        zone = None
        rest = seg
        parts = seg.split(u" ", 1)
        if len(parts) == 2 and parts[0] in _ZONE_PREFIXES:
            zone, rest = parts[0], parts[1]
        base, suffix = _split_trailing_paren(rest)
        groups = [normalize_link_group(g) for g in base.split(u",")]
        normalized = u", ".join(groups) + suffix
        out.append(u"{0} {1}".format(zone, normalized) if zone else normalized)
    return u"; ".join(out)


def column_signature(bars_raw, links_raw):
    """Reinforcement signature for one column instance."""
    return u"{0} | {1}".format(normalize_main_bars_string(bars_raw), normalize_links_string(links_raw))


# ---------------------------------------------------------------------------
# Modeled-rebar signatures (product owner, 2026-07-14: "sometimes the export
# data isn't always correct... use the actual modelled rebar as the first
# option"). Built from REAL Rebar elements hosted on the instance, not text.
# Deliberately emit the SAME token vocabulary as the text-based functions
# above ("<count>H<dia>" for main bars, "<legs>H<dia>@<spacing>c/c" for
# links/mesh) - confirmed live only 23/103 columns and 34/68 footings in
# the real model actually have modeled rebar (beams: 0/161), so most
# elements of a given size still rely on the text tier; if the two tiers
# used different formats, a modeled-rebar element and a text-only element
# of the truly identical real design would spuriously fail to match and
# split into "different" groups. Same format = they still match when the
# real design agrees, even if one came from geometry and the other from text.
# ---------------------------------------------------------------------------

def modeled_main_bars_signature(bar_groups):
    """bar_groups: list of (diameter_mm, quantity) - one entry per
    FixedNumber-layout Rebar set (real bar count is meaningful for this
    layout rule; its incidental "spacing" is not). Quantities are summed
    per diameter - a column with 4 FixedNumber sets of 2xH12 each becomes
    one '8H12' token, same as the text tier's own count.
    """
    if not bar_groups:
        return u""
    totals = {}
    order = []
    for dia_mm, qty in bar_groups:
        if dia_mm not in totals:
            totals[dia_mm] = 0
            order.append(dia_mm)
        totals[dia_mm] += qty
    order.sort(key=lambda d: -totals[d])
    return u", ".join(u"{0}H{1}".format(totals[d], d) for d in order)


def modeled_links_signature(link_groups):
    """link_groups: list of (diameter_mm, spacing_mm) - one entry per
    MaximumSpacing-layout Rebar set (spacing is the meaningful design
    value for this layout rule; its instance count depends on the
    element's own height/size and is NOT meaningful). The same
    (diameter, spacing) repeated across N separate sets (e.g. multiple leg
    groups) becomes '<N>H<dia>@<spacing>c/c' - same leg-count convention
    the text tier uses for comma-separated extra groups.
    """
    if not link_groups:
        return u""
    counts = {}
    order = []
    for dia_mm, spacing_mm in link_groups:
        key = (dia_mm, spacing_mm)
        if key not in counts:
            counts[key] = 0
            order.append(key)
        counts[key] += 1
    tokens = []
    for dia_mm, spacing_mm in order:
        n = counts[(dia_mm, spacing_mm)]
        prefix = u"{0}".format(n) if n > 1 else u""
        tokens.append(u"{0}H{1}@{2}c/c".format(prefix, dia_mm, spacing_mm))
    return u", ".join(tokens)


def modeled_column_signature(main_bar_groups, link_groups):
    """Reinforcement signature for one column instance, built from its
    actual modeled Rebar (see modeled_main_bars_signature/modeled_links_signature).
    """
    return u"{0} | {1}".format(
        modeled_main_bars_signature(main_bar_groups), modeled_links_signature(link_groups))


def modeled_footing_signature(mesh_groups):
    """Reinforcement signature for one footing instance, built from its
    actual modeled Rebar mesh (footings have no main-bar/link distinction -
    it's one distributed mesh, same math as modeled_links_signature).
    """
    return modeled_links_signature(mesh_groups)


def beam_signature(top_raw, bottom_raw, links_raw):
    """Reinforcement signature for one beam instance."""
    return u"{0} | {1} | {2}".format(
        normalize_main_bars_string(top_raw), normalize_main_bars_string(bottom_raw),
        normalize_links_string(links_raw))


def footing_signature(rebar_raw):
    """Reinforcement signature for one footing instance."""
    return normalize_links_string(rebar_raw)
