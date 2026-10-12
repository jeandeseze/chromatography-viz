import colorsys

import numpy as np
import pandas as pd


def compute_auc(
    uv_times: np.ndarray,
    uv_values: np.ndarray,
    phase_df: pd.DataFrame,
    column_volume,
    range_start_min: float,
    range_end_min: float,
    n_points: int = 1000,
) -> float:
    """Compute AUC (signal integrated over volume) for a time range.

    UV signal is interpolated to ``n_points`` evenly-spaced time values
    within ``[range_start_min, range_end_min]``.  Time points are converted
    to volume (mL) via piecewise-linear interpolation of phase boundaries,
    then trapezoidal integration is performed with respect to volume.

    Returns the raw AUC in ``signal_unit * mL``.
    """
    interp_times = np.linspace(range_start_min, range_end_min, n_points)
    interp_values = np.interp(interp_times, uv_times, uv_values)
    interp_volumes = convert_times(interp_times, phase_df, column_volume, "mL")
    return float(np.trapezoid(interp_values, interp_volumes))


def format_channel_title(name: str, unit: str = "") -> str:
    """Format a channel name for display, appending its unit.

    The unit is omitted when missing or already present in the name
    (e.g. channel "Flow (CV/h)" with unit "CV/h").
    """
    unit = (unit or "").strip()
    if not unit or unit in name:
        return name
    return f"{name} ({unit})"


def unit_suffix(unit: str = "") -> str:
    """Return a display suffix like ``' MPa'`` for hover labels; empty when no unit."""
    unit = (unit or "").strip()
    return f" {unit}" if unit else ""


def filter_phases(phase_df: pd.DataFrame) -> pd.DataFrame:
    """Remove phases before Equilibration."""
    if phase_df.empty or "name" not in phase_df.columns:
        return phase_df
    eq_idx = None
    for i, row in phase_df.iterrows():
        if row.get("name") == "Equilibration":
            eq_idx = i
            break
    if eq_idx is None:
        return phase_df
    eq_pos = phase_df.index.get_loc(eq_idx)
    return phase_df.iloc[eq_pos:].reset_index(drop=True)


def get_phase_bounds(phase_df: pd.DataFrame):
    """Return (times, volumes) arrays for phase boundaries."""
    if phase_df.empty or not all(
        c in phase_df.columns for c in ("start_time", "end_time", "start_volume", "end_volume")
    ):
        return None, None
    pts = []
    for _, row in phase_df.iterrows():
        st, et, sv, ev = (
            float(row["start_time"]),
            float(row["end_time"]),
            float(row["start_volume"]),
            float(row["end_volume"]),
        )
        pts.append((st, sv))
        pts.append((et, ev))
    pts.sort(key=lambda p: p[0])
    seen = {}
    for t, v in pts:
        seen[t] = v
    if len(seen) < 2:
        return None, None
    sorted_t = sorted(seen.keys())
    return np.array(sorted_t), np.array([seen[t] for t in sorted_t])


def convert_times(times: np.ndarray, phase_df: pd.DataFrame, column_volume, unit: str) -> np.ndarray:
    """Convert time array to the given unit (min, mL, CV)."""
    if unit == "min":
        return times
    btimes, bvolumes = get_phase_bounds(phase_df)
    if btimes is None:
        return times
    t_lo, t_hi = btimes.min(), btimes.max()
    clipped = np.clip(times, t_lo, t_hi)
    volumes = np.interp(clipped, btimes, bvolumes)
    if unit == "mL":
        return volumes
    if column_volume and column_volume > 0:
        return volumes / column_volume
    return volumes


def convert_scalar(t, phase_df: pd.DataFrame, column_volume, from_unit: str, to_unit: str):
    """Convert a single scalar value between units."""
    if from_unit == to_unit:
        return t
    btimes, bvolumes = get_phase_bounds(phase_df)
    if btimes is None:
        return t
    if from_unit == "min":
        vol = np.interp(t, btimes, bvolumes)
    elif from_unit == "mL":
        vol = t
    elif from_unit == "CV":
        vol = t * column_volume if column_volume else t
    else:
        return t
    if to_unit == "min":
        return float(np.interp(vol, bvolumes, btimes))
    if to_unit == "mL":
        return float(vol)
    if column_volume and column_volume > 0:
        return float(vol / column_volume)
    return float(vol)


def get_x_label(unit: str) -> str:
    if unit == "min":
        return "Time (min)"
    if unit == "mL":
        return "Volume (mL)"
    return "Column Volumes (CV)"


def get_elution_start(phase_df: pd.DataFrame) -> float | None:
    """Return the start_time of the Elution phase, or None if not found."""
    if phase_df.empty or "name" not in phase_df.columns:
        return None
    for _, row in phase_df.iterrows():
        if row.get("name", "").strip().lower() == "elution":
            return float(row["start_time"])
    return None


def get_loading_start(phase_df: pd.DataFrame) -> float | None:
    """Return the start_time of the Sample Application (loading) phase, or None."""
    if phase_df.empty or "name" not in phase_df.columns:
        return None
    for _, row in phase_df.iterrows():
        if row.get("name", "").strip().lower() in ("sample application", "loading"):
            return float(row["start_time"])
    return None


def get_equilibration_start(phase_df: pd.DataFrame) -> float | None:
    """Return the start_time of the Equilibration phase, or None if not found."""
    if phase_df.empty or "name" not in phase_df.columns:
        return None
    for _, row in phase_df.iterrows():
        if row.get("name", "").strip().lower() == "equilibration":
            return float(row["start_time"])
    return None


def phase_colors(name: str) -> str:
    """Generate a consistent RGBA color for a phase name."""
    palette = {
        "method settings": 0,
        "miscellaneous": 10,
        "equilibration": 200,
        "sample application": 120,
        "column wash 1": 40,
        "column wash 2": 280,
        "autozéro uv": 190,
        "elution": 60,
    }
    n = name.strip().lower()
    h = palette.get(n, sum(ord(c) * (i + 1) for i, c in enumerate(n)) % 360)
    r, g, b = colorsys.hsv_to_rgb(h / 360, 0.55, 1)
    return f"rgba({int(r*255)}, {int(g*255)}, {int(b*255)}, 0.15)"
