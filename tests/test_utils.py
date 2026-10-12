import numpy as np
import pandas as pd
import pytest

from utils import (
    convert_scalar,
    convert_times,
    filter_phases,
    format_channel_title,
    get_elution_start,
    get_phase_bounds,
    get_x_label,
    phase_colors,
    unit_suffix,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def single_phase_df():
    """One phase: 0-10 min, 0-10 mL (1 mL/min constant flow)."""
    return pd.DataFrame([{
        "name": "Equilibration",
        "start_time": 0.0,
        "end_time": 10.0,
        "start_volume": 0.0,
        "end_volume": 10.0,
    }])


@pytest.fixture
def two_phase_df():
    """Two phases with different flow rates.

    Phase 1: 0-5 min, 0-5 mL  → 1 mL/min
    Phase 2: 5-10 min, 5-15 mL → 2 mL/min
    """
    return pd.DataFrame([
        {
            "name": "Equilibration",
            "start_time": 0.0,
            "end_time": 5.0,
            "start_volume": 0.0,
            "end_volume": 5.0,
        },
        {
            "name": "Elution",
            "start_time": 5.0,
            "end_time": 10.0,
            "start_volume": 5.0,
            "end_volume": 15.0,
        },
    ])


@pytest.fixture
def three_phase_with_hold_df():
    """Three phases with a zero-flow hold in the middle.

    Phase 1: 0-5 min, 0-5 mL  → 1 mL/min
    Hold:    5-10 min, 5-5 mL → 0 mL/min (hold)
    Phase 3: 10-15 min, 5-10 mL → 1 mL/min
    """
    return pd.DataFrame([
        {
            "name": "Equilibration",
            "start_time": 0.0,
            "end_time": 5.0,
            "start_volume": 0.0,
            "end_volume": 5.0,
        },
        {
            "name": "Hold",
            "start_time": 5.0,
            "end_time": 10.0,
            "start_volume": 5.0,
            "end_volume": 5.0,
        },
        {
            "name": "Elution",
            "start_time": 10.0,
            "end_time": 15.0,
            "start_volume": 5.0,
            "end_volume": 10.0,
        },
    ])


# ── get_phase_bounds ────────────────────────────────────────────────────────

class TestGetPhaseBounds:
    def test_empty_df(self):
        ts, vs = get_phase_bounds(pd.DataFrame())
        assert ts is None
        assert vs is None

    def test_missing_columns(self):
        df = pd.DataFrame([{"name": "Foo"}])
        ts, vs = get_phase_bounds(df)
        assert ts is None
        assert vs is None

    def test_single_phase(self, single_phase_df):
        ts, vs = get_phase_bounds(single_phase_df)
        assert ts is not None
        np.testing.assert_array_almost_equal(ts, [0.0, 10.0])
        np.testing.assert_array_almost_equal(vs, [0.0, 10.0])

    def test_two_phases(self, two_phase_df):
        ts, vs = get_phase_bounds(two_phase_df)
        assert ts is not None
        np.testing.assert_array_almost_equal(ts, [0.0, 5.0, 10.0])
        np.testing.assert_array_almost_equal(vs, [0.0, 5.0, 15.0])

    def test_three_phases_with_hold(self, three_phase_with_hold_df):
        ts, vs = get_phase_bounds(three_phase_with_hold_df)
        assert ts is not None
        np.testing.assert_array_almost_equal(ts, [0.0, 5.0, 10.0, 15.0])
        np.testing.assert_array_almost_equal(vs, [0.0, 5.0, 5.0, 10.0])

    def test_too_few_points(self):
        df = pd.DataFrame([{
            "name": "X",
            "start_time": 0.0,
            "end_time": 0.0,
            "start_volume": 0.0,
            "end_volume": 0.0,
        }])
        ts, vs = get_phase_bounds(df)
        assert ts is None
        assert vs is None


# ── convert_times ───────────────────────────────────────────────────────────

class TestConvertTimes:
    def test_min_is_identity(self, single_phase_df):
        t = np.array([1.0, 5.0, 10.0])
        result = convert_times(t, single_phase_df, None, "min")
        np.testing.assert_array_almost_equal(result, t)

    def test_no_phase_df_fallback(self):
        t = np.array([1.0, 5.0, 10.0])
        result = convert_times(t, pd.DataFrame(), None, "mL")
        np.testing.assert_array_almost_equal(result, t)

    def test_constant_flow_mL(self, single_phase_df):
        t = np.array([0.0, 5.0, 10.0])
        result = convert_times(t, single_phase_df, None, "mL")
        np.testing.assert_array_almost_equal(result, [0.0, 5.0, 10.0])

    def test_varying_flow_mL(self, two_phase_df):
        t = np.array([0.0, 2.5, 5.0, 7.5, 10.0])
        result = convert_times(t, two_phase_df, None, "mL")
        expected = np.array([0.0, 2.5, 5.0, 10.0, 15.0])
        np.testing.assert_array_almost_equal(result, expected)

    def test_zero_flow_hold(self, three_phase_with_hold_df):
        t = np.array([5.0, 7.5, 10.0])
        result = convert_times(t, three_phase_with_hold_df, None, "mL")
        np.testing.assert_array_almost_equal(result, [5.0, 5.0, 5.0])

    def test_cv_conversion(self, single_phase_df):
        t = np.array([0.0, 5.0, 10.0])
        result = convert_times(t, single_phase_df, column_volume=10.0, unit="CV")
        np.testing.assert_array_almost_equal(result, [0.0, 0.5, 1.0])

    def test_cv_no_column_volume_fallback(self, single_phase_df):
        t = np.array([0.0, 5.0, 10.0])
        result = convert_times(t, single_phase_df, column_volume=None, unit="CV")
        np.testing.assert_array_almost_equal(result, [0.0, 5.0, 10.0])

    def test_clipping_out_of_range(self, single_phase_df):
        t = np.array([-1.0, 0.0, 10.0, 11.0])
        result = convert_times(t, single_phase_df, None, "mL")
        np.testing.assert_array_almost_equal(result, [0.0, 0.0, 10.0, 10.0])


# ── convert_scalar ──────────────────────────────────────────────────────────

class TestConvertScalar:
    def test_same_unit(self, single_phase_df):
        assert convert_scalar(5.0, single_phase_df, None, "min", "min") == 5.0

    def test_min_to_mL_constant(self, single_phase_df):
        result = convert_scalar(5.0, single_phase_df, None, "min", "mL")
        np.testing.assert_almost_equal(result, 5.0)

    def test_min_to_mL_varying(self, two_phase_df):
        result = convert_scalar(7.5, two_phase_df, None, "min", "mL")
        np.testing.assert_almost_equal(result, 10.0)

    def test_mL_to_min(self, single_phase_df):
        result = convert_scalar(5.0, single_phase_df, None, "mL", "min")
        np.testing.assert_almost_equal(result, 5.0)

    def test_roundtrip_min_mL(self, two_phase_df):
        for t in [0.0, 2.5, 5.0, 7.5, 10.0]:
            vol = convert_scalar(t, two_phase_df, None, "min", "mL")
            back = convert_scalar(vol, two_phase_df, None, "mL", "min")
            np.testing.assert_almost_equal(back, t, err_msg=f"Roundtrip failed for t={t}")

    def test_roundtrip_min_mL_min(self, two_phase_df):
        for t in [0.0, 2.5, 5.0, 7.5, 10.0]:
            vol = convert_scalar(t, two_phase_df, None, "min", "mL")
            back = convert_scalar(vol, two_phase_df, None, "mL", "min")
            np.testing.assert_almost_equal(back, t, err_msg=f"Roundtrip failed for t={t}")

    def test_cv_conversion(self, single_phase_df):
        result = convert_scalar(5.0, single_phase_df, 10.0, "min", "CV")
        np.testing.assert_almost_equal(result, 0.5)

    def test_no_phase_df_fallback(self):
        result = convert_scalar(3.0, pd.DataFrame(), None, "min", "mL")
        assert result == 3.0


# ── filter_phases ───────────────────────────────────────────────────────────

class TestFilterPhases:
    def test_empty(self):
        assert filter_phases(pd.DataFrame()).empty

    def test_no_equilibration(self):
        df = pd.DataFrame([{"name": "Elution", "start_time": 0, "end_time": 10}])
        result = filter_phases(df)
        assert len(result) == 1

    def test_filters_before_equilibration(self):
        df = pd.DataFrame([
            {"name": "Load", "start_time": 0, "end_time": 2},
            {"name": "Equilibration", "start_time": 2, "end_time": 5},
            {"name": "Elution", "start_time": 5, "end_time": 10},
        ])
        result = filter_phases(df)
        assert len(result) == 2
        assert result.iloc[0]["name"] == "Equilibration"


# ── get_elution_start ───────────────────────────────────────────────────────

class TestGetElutionStart:
    def test_finds_elution(self):
        df = pd.DataFrame([
            {"name": "Equilibration", "start_time": 0.0},
            {"name": "Elution", "start_time": 5.0},
        ])
        assert get_elution_start(df) == 5.0

    def test_case_insensitive(self):
        df = pd.DataFrame([
            {"name": "elution", "start_time": 3.0},
        ])
        assert get_elution_start(df) == 3.0

    def test_no_elution(self):
        df = pd.DataFrame([{"name": "Equilibration", "start_time": 0.0}])
        assert get_elution_start(df) is None

    def test_empty(self):
        assert get_elution_start(pd.DataFrame()) is None


# ── get_x_label ─────────────────────────────────────────────────────────────

class TestGetXLabel:
    def test_min(self):
        assert get_x_label("min") == "Time (min)"

    def test_mL(self):
        assert get_x_label("mL") == "Volume (mL)"

    def test_CV(self):
        assert get_x_label("CV") == "Column Volumes (CV)"


# ── phase_colors ────────────────────────────────────────────────────────────

class TestPhaseColors:
    def test_returns_rgba_string(self):
        color = phase_colors("Elution")
        assert color.startswith("rgba(")
        assert color.endswith(")")

    def test_consistent_for_same_name(self):
        assert phase_colors("Elution") == phase_colors("Elution")

    def test_known_palette_entry(self):
        c1 = phase_colors("Equilibration")
        c2 = phase_colors("elution")
        assert c1 != c2


# ── format_channel_title ────────────────────────────────────────────────────

class TestFormatChannelTitle:
    def test_appends_unit(self):
        assert format_channel_title("Pressure", "MPa") == "Pressure (MPa)"

    def test_no_unit(self):
        assert format_channel_title("Pressure", "") == "Pressure"

    def test_none_unit(self):
        assert format_channel_title("Pressure", None) == "Pressure"

    def test_unit_already_in_name_not_duplicated(self):
        assert format_channel_title("Flow (CV/h)", "CV/h") == "Flow (CV/h)"

    def test_unit_contained_in_name_not_duplicated(self):
        assert format_channel_title("% Cond", "%") == "% Cond"

    def test_unit_stripped(self):
        assert format_channel_title("UV", " mAU ") == "UV (mAU)"


# ── unit_suffix ─────────────────────────────────────────────────────────────

class TestUnitSuffix:
    def test_returns_space_prefixed_unit(self):
        assert unit_suffix("MPa") == " MPa"

    def test_empty(self):
        assert unit_suffix("") == ""

    def test_none(self):
        assert unit_suffix(None) == ""

    def test_stripped(self):
        assert unit_suffix(" mS/cm ") == " mS/cm"
