# -*- coding: utf-8 -*-
"""Ports specific to the Auto Dimension use-case (SAD Sec 4.2/4.4). Pure interfaces -
no Revit types (ADR-0001) - implemented by classes in bkbim.revit.adapter.
"""


class ISelectionReader(object):
    """Classifies a pre-picked list of Revit elements/grids into domain models.

    Implemented by bkbim.revit.adapter.selection_reader.RevitSelectionReader. The
    interactive box-select prompt itself is a UI concern and lives in the pushbutton
    entry point, not here.
    """

    def read(self, selected_elements):
        """Returns (elements, grids): (list[ElementInfo], list[GridInfo])."""
        raise NotImplementedError


class IDimensionWriter(object):
    """Writes a DimensionPlan as a real dimension.

    Implemented by bkbim.revit.adapter.dimension_writer.DimensionWriter.
    """

    def write(self, plan):
        """Returns an opaque handle to the created dimension, or None if refused."""
        raise NotImplementedError


class IFailureTracker(object):
    """Tracks which elements this command run created, so a scoped failure policy
    can safely delete only those if Revit reports an error creating them.

    Implemented by bkbim.revit.adapter.failure_policy.ScopedFailurePolicy.
    """

    def register_created(self, element_id):
        raise NotImplementedError


class IWallRunReader(object):
    """Resolves a wall's own end references plus its hosted openings' jamb
    references, for wall-run dimensioning (PHASE_1_PLAN follow-up, 2026-07-05).

    Jamb references MUST come from the wall's own cut geometry, not the door/window
    family's geometry - validated live: family geometry gave an imprecise frame
    extent that did not match the door's actual width parameter, while the wall's
    own reveal faces matched it exactly.

    Implemented by bkbim.revit.adapter.reference_provider.RevitReferenceProvider.
    """

    def wall_run_faces(self, wall_ref, length_axis, opening_locations):
        """Returns (wall_axis_faces, opening_axis_faces_list).

        wall_ref: opaque wall handle.
        length_axis: "x" | "y" - the wall's own length direction.
        opening_locations: list[float] - each hosted opening's coordinate along
                            length_axis (e.g. its bounding-box center), used to
                            match it to the correct pair of wall reveal faces.

        wall_axis_faces: AxisFaces for the wall's own two end references, or None
                         if the wall's geometry couldn't be read.
        opening_axis_faces_list: one entry per `opening_locations`, in the same
                                 order - an AxisFaces if a confident match was
                                 found, else None (never a guess).
        """
        raise NotImplementedError


class IExistingDimensionChecker(object):
    """Detects whether a planned dimension already exists in the view, so
    re-running a dimensioning command doesn't create overlapping duplicates
    (product owner feedback 2026-07-05: skip a location that's already
    dimensioned instead of redoing everything, so re-running is safe to use as
    an "update" - only add what's missing).

    Implemented by bkbim.revit.adapter.existing_dimension_checker.RevitExistingDimensionChecker.
    """

    def already_exists(self, plan):
        """Returns True if an existing dimension already covers this plan's span
        (matches its endpoint references), else False.
        """
        raise NotImplementedError
