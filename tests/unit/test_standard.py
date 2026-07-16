# -*- coding: utf-8 -*-
from bkbim.domain.standards.standard import Standard, default_standard


def test_default_standard_has_a_name():
    std = default_standard()
    assert std.name == u"Default"


def test_custom_standard_overrides_fields():
    std = Standard(name=u"BS", offset_first_mm=750.0, collision_max_passes=5)
    assert std.name == u"BS"
    assert std.offset_first_mm == 750.0
    assert std.collision_max_passes == 5
    # Untouched fields keep their defaults
    assert std.wall_perimeter_gap_mm == 700.0


def test_two_standards_are_independent():
    a = Standard(name=u"A", offset_first_mm=100.0)
    b = Standard(name=u"B", offset_first_mm=200.0)
    assert a.offset_first_mm == 100.0
    assert b.offset_first_mm == 200.0


def test_default_side_defaults_to_below_left():
    std = default_standard()
    assert std.default_side == -1


def test_default_side_is_overridable():
    std = Standard(name=u"Flipped", default_side=1)
    assert std.default_side == 1


def test_to_dict_round_trips_through_from_dict():
    original = default_standard()
    restored = Standard.from_dict(original.to_dict())

    assert restored.name == original.name
    assert restored.offset_first_mm == original.offset_first_mm
    assert restored.mep_valve_height_mm == original.mep_valve_height_mm
    assert restored.mep_wall_penetration_mm == original.mep_wall_penetration_mm
    assert restored.mep_hot_cold_spacing_mm == original.mep_hot_cold_spacing_mm
    assert restored.mep_max_branch_length_mm == original.mep_max_branch_length_mm
    assert restored.mep_frequency_factor_by_usage == original.mep_frequency_factor_by_usage
    assert restored.mep_min_slope_table_percent == original.mep_min_slope_table_percent


def test_to_dict_converts_tuple_tables_to_lists_for_json():
    data = default_standard().to_dict()
    assert isinstance(data[u"mep_min_slope_table_percent"], list)
    assert isinstance(data[u"mep_min_slope_table_percent"][0], list)


def test_from_dict_survives_json_round_trip_with_unicode_keys():
    # The real-world case this exists for: json.load() always returns
    # unicode keys under IronPython 2.7/Python 2 - from_dict must not choke
    # on that (it must not use cls(**data) internally).
    import json
    data = json.loads(json.dumps(default_standard().to_dict()))
    restored = Standard.from_dict(data)
    assert restored.offset_first_mm == 300.0
    assert restored.mep_min_slope_table_percent[0] == (75, 2.5)


def test_from_dict_with_missing_keys_falls_back_to_defaults():
    restored = Standard.from_dict({u"name": u"Partial", u"offset_first_mm": 999.0})
    assert restored.name == u"Partial"
    assert restored.offset_first_mm == 999.0
    assert restored.wall_perimeter_gap_mm == 700.0  # untouched, falls back


def test_from_dict_with_empty_dict_matches_default_standard():
    restored = Standard.from_dict({})
    assert restored.name == u"Default"
    assert restored.offset_first_mm == default_standard().offset_first_mm


def test_validate_default_standard_has_no_errors():
    assert default_standard().validate() == []


def test_validate_rejects_non_positive_offset():
    std = Standard(name=u"Bad", offset_first_mm=0)
    errors = std.validate()
    assert len(errors) == 1
    assert u"Dimension offset" in errors[0]


def test_validate_rejects_negative_gap():
    std = Standard(name=u"Bad", wall_perimeter_gap_mm=-50.0)
    errors = std.validate()
    assert any(u"Wall perimeter gap" in e for e in errors)


def test_validate_rejects_non_positive_valve_height():
    std = Standard(name=u"Bad", mep_valve_height_mm=0)
    errors = std.validate()
    assert any(u"MEP valve height" in e for e in errors)


def test_validate_rejects_non_positive_wall_penetration():
    std = Standard(name=u"Bad", mep_wall_penetration_mm=0)
    errors = std.validate()
    assert any(u"MEP wall penetration" in e for e in errors)


def test_validate_rejects_non_positive_hot_cold_spacing():
    std = Standard(name=u"Bad", mep_hot_cold_spacing_mm=0)
    errors = std.validate()
    assert any(u"MEP hot/cold spacing" in e for e in errors)


def test_validate_rejects_non_positive_optional_max_branch_length():
    std = Standard(name=u"Bad", mep_max_branch_length_mm=-1)
    errors = std.validate()
    assert any(u"maximum branch length" in e for e in errors)


def test_validate_rejects_frequency_factor_out_of_range():
    std = Standard(name=u"Bad", mep_frequency_factor_by_usage={u"intermittent": 3.0})
    errors = std.validate()
    assert any(u"frequency factor" in e for e in errors)


def test_validate_rejects_non_positive_discharge_units():
    std = Standard(name=u"Bad", mep_discharge_units_by_fixture_type={u"WC": -1.0})
    errors = std.validate()
    assert any(u"discharge units" in e for e in errors)


def test_validate_rejects_min_slope_out_of_range():
    std = Standard(name=u"Bad", mep_min_slope_table_percent=[(75, 150.0)])
    errors = std.validate()
    assert any(u"min slope" in e for e in errors)


def test_validate_rejects_max_slope_out_of_range():
    std = Standard(name=u"Bad", mep_max_slope_percent=150.0)
    errors = std.validate()
    assert any(u"max slope should be" in e for e in errors)


def test_validate_rejects_max_slope_not_greater_than_min_slope():
    std = Standard(name=u"Bad", mep_min_slope_table_percent=[(75, 5.0)], mep_max_slope_percent=2.0)
    errors = std.validate()
    assert any(u"must be greater than every configured min slope" in e for e in errors)


def test_validate_accepts_valid_max_slope_above_min_slope():
    std = Standard(name=u"OK", mep_min_slope_table_percent=[(75, 2.5)], mep_max_slope_percent=10.0)
    assert std.validate() == []


def test_validate_rejects_non_positive_pipe_capacity():
    std = Standard(name=u"Bad", mep_pipe_capacity_table_du=[(50, -1.0)])
    errors = std.validate()
    assert any(u"pipe capacity" in e for e in errors)


def test_validate_reports_multiple_errors_at_once():
    std = Standard(name=u"VeryBad", offset_first_mm=0, mep_valve_height_mm=-1)
    errors = std.validate()
    assert len(errors) == 2
