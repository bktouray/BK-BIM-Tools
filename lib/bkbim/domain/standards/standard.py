# -*- coding: utf-8 -*-
"""Named profile of dimensioning offsets/tolerances.

Replaces the AutoDims v5 script's module-level constants (OFFSET_1_MM, ZERO_TOL_MM,
...) with per-Standard fields, so BS/ISO/AIA/custom profiles are data, not code
(PHASE_1_PLAN Sec 3). Default values below are a reasonable starting point carried
over as plain numbers - not verified against any published standard - flag for
review before Phase 3 (Standards + Presets GA).
"""


class Standard(object):
    def __init__(self, name,
                 offset_first_mm=300.0,
                 wall_perimeter_gap_mm=700.0,
                 grid_chain_offset_mm=300.0,
                 grid_chain_gap_mm=700.0,
                 structural_chain_offset_mm=300.0,
                 structural_chain_gap_mm=700.0,
                 zero_tolerance_mm=5.0,
                 intersect_tolerance_mm=50.0,
                 max_snap_distance_mm=10000.0,
                 collision_shift_mm=300.0,
                 collision_max_passes=3,
                 default_side=-1,
                 mep_frequency_factor_by_usage=None,
                 mep_discharge_units_by_fixture_type=None,
                 mep_min_slope_table_percent=None,
                 mep_max_slope_percent=None,
                 mep_pipe_capacity_table_du=None,
                 mep_default_pipe_material=u"uPVC",
                 mep_default_pipe_type_name=None,
                 mep_valve_height_mm=1800.0):
        self.name = name
        self.offset_first_mm = offset_first_mm
        # Spacing between each of an exterior wall's 3 perimeter dimension
        # strings (2026-07-07) - was the long-unused "offset_second_mm"
        # reserved field, finally given a real purpose. Applied twice: once
        # between String 1 (openings) and String 2 (perpendicular walls),
        # again between String 2 and String 3 (overall). Default lowered
        # from the original 1400mm same day - product owner tried it live
        # and found that "wayyy too much gap"; also now user-adjustable per
        # run via the options window, not just this code-level default.
        self.wall_perimeter_gap_mm = wall_perimeter_gap_mm
        self.grid_chain_offset_mm = grid_chain_offset_mm
        self.grid_chain_gap_mm = grid_chain_gap_mm
        # Auto Dimension for Structural Elements (2026-07-06): kept independent
        # of grid_chain_offset/gap so tuning Grid Dimensions' spacing never
        # silently changes column/footing dimension spacing, and vice versa.
        self.structural_chain_offset_mm = structural_chain_offset_mm
        self.structural_chain_gap_mm = structural_chain_gap_mm
        self.zero_tolerance_mm = zero_tolerance_mm
        self.intersect_tolerance_mm = intersect_tolerance_mm
        self.max_snap_distance_mm = max_snap_distance_mm
        self.collision_shift_mm = collision_shift_mm
        self.collision_max_passes = collision_max_passes
        # Phase 1 Stage 3 keeps side-picking deliberately non-clever: every
        # dimension goes on this fixed side (-1 = below/left, +1 = above/right).
        # v5's per-element side-picking heuristic is not carried over; revisit only
        # if simple fixed-side placement proves wrong in practice.
        self.default_side = default_side

        # --- MEP (2026-07-09, ADR-0004 / MEP_SAD.md Sec 4) ---
        # BS EN 12056-2 sizing shape: total flow Qww = K * sqrt(sum(discharge
        # units)), K = frequency factor by usage pattern, then a pipe capacity
        # table gives the smallest DN whose flow capacity >= Qww at the run's
        # actual slope. This is the real EN 12056-2 method (discharge units in
        # L/s + frequency factor), not a flat US-style DFU-to-pipe-size lookup.
        #
        # WARNING: the *shape* of this calculation is correct; the *numbers*
        # below (discharge units per fixture, min slopes, capacity table) are
        # typical published/rule-of-thumb figures carried over from general
        # professional reference, NOT transcribed from the BS EN 12056-2 text
        # itself or verified against a national annex. Same status as this
        # file's pre-existing dimensioning defaults ("un-validated placeholder
        # - review before Phase 3"). Do not trust these for a real sizing run
        # until checked against the actual standard document or the office's
        # own reference drawings.
        self.mep_frequency_factor_by_usage = mep_frequency_factor_by_usage or {
            u"intermittent": 0.5,  # dwellings, guest houses, offices
            u"regular": 0.7,       # hospitals, schools, restaurants, hotels
            u"frequent": 1.0,      # public toilets
            u"special": 1.2,       # laboratories, industrial
        }
        self.mep_discharge_units_by_fixture_type = mep_discharge_units_by_fixture_type or {
            u"WC": 2.0,
            u"WashBasin": 0.5,
            u"Bidet": 0.3,
            u"Shower": 0.6,
            u"Bath": 0.8,
            u"KitchenSink": 0.8,
            u"WashingMachine": 0.8,
            u"Dishwasher": 0.8,
            u"FloorGully50": 0.8,
            u"FloorGully100": 1.5,
        }
        # (max_dn_mm, min_slope_percent) pairs, smallest DN first. Rule-of-thumb
        # UK domestic guidance shape (Approved Document H style), not the full
        # EN 12056-2 Colebrook-White capacity derivation - flagged above.
        self.mep_min_slope_table_percent = mep_min_slope_table_percent or [
            (75, 2.5),
            (100, 1.25),
            (150, 1.0),
        ]
        # No practical maximum enforced by default (a steep gravity run is
        # usually fine hydraulically); set explicitly per-project if the
        # office wants to cap it (e.g. to avoid trap-seal loss on branches).
        self.mep_max_slope_percent = mep_max_slope_percent
        # (dn_mm, max_total_discharge_units) pairs, smallest DN first - a DU-
        # indexed simplification of EN 12056-2's flow-based capacity method,
        # matching how common domestic branch/stack sizing references are
        # actually published for simple jobs. DN progression (50/75/100/150mm)
        # is standard UK domestic drainage practice; the DU cutoffs themselves
        # are illustrative placeholders - same "verify before trusting" flag
        # as every other mep_* field above.
        self.mep_pipe_capacity_table_du = mep_pipe_capacity_table_du or [
            (50, 1.0),
            (75, 4.0),
            (100, 8.0),
            (150, 30.0),
        ]
        self.mep_default_pipe_material = mep_default_pipe_material
        # Must be set to a real Revit PipeType name before RevitPipeWriter can
        # run (MEP_SAD.md Sec 6) - None deliberately, not guessed.
        self.mep_default_pipe_type_name = mep_default_pipe_type_name
        # Water Supply (2026-07-10, ADR-0004 pivot: Sanitary Drainage paused,
        # Water Supply is now the active slice). UNLIKE every other mep_*
        # default above, this is a real, product-owner-confirmed office
        # convention, not a placeholder needing verification: every valve
        # (shower mixer, isolation valve, etc.) sits at 1800mm above its
        # level. Used as the target elevation for a wall-routed vertical leg
        # in RoutingStyle.IN_WALL/CEILING_DROP/FLOOR_RISE when the target is
        # a valve rather than a fixture's own connector.
        self.mep_valve_height_mm = mep_valve_height_mm

    def __repr__(self):
        return u"<Standard {0}>".format(self.name)

    def to_dict(self):
        """Plain JSON-serializable dict - round-trips via from_dict(). Field
        names match the constructor kwargs 1:1 so nothing needs remapping.
        Tuple-valued table fields are converted to lists since JSON has no
        tuple type."""
        return {
            u"name": self.name,
            u"offset_first_mm": self.offset_first_mm,
            u"wall_perimeter_gap_mm": self.wall_perimeter_gap_mm,
            u"grid_chain_offset_mm": self.grid_chain_offset_mm,
            u"grid_chain_gap_mm": self.grid_chain_gap_mm,
            u"structural_chain_offset_mm": self.structural_chain_offset_mm,
            u"structural_chain_gap_mm": self.structural_chain_gap_mm,
            u"zero_tolerance_mm": self.zero_tolerance_mm,
            u"intersect_tolerance_mm": self.intersect_tolerance_mm,
            u"max_snap_distance_mm": self.max_snap_distance_mm,
            u"collision_shift_mm": self.collision_shift_mm,
            u"collision_max_passes": self.collision_max_passes,
            u"default_side": self.default_side,
            u"mep_frequency_factor_by_usage": dict(self.mep_frequency_factor_by_usage),
            u"mep_discharge_units_by_fixture_type": dict(self.mep_discharge_units_by_fixture_type),
            u"mep_min_slope_table_percent": [list(pair) for pair in self.mep_min_slope_table_percent],
            u"mep_max_slope_percent": self.mep_max_slope_percent,
            u"mep_pipe_capacity_table_du": [list(pair) for pair in self.mep_pipe_capacity_table_du],
            u"mep_default_pipe_material": self.mep_default_pipe_material,
            u"mep_default_pipe_type_name": self.mep_default_pipe_type_name,
            u"mep_valve_height_mm": self.mep_valve_height_mm,
        }

    @classmethod
    def from_dict(cls, data):
        """Builds a Standard from a dict shaped like to_dict()'s output.
        Missing/None keys fall back to the constructor's own defaults, so a
        partial or older saved file still loads cleanly.

        Deliberately does NOT unpack via cls(**data): a JSON-sourced dict has
        unicode keys under IronPython 2.7 / Python 2, and both reject unicode
        keys in **kwargs unpacking ("keywords must be strings") - explicit
        named arguments sidestep that entirely, since they're identifiers
        resolved at call time, not dict keys.
        """
        data = data or {}
        defaults = cls(name=u"_defaults_probe")

        def _get(key, fallback):
            value = data.get(key)
            return fallback if value is None else value

        def _tuples(key, fallback):
            value = data.get(key)
            if value is None:
                return fallback
            return [tuple(pair) for pair in value]

        return cls(
            name=data.get(u"name", u"Default"),
            offset_first_mm=_get(u"offset_first_mm", defaults.offset_first_mm),
            wall_perimeter_gap_mm=_get(u"wall_perimeter_gap_mm", defaults.wall_perimeter_gap_mm),
            grid_chain_offset_mm=_get(u"grid_chain_offset_mm", defaults.grid_chain_offset_mm),
            grid_chain_gap_mm=_get(u"grid_chain_gap_mm", defaults.grid_chain_gap_mm),
            structural_chain_offset_mm=_get(u"structural_chain_offset_mm", defaults.structural_chain_offset_mm),
            structural_chain_gap_mm=_get(u"structural_chain_gap_mm", defaults.structural_chain_gap_mm),
            zero_tolerance_mm=_get(u"zero_tolerance_mm", defaults.zero_tolerance_mm),
            intersect_tolerance_mm=_get(u"intersect_tolerance_mm", defaults.intersect_tolerance_mm),
            max_snap_distance_mm=_get(u"max_snap_distance_mm", defaults.max_snap_distance_mm),
            collision_shift_mm=_get(u"collision_shift_mm", defaults.collision_shift_mm),
            collision_max_passes=_get(u"collision_max_passes", defaults.collision_max_passes),
            default_side=_get(u"default_side", defaults.default_side),
            mep_frequency_factor_by_usage=_get(
                u"mep_frequency_factor_by_usage", defaults.mep_frequency_factor_by_usage),
            mep_discharge_units_by_fixture_type=_get(
                u"mep_discharge_units_by_fixture_type", defaults.mep_discharge_units_by_fixture_type),
            mep_min_slope_table_percent=_tuples(
                u"mep_min_slope_table_percent", defaults.mep_min_slope_table_percent),
            mep_max_slope_percent=_get(u"mep_max_slope_percent", defaults.mep_max_slope_percent),
            mep_pipe_capacity_table_du=_tuples(
                u"mep_pipe_capacity_table_du", defaults.mep_pipe_capacity_table_du),
            mep_default_pipe_material=_get(u"mep_default_pipe_material", defaults.mep_default_pipe_material),
            mep_default_pipe_type_name=_get(u"mep_default_pipe_type_name", defaults.mep_default_pipe_type_name),
            mep_valve_height_mm=_get(u"mep_valve_height_mm", defaults.mep_valve_height_mm),
        )

    def validate(self):
        """Pure engineering-value validation - the real constraints already
        implied by this class's own field comments (positive offsets, sane
        MEP ranges), not speculative rules. Returns a list of human-readable
        error strings; empty list means valid. Never raises - the Settings UI
        renders these directly instead of catching an exception, per "never
        silently accept invalid engineering data."
        """
        errors = []

        def _positive(label, value):
            if value is None or value <= 0:
                errors.append(u"{0} must be greater than 0 (got {1}).".format(label, value))

        _positive(u"Dimension offset", self.offset_first_mm)
        _positive(u"Wall perimeter gap", self.wall_perimeter_gap_mm)
        _positive(u"Grid chain offset", self.grid_chain_offset_mm)
        _positive(u"Grid chain gap", self.grid_chain_gap_mm)
        _positive(u"Structural chain offset", self.structural_chain_offset_mm)
        _positive(u"Structural chain gap", self.structural_chain_gap_mm)
        _positive(u"MEP valve height", self.mep_valve_height_mm)

        for usage, factor in (self.mep_frequency_factor_by_usage or {}).items():
            if factor is None or not (0 < factor <= 2):
                errors.append(
                    u"MEP frequency factor for '{0}' should be between 0 and 2 (got {1}).".format(usage, factor))

        for fixture, du in (self.mep_discharge_units_by_fixture_type or {}).items():
            if du is None or du <= 0:
                errors.append(
                    u"MEP discharge units for '{0}' must be greater than 0 (got {1}).".format(fixture, du))

        for dn_mm, slope_percent in (self.mep_min_slope_table_percent or []):
            if slope_percent is None or not (0 < slope_percent <= 100):
                errors.append(
                    u"MEP min slope for DN{0} should be between 0 and 100% (got {1}).".format(dn_mm, slope_percent))

        if self.mep_max_slope_percent is not None:
            if not (0 < self.mep_max_slope_percent <= 100):
                errors.append(
                    u"MEP max slope should be between 0 and 100% (got {0}).".format(self.mep_max_slope_percent))
            else:
                min_slopes = [s for _, s in (self.mep_min_slope_table_percent or []) if s is not None]
                if min_slopes and min(min_slopes) >= self.mep_max_slope_percent:
                    errors.append(
                        u"MEP max slope ({0}%) must be greater than every configured min slope "
                        u"(smallest configured is {1}%).".format(self.mep_max_slope_percent, min(min_slopes)))

        for dn_mm, capacity_du in (self.mep_pipe_capacity_table_du or []):
            if capacity_du is None or capacity_du <= 0:
                errors.append(
                    u"MEP pipe capacity for DN{0} must be greater than 0 (got {1}).".format(dn_mm, capacity_du))

        return errors


def default_standard():
    """Un-validated placeholder profile - review before Phase 3 Standards GA."""
    return Standard(name=u"Default")


def load_office_standard():
    """Loads the office-wide Standard from the OFFICE SettingsStore layer if
    one has been saved via Settings > Office Standards, else falls back to
    default_standard(). Every dimensioning/MEP pushbutton should call this
    instead of default_standard() directly - otherwise editing Office
    Standards would have no effect on any real tool, which would make that
    whole Settings page a non-functional decoration. `core`/`ui.views.settings.
    office_standards_page` both depend on `domain` per SAD Sec 2's layering
    (ui -> app -> domain <- revit, all -> core) - this function is the one
    place `domain` depends back on `core`, which the dependency graph
    explicitly allows (core depends on nothing, everything else may depend
    on it)."""
    from bkbim.core.settings import LAYER_OFFICE, get_settings
    from bkbim.core.settings_paths import office_standards_path

    settings = get_settings()
    settings.load_layer_from_json(LAYER_OFFICE, office_standards_path())
    saved = settings.get(u"office_standards.standard")
    if saved:
        return Standard.from_dict(saved)
    return default_standard()
