import streamlit as st

_x_unit_map = {"Time (min)": "min", "Volume (mL)": "mL", "Column Volumes (CV)": "CV"}
_x_label_map = {"min": "Time (min)", "mL": "Volume (mL)", "CV": "Column Volumes (CV)"}


def xaxis_selector(key: str, default_unit: str = "min") -> str:
    """Render an x-axis unit segmented control. Returns unit string."""
    if key not in st.session_state:
        st.session_state[key] = default_unit
    selected = st.segmented_control(
        "X-axis unit",
        options=list(_x_label_map.values()),
        default=_x_label_map.get(st.session_state[key], "Time (min)"),
        key=f"xaxis_{key}",
    )
    st.session_state[key] = _x_unit_map.get(selected, "min")
    return st.session_state[key]


def build_curve_map(run: dict) -> dict:
    """Build {name: curve_dict} from run curves."""
    return {c["name"]: c for c in run["curves"]}


def get_common_channels(runs: list[dict]) -> list[str]:
    """Return channel names common to all runs."""
    if not runs:
        return []
    curve_sets = [set(c["name"] for c in run["curves"]) for run in runs]
    common = curve_sets[0].intersection(*curve_sets[1:])
    return sorted(common)
