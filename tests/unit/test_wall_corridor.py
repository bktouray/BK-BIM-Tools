# -*- coding: utf-8 -*-
import sys
import types


clr = types.ModuleType("clr")
clr.AddReference = lambda *args, **kwargs: None
sys.modules.setdefault("clr", clr)

from bkbim.revit.adapter.mep.wall_corridor import (
    _corridor_path_from_wall_network, _fixture_corridor_path_from_wall_network)


def test_wall_network_uses_intersections_without_split_walls():
    segments = [
        ((-1000.0, 0.0, -150.0), (3000.0, 0.0, -150.0)),
        ((1000.0, -1000.0, -150.0), (1000.0, 3000.0, -150.0)),
        ((1000.0, 2000.0, -150.0), (3000.0, 2000.0, -150.0)),
    ]

    path = _corridor_path_from_wall_network(
        segments,
        (0.0, 100.0, -150.0),
        [(900.0, 1500.0, 500.0), (2500.0, 2100.0, 500.0)])

    assert path == [
        (0.0, 0.0, -150.0),
        (1000.0, 0.0, -150.0),
        (1000.0, 1500.0, -150.0),
        (1000.0, 2000.0, -150.0),
        (2500.0, 2000.0, -150.0),
    ]


def test_wall_network_rejects_branching_fixture_paths():
    segments = [
        ((-1000.0, 0.0, -150.0), (3000.0, 0.0, -150.0)),
        ((1000.0, -1000.0, -150.0), (1000.0, 3000.0, -150.0)),
    ]

    try:
        _corridor_path_from_wall_network(
            segments,
            (1000.0, 0.0, -150.0),
            [(1000.0, -800.0, 500.0), (1000.0, 2500.0, 500.0)])
        assert False, "expected ValueError"
    except ValueError as error:
        assert u"branching" in str(error)


def test_wall_network_allows_valve_far_from_fixture_corridor():
    segments = [
        ((0.0, 0.0, -150.0), (0.0, 4000.0, -150.0)),
        ((0.0, 0.0, -150.0), (3000.0, 0.0, -150.0)),
    ]

    path = _corridor_path_from_wall_network(
        segments,
        (3500.0, 3000.0, -150.0),
        [(100.0, 800.0, 500.0), (100.0, 3000.0, 500.0)])

    assert path == [
        (3000.0, 0.0, -150.0),
        (0.0, 0.0, -150.0),
        (0.0, 800.0, -150.0),
        (0.0, 3000.0, -150.0),
    ]


def test_direct_feed_fixture_corridor_ignores_remote_valve_wall_perimeter():
    segments = [
        ((0.0, 0.0, -150.0), (0.0, 4000.0, -150.0)),
        ((0.0, 0.0, -150.0), (3000.0, 0.0, -150.0)),
    ]

    path = _fixture_corridor_path_from_wall_network(
        segments,
        (3500.0, 3000.0, -150.0),
        [(100.0, 800.0, 500.0), (100.0, 3000.0, 500.0)])

    assert path == [
        (0.0, 3000.0, -150.0),
        (0.0, 800.0, -150.0),
    ]
