# -*- coding: utf-8 -*-
"""Detects whether a planned dimension already exists in the view, so re-running a
dimensioning command is safe to use as an "update" - only add what's missing,
never create overlapping duplicates (product owner feedback 2026-07-05).

Matches on the planned dimension's two ENDPOINT references (the overall span),
not its full internal reference set - deliberately: if a model change adds a new
opening inside an already-dimensioned span, this still counts the span as already
handled rather than trying to detect "did the content change," matching what was
asked for ("if there's a dimension already placed, skip it").

Verified live 2026-07-05: a freshly-written dimension's own references produce
byte-identical stable-representation keys to the plan that created it, and this
holds even for dimensions queried within the same (uncommitted) transaction that
created them.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import Dimension, FilteredElementCollector

from bkbim.domain.dimensioning.ports import IExistingDimensionChecker
from bkbim.revit.adapter.stable_representation import reference_stable_key


class RevitExistingDimensionChecker(IExistingDimensionChecker):
    def __init__(self, doc, view):
        self._doc = doc
        self._view = view
        self._existing_key_sets = None  # lazy-loaded, cached for the whole run

    def already_exists(self, plan):
        if not plan.refs:
            return False

        try:
            endpoint_keys = set([
                reference_stable_key(self._doc, plan.refs[0]),
                reference_stable_key(self._doc, plan.refs[-1]),
            ])
        except Exception:
            return False

        for existing_keys in self._load_existing_key_sets():
            if endpoint_keys.issubset(existing_keys):
                return True
        return False

    def _load_existing_key_sets(self):
        if self._existing_key_sets is not None:
            return self._existing_key_sets

        key_sets = []
        dims = FilteredElementCollector(self._doc, self._view.Id).OfClass(Dimension).ToElements()
        for dim in dims:
            try:
                refs = dim.References
                if refs is None or refs.Size == 0:
                    continue
                keys = set()
                for ref in refs:
                    keys.add(reference_stable_key(self._doc, ref))
                key_sets.append(keys)
            except Exception:
                continue

        self._existing_key_sets = key_sets
        return key_sets
