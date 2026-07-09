# -*- coding: utf-8 -*-
"""Detects whether an element already has an IndependentTag in the view, so
re-running Auto Tag is safe to use as an "update" - only tag what's missing,
same "skip if already placed" convention existing_dimension_checker.py uses
for dimensions.

GetTaggedLocalElementIds() (Revit 2022+) returns every element ID a tag
covers - a multi-category/multi-reference tag can cover more than one, so
this collects the full set rather than assuming one tag <-> one element.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import FilteredElementCollector, IndependentTag

from bkbim.domain.tagging.ports import IAlreadyTaggedChecker
from bkbim.revit.adapter.stable_representation import element_id_token


class RevitAlreadyTaggedChecker(IAlreadyTaggedChecker):
    def __init__(self, doc, view):
        self._doc = doc
        self._view = view
        self._tagged_id_tokens = None  # lazy-loaded, cached for the whole run

    def is_tagged(self, element):
        return element_id_token(element.Id) in self._load_tagged_id_tokens()

    def _load_tagged_id_tokens(self):
        if self._tagged_id_tokens is not None:
            return self._tagged_id_tokens

        tokens = set()
        tags = FilteredElementCollector(self._doc, self._view.Id).OfClass(IndependentTag).ToElements()
        for tag in tags:
            try:
                tagged_ids = tag.GetTaggedLocalElementIds()
            except Exception:
                continue
            for tagged_id in tagged_ids:
                tokens.add(element_id_token(tagged_id))

        self._tagged_id_tokens = tokens
        return tokens
