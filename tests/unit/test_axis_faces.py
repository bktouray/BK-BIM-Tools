# -*- coding: utf-8 -*-
from bkbim.domain.models.axis_faces import AxisFaces


def test_holds_fields_as_given():
    af = AxisFaces(ref_lo="lo-ref", ref_hi="hi-ref", coord_lo=0.0, coord_hi=10.0)
    assert af.ref_lo == "lo-ref"
    assert af.ref_hi == "hi-ref"
    assert af.coord_lo == 0.0
    assert af.coord_hi == 10.0
