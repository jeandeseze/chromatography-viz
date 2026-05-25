import json as _json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from loaders import load_json_run

st.set_page_config(page_title="Chromatography Viewer", layout="wide")
st.title("Chromatography Data Viewer")

# --- Data directory (auto-detect WSL vs native Windows) ---
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
]:
    if k not in st.session_state:
        st.session_state[k] = default

# --- Discover json files ---
all_json_files = (
    sorted(str(f) for f in DATA_DIR.iterdir() if f.suffix.lower() == ".json")
    if DATA_DIR.is_dir()
    else []
)

if not all_json_files:
    st.error(f"Data directory not found or empty: {DATA_DIR}")
    st.stop()

# --- Build run index grouped by study ---
runs_by_study = {}
for jp in all_json_files:
    try:
        with open(jp, "r") as f:
            raw = _json.load(f)
        ri = raw.get("run_info", {})
        study_id = raw.get("study_id", "N/A")
        study_name = raw.get("study_name", study_id)
        run_name = ri.get("name", Path(jp).stem)
        if study_id not in runs_by_study:
            runs_by_study[study_id] = {
                "study_name": study_name,
                "runs": [],
            }
        runs_by_study[study_id]["runs"].append({
            "path": jp,
            "run_id": study_id,
            "run_name": run_name,
            "display": f"[{study_id}] {run_name}",
            "study_name": study_name,
            "run_info": ri,
            "column_info": raw.get("column_info", ""),
        })
    except Exception as e:
        st.error(f"Failed to read {Path(jp).name}: {e}")

# ================================================================
# SIDEBAR: Study + Run selection (expanders per study)
# ================================================================
st.sidebar.header("Select Runs")

all_study_ids = sorted(runs_by_study.keys())
study_display = {sid: runs_by_study[sid]["study_name"] for sid in all_study_ids}

selected_studies = st.sidebar.multiselect(
    "Studies",
    all_study_ids,
    format_func=lambda sid: study_display[sid],
    default=[all_study_ids[0]] if all_study_ids else [],
    key="study_filter",
)

prev_selected = set(st.session_state.selected_runs)
new_selected = set()

for sid in selected_studies:
    info = runs_by_study[sid]
    with st.sidebar.expander(info["study_name"], expanded=True):
        for run_meta in info["runs"]:
            if st.checkbox(
                run_meta["run_name"],
                value=(run_meta["path"] in prev_selected),
                key=f"run_cb_{run_meta['path']}",
            ):
                new_selected.add(run_meta["path"])

# Only keep runs that belong to selected studies
available_paths = set(
    rm["path"] for sid in selected_studies for rm in runs_by_study[sid]["runs"]
)
st.session_state.selected_runs = list(new_selected & available_paths)

if not st.session_state.selected_runs:
    st.info("Select at least one run from the sidebar.")
    st.stop()

st.sidebar.success(f"{len(st.session_state.selected_runs)} run(s) selected")

# --- Load all selected runs (cached) ---
for rp in st.session_state.selected_runs:
    if rp not in st.session_state.run_data:
        st.session_state.run_data[rp] = load_json_run(rp)

# --- Build run metadata map ---
all_runs_flat = [
    rm for info in runs_by_study.values() for rm in info["runs"]
]
path_to_meta = {rm["path"]: rm for rm in all_runs_flat}
selected_run_metas = [
    path_to_meta[rp] for rp in st.session_state.selected_runs
    if rp in path_to_meta
]

# ================================================================
# TABS
# ================================================================
tab_chroma, tab_auc, tab_peaks, tab_phases, tab_events, tab_params, tab_sysinfo = st.tabs([
    "Chromatogram", "AUC", "Peaks", "Phases", "Method Events", "Experimental Params", "System Infos"
])

# --- Helpers ---
def build_curve_map(run):
    return {c["name"]: c for c in run["curves"]}


def get_common_channels(runs):
    if not runs:
        return []
    curve_sets = [set(c["name"] for c in run["curves"]) for run in runs]
    common = curve_sets[0].intersection(*curve_sets[1:])
    return sorted(common)


