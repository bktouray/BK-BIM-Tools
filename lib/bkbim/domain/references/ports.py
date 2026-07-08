# -*- coding: utf-8 -*-
"""Reference resolution port (SAD Sec 4.2, PHASE_1_PLAN Sec 3).

Implemented by bkbim.revit.adapter.reference_provider.RevitReferenceProvider.
Domain/app code depends on this interface only - never on Revit types directly
(ADR-0001 dependency-inversion seam, same pattern as domain.ports.IElementReader).
"""


class IReferenceProvider(object):
    def faces_for(self, element_ref, axis):
        """Returns an AxisFaces for `element_ref` along `axis` ("x" | "y"), or None
        if fewer than two matching faces are found.

        :rtype: bkbim.domain.models.axis_faces.AxisFaces
        """
        raise NotImplementedError

    def grid_reference(self, grid_ref):
        """Returns an opaque reference handle for `grid_ref`, or None if unavailable."""
        raise NotImplementedError

    def outline_edges_for(self, element_ref):
        """Returns list[OutlineEdge] for `element_ref`'s real boundary - every
        straight, axis-aligned side face, not just the two extreme faces per
        axis (contrast with `faces_for`). Used for true perimeter tracing on
        non-rectangular (notched/stepped) footprints. Curved/diagonal side
        faces are skipped, not guessed at - same axis-aligned-only scope as
        the rest of this port.

        :rtype: list[bkbim.domain.models.outline_edge.OutlineEdge]
        """
        raise NotImplementedError
