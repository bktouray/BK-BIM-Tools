# -*- coding: utf-8 -*-
"""Revit 2026 (build 2026.4) API quirk isolation (SAD Sec 4.3, ADR-0003 versioning).

Stubbed for Phase 0. Populated in Phase 1 when real version-sensitive code is ported
from the AutoDims monolith - e.g. ElementId.Value vs .IntegerValue,
Element.Name.GetValue vs .Name - so a future revit2027.py can diverge without
touching the adapter call sites.
"""
