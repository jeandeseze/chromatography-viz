import numpy as np
import pandas as pd

from utils import compute_auc


# ── Helpers ─────────────────────────────────────────────────────────────────

def _constant_signal(t_start, t_end, n=200, value=100.0):
    """Return (times, values) for a flat signal over [t_start, t_end]."""
    times = np.linspace(t_start, t_end, n)
    return times, np.full(n, value)


def _triangle_signal(t_start, t_end, n=200, peak_value=100.0):
    """Return (times, values) for a triangle: 0 → peak → 0."""
    times = np.linspace(t_start, t_end, n)
    mid = (t_start + t_end) / 2.0
    values = np.where(times <= mid,
                      peak_value * (times - t_start) / (mid - t_start),
                      peak_value * (t_end - times) / (t_end - mid))
    return times, values


def _phase(name, st, et, sv, ev):
    return {"name": name, "start_time": st, "end_time": et,
            "start_volume": sv, "end_volume": ev}


# ── Tests ───────────────────────────────────────────────────────────────────

class TestComputeAuc:

    def test_constant_signal_constant_flow(self):
        """UV=100, flow=1 mL/min for 10 min → 10 mL. AUC = 100 × 10 = 1000."""
        times, values = _constant_signal(0, 10, value=100.0)
        phases = pd.DataFrame([_phase("Run", 0, 10, 0, 10)])
        result = compute_auc(times, values, phases, None, 0, 10)
        np.testing.assert_almost_equal(result, 1000.0, decimal=0)

    def test_same_signal_double_flow(self):
        """UV=100, flow=2 mL/min for 10 min → 20 mL. AUC = 100 × 20 = 2000.

        This verifies AUC scales with volume, NOT time. Same duration as
        above (10 min) but twice the volume → twice the AUC.
        """
        times, values = _constant_signal(0, 10, value=100.0)
        phases = pd.DataFrame([_phase("Run", 0, 10, 0, 20)])
        result = compute_auc(times, values, phases, None, 0, 10)
        np.testing.assert_almost_equal(result, 2000.0, decimal=0)

    def test_flow_rate_change_mid_range(self):
        """UV=100 constant, two phases with different flows.

        Phase 1: 0-5 min, 0-5 mL  (1 mL/min)
        Phase 2: 5-10 min, 5-15 mL (2 mL/min)
        Total volume = 15 mL → AUC = 100 × 15 = 1500
        """
        times, values = _constant_signal(0, 10, value=100.0)
        phases = pd.DataFrame([
            _phase("Phase1", 0, 5, 0, 5),
            _phase("Phase2", 5, 10, 5, 15),
        ])
        result = compute_auc(times, values, phases, None, 0, 10)
        np.testing.assert_almost_equal(result, 1500.0, decimal=0)

    def test_zero_flow_hold(self):
        """UV=100, with a zero-flow hold in the middle.

        Phase 1: 0-5 min, 0-5 mL  (1 mL/min)
        Hold:    5-10 min, 5-5 mL (0 mL/min)
        Phase 3: 10-15 min, 5-10 mL (1 mL/min)
        Total volume over 0-15 min = 10 mL → AUC = 100 × 10 = 1000
        """
        times, values = _constant_signal(0, 15, value=100.0)
        phases = pd.DataFrame([
            _phase("Phase1", 0, 5, 0, 5),
            _phase("Hold", 5, 10, 5, 5),
            _phase("Phase3", 10, 15, 5, 10),
        ])
        result = compute_auc(times, values, phases, None, 0, 15)
        np.testing.assert_almost_equal(result, 1000.0, decimal=0)

    def test_triangle_peak(self):
        """Triangle 0→100→0 over 0-10 mL. AUC = 0.5 × 100 × 10 = 500."""
        times, values = _triangle_signal(0, 10, peak_value=100.0)
        phases = pd.DataFrame([_phase("Run", 0, 10, 0, 10)])
        result = compute_auc(times, values, phases, None, 0, 10)
        np.testing.assert_almost_equal(result, 500.0, decimal=0)

    def test_triangle_peak_then_hold(self):
        """Triangle 0→100→0 over time, but volume only advances during rise.

        Phase 1: 0-5 min, 0-10 mL  (2 mL/min, volume advances)
        Phase 2: 5-10 min, 10-10 mL (0 mL/min, hold, no volume change)

        The rising half of the triangle (UV 0→100) maps to volume 0→10 mL.
        The falling half (UV 100→0) occurs during the hold (no volume change).
        Only the rising half contributes: right triangle → 0.5 × 100 × 10 = 500.
        """
        times, values = _triangle_signal(0, 10, peak_value=100.0)
        phases = pd.DataFrame([
            _phase("Fast", 0, 5, 0, 10),
            _phase("Hold", 5, 10, 10, 10),
        ])
        result = compute_auc(times, values, phases, None, 0, 10)
        np.testing.assert_almost_equal(result, 500.0, decimal=0)

    def test_zero_signal(self):
        """Zero signal produces zero AUC regardless of flow profile."""
        times, values = _constant_signal(0, 10, value=0.0)
        phases = pd.DataFrame([_phase("Run", 0, 10, 0, 20)])
        result = compute_auc(times, values, phases, None, 0, 10)
        assert result == 0.0

    def test_partial_range_integration(self):
        """Integrate only part of the range. UV=100, flow=1 mL/min.

        Full range: 0-10 min → 0-10 mL.
        Integrate 3-7 min → volume 3-7 mL, delta=4 mL → AUC = 100 × 4 = 400.
        """
        times, values = _constant_signal(0, 10, value=100.0)
        phases = pd.DataFrame([_phase("Run", 0, 10, 0, 10)])
        result = compute_auc(times, values, phases, None, 3, 7)
        np.testing.assert_almost_equal(result, 400.0, decimal=0)

    def test_partial_range_across_flow_change(self):
        """Integrate across a flow-rate boundary.

        Phase 1: 0-5 min, 0-5 mL  (1 mL/min)
        Phase 2: 5-10 min, 5-15 mL (2 mL/min)

        Integrate 3-7 min:
          t=3 → V=3, t=5 → V=5, t=7 → V=9
          delta V = 6 mL → AUC = 100 × 6 = 600
        """
        times, values = _constant_signal(0, 10, value=100.0)
        phases = pd.DataFrame([
            _phase("Phase1", 0, 5, 0, 5),
            _phase("Phase2", 5, 10, 5, 15),
        ])
        result = compute_auc(times, values, phases, None, 3, 7)
        np.testing.assert_almost_equal(result, 600.0, decimal=0)

    def test_three_phase_variable_flow(self):
        """Three phases, all different flows, constant signal.

        Phase 1: 0-4 min, 0-4 mL   (1 mL/min)
        Phase 2: 4-8 min, 4-12 mL  (2 mL/min)
        Phase 3: 8-10 min, 12-17 mL (2.5 mL/min)
        Total volume = 17 mL → AUC = 100 × 17 = 1700
        """
        times, values = _constant_signal(0, 10, value=100.0)
        phases = pd.DataFrame([
            _phase("P1", 0, 4, 0, 4),
            _phase("P2", 4, 8, 4, 12),
            _phase("P3", 8, 10, 12, 17),
        ])
        result = compute_auc(times, values, phases, None, 0, 10)
        np.testing.assert_almost_equal(result, 1700.0, decimal=0)

    def test_cv_does_not_affect_auc_volume(self):
        """Column volume (CV) should not affect the AUC in mL.

        UV=100, 10 mL total volume. AUC should be 1000 regardless of CV.
        """
        times, values = _constant_signal(0, 10, value=100.0)
        phases = pd.DataFrame([_phase("Run", 0, 10, 0, 10)])
        result_no_cv = compute_auc(times, values, phases, None, 0, 10)
        result_with_cv = compute_auc(times, values, phases, 25.0, 0, 10)
        np.testing.assert_almost_equal(result_no_cv, result_with_cv, decimal=0)
        np.testing.assert_almost_equal(result_with_cv, 1000.0, decimal=0)
