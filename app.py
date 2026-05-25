import platform
from pathlib import Path

import streamlit as st

from run_index import build_run_index, discover_json_files, load_selected_runs
from sidebar import render_sidebar
from tabs import auc, chromatogram, events, params, peaks, phases, sysinfo

st.set_page_config(page_title="Chromatography Viewer", layout="wide")

st.markdown(
    """
<style>
[data-testid="stSidebar"][aria-expanded="true"] {
    max-width: 600px !important;
    min-width: 600px !important;
}
</style>
""",
    unsafe_allow_html=True,
)

st.title("Chromatography Data Viewer")

_SYS_DRIVE = "C:" if platform.system() == "Windows" else "/mnt/c"
DATA_DIR = Path(
    f"{_SYS_DRIVE}/Users/JeandeSEZE/Veyton/"
    r"C-R&D-Process dev - Documents/"
    r"20_Internal Studies/05_Model studies/xtodata"
)

# --- Session state ---
for k, default in [
    ("selected_runs", []),
    ("run_data", {}),
    ("auc_range", None),
    ("auc_range_unit", "min"),
    ("chroma_x_unit", "min"),
    ("auc_x_unit", "min"),
    ("show_phases", True),
]:
    if k not in st.session_state:
        st.session_state[k] = default

# --- Discover and index runs ---
all_json_files = discover_json_files(DATA_DIR)

if not all_json_files:
    st.error(f"Data directory not found or empty: {DATA_DIR}")
    st.stop()

runs_by_study = build_run_index(all_json_files)

# --- Sidebar selection ---
render_sidebar(runs_by_study)

# --- Load selected runs ---
st.session_state.run_data = load_selected_runs(
    st.session_state.selected_runs, st.session_state.run_data
)

# --- Build path->meta map ---
all_runs_flat = [
    rm for info in runs_by_study.values() for rm in info["runs"]
]
path_to_meta = {rm["path"]: rm for rm in all_runs_flat}
selected_run_metas = [
    path_to_meta[rp] for rp in st.session_state.selected_runs
    if rp in path_to_meta
]

# --- Tabs ---
tab_chroma, tab_auc, tab_peaks, tab_phases, tab_events, tab_params, tab_sysinfo = st.tabs([
    "Chromatogram", "AUC", "Peaks", "Phases", "Method Events", "Experimental Params", "System Infos"
])

with tab_chroma:
    chromatogram.render(selected_run_metas)

with tab_auc:
    auc.render(selected_run_metas)

with tab_peaks:
    peaks.render(selected_run_metas)

with tab_phases:
    phases.render(selected_run_metas)

with tab_events:
    events.render(selected_run_metas)

with tab_params:
    params.render(selected_run_metas)

with tab_sysinfo:
    sysinfo.render(selected_run_metas)
