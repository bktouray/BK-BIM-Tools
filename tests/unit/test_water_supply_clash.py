# -*- coding: utf-8 -*-
from bkbim.domain.mep.routing.water_supply_clash import detect_hot_cold_clashes


def _segment(system, start, end, label=u"s1"):
    return {
        "system": system,
        "kind": u"generated",
        "label": label,
        "start": start,
        "end": end,
        "diameter_mm": 25,
    }


def test_detects_overlapping_hot_and_cold_horizontal_runs():
    cold = [_segment(u"Cold Water", (0, 0, 2400), (1000, 0, 2400), u"cold feed")]
    hot = [_segment(u"Hot Water", (500, 0, 2400), (1500, 0, 2400), u"hot feed")]

    diagnostics = detect_hot_cold_clashes(cold, hot)

    assert diagnostics
    assert u"overlap" in diagnostics[0]


def test_detects_crossing_hot_and_cold_runs_at_same_elevation():
    cold = [_segment(u"Cold Water", (0, 500, 2400), (1000, 500, 2400))]
    hot = [_segment(u"Hot Water", (500, 0, 2400), (500, 1000, 2400))]

    diagnostics = detect_hot_cold_clashes(cold, hot)

    assert diagnostics
    assert u"cross" in diagnostics[0]


def test_detects_overlapping_vertical_risers():
    cold = [_segment(u"Cold Water", (100, 200, 200), (100, 200, 2400))]
    hot = [_segment(u"Hot Water", (100, 200, 1800), (100, 200, 2500))]

    diagnostics = detect_hot_cold_clashes(cold, hot)

    assert diagnostics
    assert u"vertical risers overlap" in diagnostics[0]


def test_separated_hot_and_cold_routes_do_not_clash():
    cold = [_segment(u"Cold Water", (0, 0, 2400), (1000, 0, 2400))]
    hot = [_segment(u"Hot Water", (0, 50, 2450), (1000, 50, 2450))]

    assert detect_hot_cold_clashes(cold, hot) == []


def test_detects_vertical_riser_crossing_horizontal_run():
    cold = [_segment(u"Cold Water", (500, 0, 200), (500, 0, 2500))]
    hot = [_segment(u"Hot Water", (0, 0, 1800), (1000, 0, 1800))]

    diagnostics = detect_hot_cold_clashes(cold, hot)

    assert diagnostics
    assert u"vertical riser crosses" in diagnostics[0]