# ================================================================
# TAB: Chromatogram — overlay all selected runs
# ================================================================
with tab_chroma:
    selected_runs_data = [
        st.session_state.run_data[rpm["path"]] for rpm in selected_run_metas
    ]
    selected_run_labels = [
        f"{rpm['study_name']} > {rpm['run_name']}" for rpm in selected_run_metas
    ]

    # Find common channel names across all selected runs
    common_channels = get_common_channels(selected_runs_data)

    if not common_channels:
        st.warning("No common channels across selected runs. Showing channels from first run.")
        common_channels = [c["name"] for c in selected_runs_data[0]["curves"]]

    preferred = ["UV", "Conductivity"]
    default_channels = [ch for ch in preferred if ch in common_channels]
    if not default_channels:
        default_channels = common_channels[:2] if len(common_channels) >= 2 else common_channels
    selected_channels = st.multiselect(
        "Channels to display (max 3)",
        common_channels,
        default=default_channels,
        key="chroma_channels",
    )

    if len(selected_channels) > 3:
        selected_channels = selected_channels[:3]
        st.warning("Limited to 3 channels.")

    if not selected_channels:
        st.info("Select at least one channel.")
    else:
        fig = go.Figure()

        for run, run_label in zip(selected_runs_data, selected_run_labels):
            cmap = build_curve_map(run)
            for ch_name in selected_channels:
                if ch_name not in cmap:
                    continue
                c = cmap[ch_name]
                times = c.get("times", [])
                values = np.array(c.get("values", []))
                if not times or values.size == 0:
                    continue

                v_min, v_max = values.min(), values.max()
                v_range = v_max - v_min if v_max != v_min else 1.0
                scaled = (values - v_min) / v_range

                trace_name = f"{run_label} — {ch_name}"
                fig.add_trace(go.Scattergl(
                    x=times,
                    y=scaled,
                    mode="lines",
                    name=trace_name,
                    hovertemplate=(
                        f"<b>{trace_name}</b><br>"
                        f"Time: %{{x:.2f}}<br>"
                        f"Scaled: %{{y:.3f}}<br>"
                        f"Raw range: [{v_min:.2f}, {v_max:.2f}]<extra></extra>"
                    ),
                    line=dict(width=1.5),
                ))

        fig.update_layout(
            hovermode="x unified",
            xaxis_title="Time (min)",
            yaxis_title="Normalized (0–1)",
            yaxis_range=[0, 1],
            height=500,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True, key="chromatogram")

