# -*- coding: utf-8 -*-
"""Reads every family type actually placed in the document for ONE Auto Mark
category (Doors, Windows, Columns, Beams, Footings) at a time - doc-wide, not
view-scoped, since Mark numbering should account for every placed instance
regardless of which view is active.

Dimension reading differs by category since there's no single Revit
parameter scheme that covers all of them:
- Doors/Windows have real BuiltInParameters (DOOR_WIDTH/DOOR_HEIGHT etc.),
  read off the type first, same convention as lib/bkbim/boq/extractors.py's
  door/window fields. They also split same-type instances by host wall
  thickness so the same door/window in two walls can receive A/B suffixes
  under one base mark.
- Columns/Beams/Footings have no universal BuiltInParameter for their
  section/plan dimensions - family authors use all sorts of display names
  ("b"/"h", "Width"/"Depth", "bf"/"d", ...), so these fall back to a list of
  candidate LookupParameter name pairs, extending the same idea already used
  (write-side) by lib/bkbim/automation/columns.py's _BH_NAMES.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import (
    BuiltInCategory, BuiltInParameter, FamilyInstance, FilteredElementCollector,
)
from Autodesk.Revit.DB.Structure import Rebar, RebarLayoutRule

from bkbim.domain.geometry.units import ft_to_mm
from bkbim.domain.marking.reinforcement_signature import (
    SOURCE_MODELED_REBAR, SOURCE_NAVIATE_TEXT, SOURCE_NONE, SOURCE_TEKLA_TEXT,
    beam_signature, column_signature, footing_signature,
    modeled_column_signature, modeled_footing_signature,
)
from bkbim.domain.models.mark_family_group import MarkFamilyGroup
from bkbim.domain.models.mark_reinforcement_group import MarkReinforcementGroup
from bkbim.domain.models.mark_type_group import MarkTypeGroup
from bkbim.revit.adapter.element_naming import type_name
from bkbim.revit.adapter.stable_representation import element_id_token

CATEGORY_DOORS = u"Doors"
CATEGORY_WINDOWS = u"Windows"
CATEGORY_COLUMNS = u"Columns"
CATEGORY_BEAMS = u"Beams"
CATEGORY_FOOTINGS = u"Footings"

CATEGORIES = (CATEGORY_DOORS, CATEGORY_WINDOWS, CATEGORY_COLUMNS,
              CATEGORY_BEAMS, CATEGORY_FOOTINGS)

CATEGORY_BUILTIN_CATEGORIES = {
    CATEGORY_DOORS: (BuiltInCategory.OST_Doors,),
    CATEGORY_WINDOWS: (BuiltInCategory.OST_Windows,),
    CATEGORY_COLUMNS: (BuiltInCategory.OST_StructuralColumns, BuiltInCategory.OST_Columns),
    CATEGORY_BEAMS: (BuiltInCategory.OST_StructuralFraming,),
    CATEGORY_FOOTINGS: (BuiltInCategory.OST_StructuralFoundation,),
}

# Dimension-A label shown in the review window per category (Dimension-B is
# always "Height" for Doors/Windows, "H"/"Depth" for Columns/Beams, "Width"
# for Footings - the flow module derives that label from the category too).
DIMENSION_A_LABEL = {
    CATEGORY_DOORS: u"Width",
    CATEGORY_WINDOWS: u"Width",
    CATEGORY_COLUMNS: u"B",
    CATEGORY_BEAMS: u"B",
    CATEGORY_FOOTINGS: u"Length",
}
DIMENSION_B_LABEL = {
    CATEGORY_DOORS: u"Height",
    CATEGORY_WINDOWS: u"Height",
    CATEGORY_COLUMNS: u"H",
    CATEGORY_BEAMS: u"H",
    CATEGORY_FOOTINGS: u"Width",
}

_DOOR_WIDTH_BIPS = (u"DOOR_WIDTH", u"FAMILY_WIDTH_PARAM", u"GENERIC_WIDTH")
_DOOR_HEIGHT_BIPS = (u"DOOR_HEIGHT", u"FAMILY_HEIGHT_PARAM", u"GENERIC_HEIGHT")
_WINDOW_WIDTH_BIPS = (u"WINDOW_WIDTH", u"FAMILY_WIDTH_PARAM", u"GENERIC_WIDTH")
_WINDOW_HEIGHT_BIPS = (u"WINDOW_HEIGHT", u"FAMILY_HEIGHT_PARAM", u"GENERIC_HEIGHT")

# Candidate (b, h) display-name pairs across rectangular/I-shape structural
# families - same list lib/bkbim/automation/columns.py writes with, plus
# "bf"/"d" for I-shaped beam sections.
_COLUMN_BEAM_BH_PAIRS = [(u"b", u"h"), (u"Width", u"Depth"), (u"w", u"d"),
                         (u"B", u"H"), (u"Width", u"Height"), (u"bf", u"d")]

# Candidate (length, width) display-name pairs for footing families.
_FOOTING_LW_PAIRS = [(u"Length", u"Width"), (u"L", u"B"), (u"Width", u"Length")]

def _bip(name):
    return getattr(BuiltInParameter, name, None)


def _double_by_bip(element, bip_names):
    if element is None:
        return None
    for name in bip_names:
        bip = _bip(name)
        if bip is None:
            continue
        try:
            p = element.get_Parameter(bip)
            if p is not None:
                v = p.AsDouble()
                if v:
                    return v
        except Exception:
            continue
    return None


def _type_dim_bip_pair_mm(symbol, a_bips, b_bips):
    a_ft = _double_by_bip(symbol, a_bips)
    b_ft = _double_by_bip(symbol, b_bips)
    return (ft_to_mm(a_ft) if a_ft is not None else None,
            ft_to_mm(b_ft) if b_ft is not None else None)


def _lookup_pair_mm(symbol, name_pairs):
    for a_name, b_name in name_pairs:
        try:
            pa = symbol.LookupParameter(a_name)
            pb = symbol.LookupParameter(b_name)
        except Exception:
            continue
        if pa is None or pb is None:
            continue
        try:
            a_ft = pa.AsDouble()
            b_ft = pb.AsDouble()
        except Exception:
            continue
        return ft_to_mm(a_ft), ft_to_mm(b_ft)
    return None, None


_DIMENSION_READERS = {
    CATEGORY_DOORS: lambda symbol: _type_dim_bip_pair_mm(symbol, _DOOR_WIDTH_BIPS, _DOOR_HEIGHT_BIPS),
    CATEGORY_WINDOWS: lambda symbol: _type_dim_bip_pair_mm(symbol, _WINDOW_WIDTH_BIPS, _WINDOW_HEIGHT_BIPS),
    CATEGORY_COLUMNS: lambda symbol: _lookup_pair_mm(symbol, _COLUMN_BEAM_BH_PAIRS),
    CATEGORY_BEAMS: lambda symbol: _lookup_pair_mm(symbol, _COLUMN_BEAM_BH_PAIRS),
    CATEGORY_FOOTINGS: lambda symbol: _lookup_pair_mm(symbol, _FOOTING_LW_PAIRS),
}


def _host_wall_thickness_mm(elem):
    """Returns the host wall thickness in rounded millimeters when readable.

    Doors/windows normally expose a Wall as FamilyInstance.Host. Revit API
    versions and host conditions vary, so this tries the common direct Wall
    width first, then WallType.Width. Returning None groups unresolved hosts
    together without blocking Auto Mark.
    """
    try:
        host = elem.Host
    except Exception:
        host = None
    if host is None:
        return None

    try:
        width_ft = host.Width
        if width_ft:
            return int(round(ft_to_mm(width_ft)))
    except Exception:
        pass

    try:
        wall_type = host.WallType
        width_ft = wall_type.Width
        if width_ft:
            return int(round(ft_to_mm(width_ft)))
    except Exception:
        pass
    try:
        wall_type = elem.Document.GetElement(host.GetTypeId())
        width_ft = wall_type.Width
        if width_ft:
            return int(round(ft_to_mm(width_ft)))
    except Exception:
        pass
    return None


def _uses_host_wall_thickness(category):
    return category in (CATEGORY_DOORS, CATEGORY_WINDOWS)


# ---------------------------------------------------------------------------
# Reinforcement signatures (Columns/Beams/Footings only - Doors/Windows have
# no rebar concept, so they're simply absent from this dict; read_family_groups
# skips reinforcement-group computation entirely when a category has no
# reader). Read off the INSTANCE, not the type/symbol - two elements sharing
# a Revit type/section can carry genuinely different rebar (confirmed live,
# 2026-07-14 - e.g. all "200x500" columns share one FamilySymbol but split
# into 4 real reinforcement variants).
#
# THREE-TIER priority (product owner, 2026-07-14: "the export data isn't
# always correct... use the actual modelled rebar as the first option...
# if there are no modelled rebar, use tekla exported text and NVRebar
# settings... if both are empty, sort by size"): (1) real modeled Rebar
# elements hosted on the instance - most reliable, reflects what's
# actually built/drawn, not an export snapshot; (2) TSDI_RC_*/NVRebarSetting
# exported text (this project's actual Tekla Structural Designer export
# convention - a future non-Tekla source would need its own reader added
# here, same spirit as _COLUMN_BEAM_BH_PAIRS' candidate-name-list above);
# (3) empty signature, which naturally makes every instance of that type
# share one group - i.e. sorts by size alone, with no extra code needed for
# that fallback. Confirmed live only 23/103 columns and 34/68 footings
# actually have modeled rebar (beams: 0/161) - most elements still rely on
# tier 2, so the modeled-rebar signature functions deliberately emit the
# SAME token vocabulary as the text ones (see reinforcement_signature.py)
# so a modeled-rebar element and a text-only element of the truly
# identical real design still match instead of spuriously splitting.
# ---------------------------------------------------------------------------

def _pstr(elem, name):
    p = elem.LookupParameter(name)
    if p is None:
        return None
    try:
        return p.AsString()
    except Exception:
        return None


def _build_rebar_by_host(doc):
    """One collector pass for the whole document, bucketed by host element
    id - looking this up per-instance instead would mean one collector
    scan per column/beam/footing, needlessly expensive at real model scale.
    """
    by_host = {}
    for r in FilteredElementCollector(doc).OfClass(Rebar).ToElements():
        try:
            host_id = r.GetHostId()
        except Exception:
            host_id = None
        if host_id is None:
            continue
        by_host.setdefault(element_id_token(host_id), []).append(r)
    return by_host


def _rebar_diameter_mm(rebar, snap=1.0):
    p = rebar.LookupParameter(u"Bar Diameter")
    if p is None:
        return None
    try:
        return int(round(ft_to_mm(p.AsDouble()) / snap) * snap)
    except Exception:
        return None


def _rebar_spacing_mm(rebar, snap=5.0):
    try:
        return int(round(ft_to_mm(rebar.MaxSpacing) / snap) * snap)
    except Exception:
        return None


def _split_rebar_by_layout(rebar_list):
    """Real modeled rebar splits cleanly on LayoutRule, confirmed live
    against this project's actual data: FixedNumber sets are longitudinal
    main bars (their own bar COUNT is the meaningful design value - it
    doesn't depend on the host element's height/size); every other layout
    rule (MaximumSpacing seen live; MinimumClearSpacing/NumberWithSpacing
    not seen but grouped the same way) is a distributed set (stirrup/tie/
    mesh) whose own SPACING is the meaningful value, not its incidental
    instance count (which DOES depend on the host's height/size).

    Returns (main_bar_groups, distributed_groups), each a list of
    (diameter_mm, value) - value is quantity for main bars, spacing_mm for
    distributed sets. Entries with no readable diameter are skipped.
    """
    main_bar_groups = []
    distributed_groups = []
    for r in rebar_list:
        dia = _rebar_diameter_mm(r)
        if dia is None:
            continue
        try:
            is_fixed_number = r.LayoutRule == RebarLayoutRule.FixedNumber
        except Exception:
            is_fixed_number = False
        if is_fixed_number:
            try:
                qty = r.Quantity
            except Exception:
                qty = None
            if qty:
                main_bar_groups.append((dia, qty))
        else:
            spacing = _rebar_spacing_mm(r)
            if spacing:
                distributed_groups.append((dia, spacing))
    return main_bar_groups, distributed_groups


def _column_reinforcement(elem, rebar_by_host):
    """Returns (signature, source_label) - source_label is one of
    reinforcement_signature.SOURCE_* (product owner, 2026-07-15: "make me
    notice that difference when marking" - surfaced in AutoMarkOptions'
    preview via MarkReinforcementGroup.sources).
    """
    hosted = rebar_by_host.get(element_id_token(elem.Id))
    if hosted:
        main_bar_groups, link_groups = _split_rebar_by_layout(hosted)
        modeled = modeled_column_signature(main_bar_groups, link_groups)
        if modeled.strip(u" |"):
            return modeled, SOURCE_MODELED_REBAR
    text_sig = column_signature(_pstr(elem, u"TSDI_RC_Bars"), _pstr(elem, u"TSDI_RC_Links"))
    if text_sig.strip(u" |"):
        return text_sig, SOURCE_TEKLA_TEXT
    return u"", SOURCE_NONE


def _beam_reinforcement(elem, rebar_by_host):
    # No beam ever has modeled rebar in this project (confirmed live,
    # 0/161) - text is the only tier available for beams today. Kept as
    # its own function (not sharing _column_reinforcement) so adding real
    # modeled beam rebar later is a self-contained change.
    text_sig = beam_signature(_pstr(elem, u"TSDI_RC_Top"), _pstr(elem, u"TSDI_RC_Bottom"), _pstr(elem, u"TSDI_RC_Links"))
    if text_sig.strip(u" |"):
        return text_sig, SOURCE_TEKLA_TEXT
    return u"", SOURCE_NONE


def _footing_reinforcement(elem, rebar_by_host):
    hosted = rebar_by_host.get(element_id_token(elem.Id))
    if hosted:
        _main_bar_groups, mesh_groups = _split_rebar_by_layout(hosted)
        modeled = modeled_footing_signature(mesh_groups)
        if modeled:
            return modeled, SOURCE_MODELED_REBAR
    text_sig = footing_signature(_pstr(elem, u"NVRebarSetting"))
    if text_sig:
        return text_sig, SOURCE_NAVIATE_TEXT
    return u"", SOURCE_NONE


_REINFORCEMENT_READERS = {
    CATEGORY_COLUMNS: _column_reinforcement,
    CATEGORY_BEAMS: _beam_reinforcement,
    CATEGORY_FOOTINGS: _footing_reinforcement,
}


def category_supports_reinforcement(category):
    """True for Columns/Beams/Footings - the categories that can carry a
    per-instance rebar signature. False for Doors/Windows, so callers (the
    options window) know to hide the size-only/size+reinforcement toggle
    entirely rather than showing a mode with no effect.
    """
    return category in _REINFORCEMENT_READERS


def _family_name(symbol, fallback=u"Unnamed Family"):
    try:
        name = symbol.Family.Name
        if name:
            return name
    except Exception:
        pass
    return fallback


_PCC_BLINDING_TYPE_MARK = u"PCC Blinding"


def _is_pcc_blinding_pad(symbol):
    """PCC Blinding pads (bkbim.automation.blinding) share the Structural
    Foundation category with real footings but aren't a structural element
    to number - excluded from Footings marking (product owner, 2026-07-14:
    "exclude PCC Blinding pads from Auto Mark -> Footings") so Auto Mark
    never overwrites the PCC Blinding tool's own "PCC-<footing mark>" sync
    (see hooks/doc-changed.py) with a plain "F#" mark. Not re-imported from
    automation.blinding.is_blinding_pad - this adapter module doesn't
    otherwise depend on the automation layer, and the check itself is a
    2-line duplicate, same tolerance this codebase already has for small
    per-module helpers (e.g. every automation/*.py has its own _name()).
    """
    try:
        tm = symbol.LookupParameter(u"Type Mark")
        return tm is not None and tm.AsString() == _PCC_BLINDING_TYPE_MARK
    except Exception:
        return False


def read_family_groups(doc, category, split_by_host_thickness=None):
    """Every family+type of `category` with at least one placed instance,
    grouped as MarkFamilyGroup -> MarkTypeGroup, each holding the ElementIds
    of every instance of that type (every one of which will get the same
    mark - see mark_planner.py).

    :param split_by_host_thickness: for Doors/Windows, True keeps the current
        A/B wall-thickness variants; False restores legacy same-type/same-size
        marking regardless of host wall thickness. None uses the category
        default.
    :rtype: list of bkbim.domain.models.mark_family_group.MarkFamilyGroup
    """
    dimension_reader = _DIMENSION_READERS[category]
    reinforcement_reader = _REINFORCEMENT_READERS.get(category)
    # One doc-wide collector pass, reused for every element - looking this
    # up per-instance would mean one Rebar collector scan per column/beam/
    # footing, needlessly expensive at real model scale.
    rebar_by_host = _build_rebar_by_host(doc) if reinforcement_reader is not None else {}

    if split_by_host_thickness is None:
        split_by_host_thickness = _uses_host_wall_thickness(category)
    else:
        split_by_host_thickness = bool(split_by_host_thickness) and _uses_host_wall_thickness(category)
    elements_by_group_key = {}
    symbol_by_group_key = {}
    host_thickness_by_group_key = {}
    for built_in_category in CATEGORY_BUILTIN_CATEGORIES[category]:
        collected = (FilteredElementCollector(doc).OfCategory(built_in_category)
                     .WhereElementIsNotElementType().ToElements())
        for elem in collected:
            if not isinstance(elem, FamilyInstance):
                continue
            symbol = elem.Symbol
            if symbol is None:
                continue
            if category == CATEGORY_FOOTINGS and _is_pcc_blinding_pad(symbol):
                continue
            symbol_key = element_id_token(symbol.Id)
            host_thickness_mm = _host_wall_thickness_mm(elem) if split_by_host_thickness else None
            key = (symbol_key, host_thickness_mm) if split_by_host_thickness else symbol_key
            symbol_by_group_key[key] = symbol
            host_thickness_by_group_key[key] = host_thickness_mm
            elements_by_group_key.setdefault(key, []).append(elem)

    families = {}
    for key, elements in elements_by_group_key.items():
        symbol = symbol_by_group_key[key]
        family_name = _family_name(symbol)
        dimension_a_mm, dimension_b_mm = dimension_reader(symbol)
        host_thickness_mm = host_thickness_by_group_key.get(key)

        reinforcement_groups = None
        if reinforcement_reader is not None:
            refs_by_signature = {}
            sources_by_signature = {}
            signature_order = []
            for elem in elements:
                try:
                    signature, source = reinforcement_reader(elem, rebar_by_host)
                    signature = signature or u""
                except Exception:
                    signature, source = u"", SOURCE_NONE
                if signature not in refs_by_signature:
                    refs_by_signature[signature] = []
                    sources_by_signature[signature] = []
                    signature_order.append(signature)
                refs_by_signature[signature].append(elem.Id)
                if source not in sources_by_signature[signature]:
                    sources_by_signature[signature].append(source)
            reinforcement_groups = [
                MarkReinforcementGroup(sig, refs_by_signature[sig], sources=sources_by_signature[sig])
                for sig in signature_order]

        type_group = MarkTypeGroup(
            type_name=type_name(symbol), dimension_a_mm=dimension_a_mm,
            dimension_b_mm=dimension_b_mm,
            instance_refs=[elem.Id for elem in elements],
            reinforcement_groups=reinforcement_groups,
            host_thickness_mm=host_thickness_mm)
        families.setdefault(family_name, []).append(type_group)

    return [MarkFamilyGroup(name, groups) for name, groups in families.items()]
