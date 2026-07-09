# -*- coding: utf-8 -*-
"""Ports for the Auto Tag use-case (SAD Sec 4.2/4.4). Pure interfaces - no
Revit types (ADR-0001) - implemented by classes in bkbim.revit.adapter.
"""


class IAlreadyTaggedChecker(object):
    """Detects whether an element already has a tag of the run's chosen tag
    category in the target view, so re-running Auto Tag is safe to use as an
    "update" - only tag what's missing, never pile up duplicate tags (same
    "skip if already placed" convention the dimensioning tools use).

    Implemented by bkbim.revit.adapter.already_tagged_checker.RevitAlreadyTaggedChecker.
    """

    def is_tagged(self, element):
        raise NotImplementedError


class ITagWriter(object):
    """Places a tag on one element.

    Implemented by bkbim.revit.adapter.tag_writer.RevitTagWriter.
    """

    def write(self, element):
        """Returns an opaque handle to the created tag, or None if refused."""
        raise NotImplementedError