# ================================================================
# TAB: AUC — pick one run
# ================================================================
with tab_auc:
    if not selected_run_metas:
        st.info("Select at least one run from the sidebar.")
    else:
        run_option_labels = [
            f"{rpm['study_name']} > {rpm['run_name']}" for rpm in selected_run_metas
        ]
        auc_sel_c1, auc_sel_c2 = st.columns(2)
        with auc_sel_c1:
            chosen_run_idx = st.selectbox(
                "Run",
                range(len(run_option_labels)),
                format_func=lambda i: run_option_labels[i],
                key="auc_run",
            )
        with auc_sel_c2:
            wavelength = st.selectbox(
                "Wavelength (nm)",
                [280, 260],
                index=0,
                key="auc_wavelength",
            )

        chosen_rpm = selected_run_metas[chosen_run_idx]
        chosen_run = st.session_state.run_data[chosen_rpm["path"]]
        cmap = build_curve_map(chosen_run)

        if "UV" not in cmap:
            st.info("No curve named 'UV' found in this run.")
        else:
            uv_c = cmap["UV"]
            uv_times = np.array(uv_c["times"])
            uv_values = np.array(uv_c["values"])
            t_min, t_max = float(uv_times.min()), float(uv_times.max())
            unit = uv_c.get("amplitude_unit", "")

            auc_widget_key = f"{chosen_rpm['path']}:UV"

            if st.session_state.auc_range is None:
                st.session_state.auc_range = (t_min, t_max)

            new_range = st.slider(
                "Integration range",
                min_value=t_min,
                max_value=t_max,
                value=st.session_state.auc_range,
                step=0.01,
                key=f"auc_slider_{auc_widget_key}",
            )
            range_start, range_end = new_range

            interp_times = np.linspace(range_start, range_end, 1000)
            interp_values = np.interp(interp_times, uv_times, uv_values)
            auc_raw = float(np.trapezoid(interp_values, interp_times))
            dur = float(interp_times[-1] - interp_times[0])

            conversion_factors = {280: 0.0001, 260: 0.0002}
            auc_conc = auc_raw * conversion_factors[wavelength]

            max_pts = 2000
            if len(uv_times) > max_pts:
                step = max(1, len(uv_times) // max_pts)
                plot_t, plot_v = uv_times[::step], uv_values[::step]
            else:
                plot_t, plot_v = uv_times, uv_values

            plot_seg_mask = (plot_t >= range_start) & (plot_t <= range_end)
            plot_seg_t = plot_t[plot_seg_mask]
            plot_seg_v = plot_v[plot_seg_mask]

            v_at_start = np.interp(range_start, plot_t, plot_v)
            v_at_end = np.interp(range_end, plot_t, plot_v)
            fill_t = np.concatenate([[range_start], plot_seg_t, [range_end]])
            fill_v = np.concatenate([[v_at_start], plot_seg_v, [v_at_end]])

            fig_auc = go.Figure()
            fig_auc.add_trace(go.Scatter(
                x=plot_t, y=plot_v, mode="lines", name="UV",
                line=dict(color="steelblue", width=1.5),
                hovertemplate=f"Time: %{{x:.2f}}<br>Value: %{{y:.2f}} {unit}<extra></extra>",
            ))

            if fill_t.size > 2:
                fig_auc.add_trace(go.Scatter(
                    x=np.concatenate([fill_t, fill_t[::-1]]),
                    y=np.concatenate([fill_v, np.zeros_like(fill_v)]),
                    fill="toself", fillcolor="rgba(70, 130, 180, 0.25)",
                    line=dict(color="rgba(70, 130, 180, 0)"),
                    hoverinfo="skip", showlegend=False,
                ))

            pv_min, pv_max = min(plot_v), max(plot_v)
            fig_auc.add_shape(
                type="line", x0=range_start, y0=pv_min, x1=range_start, y1=pv_max,
                line=dict(color="orange", width=2, dash="dash"))
            fig_auc.add_shape(
                type="line", x0=range_end, y0=pv_min, x1=range_end, y1=pv_max,
                line=dict(color="orange", width=2, dash="dash"))

            fig_auc.update_layout(
                hovermode="x unified",
                xaxis_title="Time (min)",
                yaxis_title=f"Signal ({unit})" if unit else "Signal",
                height=450,
            )

            st.plotly_chart(
                fig_auc,
                use_container_width=True,
                key=f"auc_chart_{auc_widget_key}",
            )

            auc_c1, auc_c2, auc_c3, auc_c4 = st.columns(4)
            auc_c1.metric("AUC", f"{auc_raw:,.2f} {unit}.min")
            auc_c2.metric("Range", f"{range_start:.2f} \u2013 {range_end:.2f} min")
            auc_c3.metric("Duration", f"{dur:.2f} min")
            auc_c4.metric("Mass", f"{auc_conc:,.4f} mg")

# ================================================================
# TAB: Peaks — pick one run
# ================================================================
with tab_peaks:
    runs_with_peaks = [
        rpm for rpm in selected_run_metas
        if not st.session_state.run_data[rpm["path"]]["peak_df"].empty
    ]

    if not runs_with_peaks:
        st.info("No selected runs have peak data.")
    else:
        peak_run_labels = [
            f"{rpm['study_name']} > {rpm['run_name']}" for rpm in runs_with_peaks
        ]
        peak_idx = st.selectbox(
            "Run",
            range(len(peak_run_labels)),
            format_func=lambda i: peak_run_labels[i],
            key="peaks_run",
        )
        peak_run = st.session_state.run_data[runs_with_peaks[peak_idx]["path"]]
        peak_df = peak_run["peak_df"]

        display_cols = [c for c in peak_df.columns if c != "table_name"]
        st.dataframe(
            peak_df[display_cols].style.format({
                c: "{:.2f}" for c in [
                    "start_retention", "max_retention", "end_retention",
                    "width", "width_at_half_height",
                ] if c in peak_df.columns
            })
        )

        fig_peaks = go.Figure(data=[go.Bar(
            x=peak_df["name"],
            y=peak_df["area"],
            marker_color="steelblue",
            hovertemplate="Peak: %{x}<br>Area: %{y:,.2f}<extra></extra>",
        )])
        fig_peaks.update_layout(xaxis_title="Peak", yaxis_title="Area", height=350)
        st.plotly_chart(fig_peaks, use_container_width=True, key="peak_chart")

# ================================================================
# TAB: Phases — pick one run
# ================================================================
with tab_phases:
    runs_with_phases = [
        rpm for rpm in selected_run_metas
        if not st.session_state.run_data[rpm["path"]]["phase_df"].empty
    ]

    if not runs_with_phases:
        st.info("No selected runs have phase data.")
    else:
        phase_run_labels = [
            f"{rpm['study_name']} > {rpm['run_name']}" for rpm in runs_with_phases
        ]
        phase_idx = st.selectbox(
            "Run",
            range(len(phase_run_labels)),
            format_func=lambda i: phase_run_labels[i],
            key="phases_run",
        )
        st.dataframe(st.session_state.run_data[runs_with_phases[phase_idx]["path"]]["phase_df"])

# ================================================================
# TAB: Method Events — pick one run
# ================================================================
with tab_events:
    runs_with_events = [
        rpm for rpm in selected_run_metas
        if not st.session_state.run_data[rpm["path"]]["event_df"].empty
    ]

    if not runs_with_events:
        st.info("No selected runs have method events.")
    else:
        evt_run_labels = [
            f"{rpm['study_name']} > {rpm['run_name']}" for rpm in runs_with_events
        ]
        evt_idx = st.selectbox(
            "Run",
            range(len(evt_run_labels)),
            format_func=lambda i: evt_run_labels[i],
            key="events_run",
        )
        st.dataframe(st.session_state.run_data[runs_with_events[evt_idx]["path"]]["event_df"])

# ================================================================
# TAB: Experimental Params — pick one run
# ================================================================
with tab_params:
    runs_with_params = [
        rpm for rpm in selected_run_metas
        if st.session_state.run_data[rpm["path"]]["exp_params"]
    ]

    if not runs_with_params:
        st.info("No selected runs have experimental parameters.")
    else:
        param_run_labels = [
            f"{rpm['study_name']} > {rpm['run_name']}" for rpm in runs_with_params
        ]
        param_idx = st.selectbox(
            "Run",
            range(len(param_run_labels)),
            format_func=lambda i: param_run_labels[i],
            key="params_run",
        )
        param_run = st.session_state.run_data[runs_with_params[param_idx]["path"]]
        params_df = pd.DataFrame(
            list(param_run["exp_params"].items()), columns=["Parameter", "Value"])
        meta_keys = {"excel_row", "excel_match_date", "excel_match_run"}
        data_params = params_df[~params_df["Parameter"].isin(meta_keys)]
        meta_params = params_df[params_df["Parameter"].isin(meta_keys)]

        if not meta_params.empty:
            st.caption("Excel match: " + ", ".join(
                f"{row['Parameter']}={row['Value']}"
                for _, row in meta_params.iterrows()
            ))

        def fmt_val(v):
            try:
                return f"{float(v):.4g}"
            except (ValueError, TypeError):
                return str(v)

        st.dataframe(data_params.set_index("Parameter").style.format(fmt_val))

# ================================================================
# TAB: System Infos
# ================================================================
with tab_sysinfo:
    first_ri = selected_run_metas[0]["run_info"]
    st.json(first_ri)
