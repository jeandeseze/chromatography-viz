import json as _json
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from loaders import load_json_run

st.set_page_config(page_title="Chromatography Viewer", layout="wide")
st.title("Chromatography Data Viewer")

# --- Hardcoded data directory ---
DATA_DIR = Path(
    r"/mnt/c/Users/JeandeSEZE/Veyton/C-R&D-Process dev - Documents/"
    r"20_Internal Studies/05_Model studies/xtodata"
)

# --- Session state ---
if "runs" not in st.session_state:
    st.session_state.runs = []
if "run_data" not in st.session_state:
    st.session_state.run_data = {}
if "auc_range" not in st.session_state:
    st.session_state.auc_range = None

# --- Discover json files ---
if DATA_DIR.is_dir():
    all_json_files = sorted(
        str(f) for f in DATA_DIR.iterdir() if f.suffix.lower() == ".json"
    )
else:
    all_json_files = []

if not all_json_files:
    st.error(f"Data directory not found or empty: {DATA_DIR}")
    st.stop()

# --- Build display names ---
run_displays = []
for jp in all_json_files:
    try:
        with open(jp, "r") as f:
            raw = _json.load(f)
        ri = raw.get("run_info", {})
        study_id = raw.get("study_id", "")
        run_name = ri.get("name", Path(jp).stem)
        display = f"[{study_id}] {run_name}" if study_id else run_name
        run_displays.append({
            "path": jp,
            "display": display,
            "study_id": study_id,
            "study_name": raw.get("study_name", ""),
            "run_info": ri,
            "column_info": raw.get("column_info", ""),
        })
    except Exception as e:
        st.error(f"Failed to read {Path(jp).name}: {e}")

# --- Multiselect for runs ---
st.sidebar.header("Select Runs")
selected_displays = [r["display"] for r in run_displays]
selected_runs = st.sidebar.multiselect(
    "Available files",
    selected_displays,
    key="selected_runs",
)

if not selected_runs:
    st.info(f"Select one or more runs from the sidebar ({len(run_displays)} available).")
    st.stop()

# Build selected run metadata
idx_map = {r["display"]: i for i, r in enumerate(run_displays)}
st.session_state.runs = [run_displays[idx_map[d]] for d in selected_runs]
st.session_state.run_data = {}

st.sidebar.success(f"{len(st.session_state.runs)} run(s) selected")

# --- Run selector (when multiple loaded) ---
if len(st.session_state.runs) == 1:
    selected_run = st.session_state.runs[0]
else:
    display_names = [r["display"] for r in st.session_state.runs]
    selected_idx = st.selectbox(
        "Select run to display",
        range(len(display_names)),
        format_func=lambda i: display_names[i],
    )
    selected_run = st.session_state.runs[selected_idx]

ri = selected_run["run_info"]
study_id = selected_run.get("study_id", "")
study_name = selected_run.get("study_name", "")

# --- Metadata header ---
st.subheader(f"Run: {ri.get('name', 'Unknown')}")
if study_id:
    st.caption(f"Study: **{study_id}** \u2014 {study_name}")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("System", ri.get("system_name", "-"))
c2.metric("Version", ri.get("unicorn_version", "-"))
c3.metric("State", ri.get("run_state", "-"))
c4.metric("Batch", ri.get("batch_id", "-"))
c5.metric("Run #", ri.get("run_index", "-"))

if ri.get("created_at"):
    st.caption(f"Created: {ri['created_at']} by {ri.get('created_by', '-')}")
col_info = selected_run.get("column_info", "")
if col_info:
    st.caption(f"Column: {col_info}")

# --- Load data (cached) ---
run_path = selected_run["path"]
if run_path not in st.session_state.run_data:
    with st.spinner("Loading run data..."):
        st.session_state.run_data[run_path] = load_json_run(run_path)

run = st.session_state.run_data[run_path]
st.divider()

# --- Controls (sidebar) ---
st.sidebar.divider()
curve_names = [c["name"] for c in run["curves"]]
curve_map = {c["name"]: c for c in run["curves"]}

selected_curves = st.sidebar.multiselect(
    "Channels to display",
    curve_names,
    default=curve_names[:3] if len(curve_names) >= 3 else curve_names,
    key="channel_select",
)

show_peaks_overlay = st.sidebar.checkbox("Show peak markers", value=True, key="peak_overlay")
show_phases_overlay = st.sidebar.checkbox("Show phase regions", value=True, key="phase_overlay")
show_events_overlay = st.sidebar.checkbox("Show method events", value=False, key="event_overlay")

# --- Chromatogram ---
st.header("Chromatogram")

rows = []
for name in selected_curves:
    c = curve_map[name]
    times = c.get("times", [])
    values = c.get("values", [])
    if not times:
        continue
    for t, v in zip(times, values):
        rows.append({"time": t, "value": v, "channel": name})

chroma_df = pd.DataFrame(rows)

base = alt.Chart(chroma_df).mark_line(interpolate="linear").encode(
    x="time:Q",
    y="value:Q",
    color="channel:N",
    tooltip=["time:Q", "value:Q", "channel:N"],
).interactive()

st.altair_chart(base, use_container_width=True)

# --- Area Under Curve (AUC) ---
uv_curves = [c for c in run["curves"] if c.get("data_type") == "UV"]

if uv_curves:
    st.header("Area Under Curve")
    st.divider()

    uv_curve_names = [c["name"] for c in uv_curves]
    auc_curve_name = st.selectbox(
        "UV curve for integration",
        uv_curve_names,
        key="auc_curve",
    )
    uv_c = curve_map[auc_curve_name]
    uv_times = np.array(uv_c["times"])
    uv_values = np.array(uv_c["values"])

    t_min, t_max = float(uv_times.min()), float(uv_times.max())

    unit = uv_c.get("amplitude_unit", "")

    if st.session_state.auc_range is None:
        st.session_state.auc_range = (t_min, t_max)

    range_start, range_end = st.slider(
        "Integration range",
        min_value=t_min,
        max_value=t_max,
        value=st.session_state.auc_range,
        step=0.01,
        key="auc_range_slider",
    )
    st.session_state.auc_range = (range_start, range_end)

    mask = (uv_times >= range_start) & (uv_times <= range_end)
    seg_times = uv_times[mask]
    seg_values = uv_values[mask]

    if seg_times.size > 1:
        auc_value = float(np.trapezoid(seg_values, seg_times))
        dur = seg_times[-1] - seg_times[0]
    else:
        auc_value = 0.0
        dur = 0.0

    auc_c1, auc_c2, auc_c3 = st.columns(3)
    auc_c1.metric("AUC", f"{auc_value:,.2f}")
    auc_c2.metric("Range", f"{range_start:.2f} \u2013 {range_end:.2f} min")
    auc_c3.metric("Duration", f"{dur:.2f} min")

    # Build Altair chart
    uv_df = pd.DataFrame({"time": uv_times, "value": uv_values})
    seg_df = pd.DataFrame({"time": seg_times, "value": seg_values})

    shaded = (
        alt.Chart(seg_df)
        .mark_area(opacity=0.25)
        .encode(x="time:Q", y="value:Q", color=alt.value("steelblue"))
    )

    line = (
        alt.Chart(uv_df)
        .mark_line(interpolate="linear", strokeWidth=1.5)
        .encode(
            x="time:Q",
            y="value:Q",
            tooltip=["time:Q", "value:Q"],
            color=alt.value("steelblue"),
        )
        .interactive()
    )

    bound_df = pd.DataFrame({"x": [range_start, range_end]})
    bounds = (
        alt.Chart(bound_df)
        .mark_rule(color="orange", strokeDash=[4, 4], strokeWidth=1.5)
        .encode(x="x:Q")
    )

    auc_chart = (shaded + line + bounds).properties(height=450)
    st.altair_chart(auc_chart, use_container_width=True)

# --- Peaks ---
if not run["peak_df"].empty:
    st.header("Peaks")
    st.divider()
    display_cols = [c for c in run["peak_df"].columns if c != "table_name"]
    st.dataframe(
        run["peak_df"][display_cols].style.format({
            c: "{:.2f}" for c in [
                "start_retention", "max_retention", "end_retention",
                "width", "width_at_half_height",
            ] if c in run["peak_df"].columns
        })
    )

    peak_df = run["peak_df"]
    peak_chart = (
        alt.Chart(peak_df)
        .mark_bar()
        .encode(
            x="name:N",
            y="area:Q",
            color=alt.value("steelblue"),
            tooltip=["name:N", "area:Q", alt.Text("percent_of_total_area:Q", format=".1f")],
        )
        .properties(height=350)
    )
    st.altair_chart(peak_chart, use_container_width=True)

# --- Phases ---
if not run["phase_df"].empty:
    st.header("Phases")
    st.divider()
    st.dataframe(run["phase_df"])

# --- Method Events ---
if not run["event_df"].empty:
    st.header("Method Events")
    st.divider()
    st.dataframe(run["event_df"])

# --- Experimental Params ---
if run["exp_params"]:
    st.header("Experimental Params")
    st.divider()
    params_df = pd.DataFrame(list(run["exp_params"].items()), columns=["Parameter", "Value"])
    meta_keys = {"excel_row", "excel_match_date", "excel_match_run"}
    data_params = params_df[~params_df["Parameter"].isin(meta_keys)]
    meta_params = params_df[params_df["Parameter"].isin(meta_keys)]

    if not meta_params.empty:
        st.caption("Excel match: " + ", ".join(
            f"{row['Parameter']}={row['Value']}" for _, row in meta_params.iterrows()
        ))

    def fmt_val(v):
        try:
            return f"{float(v):.4g}"
        except (ValueError, TypeError):
            return str(v)

    st.dataframe(
        data_params.set_index("Parameter").style.format(fmt_val)
    )
