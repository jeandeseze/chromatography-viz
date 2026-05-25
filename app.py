import json as _json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from loaders import load_json_run

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
    ("auc_range_unit", "min"),
    ("chroma_x_unit", "min"),
    ("auc_x_unit", "min"),
    ("show_phases", True),
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
    if rp not in st.session_state.run_data or st.session_state.run_data[rp].get("column_volume") is None:
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


def _xaxis_selector(key, default_unit="min"):
    _x_unit_map = {"Time (min)": "min", "Volume (mL)": "mL", "Column Volumes (CV)": "CV"}
    _x_label_map = {"min": "Time (min)", "mL": "Volume (mL)", "CV": "Column Volumes (CV)"}
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

# --- Helpers ---
def build_curve_map(run):
    return {c["name"]: c for c in run["curves"]}


def get_common_channels(runs):
    if not runs:
        return []
    curve_sets = [set(c["name"] for c in run["curves"]) for run in runs]
    common = curve_sets[0].intersection(*curve_sets[1:])
    return sorted(common)


def _filter_phases(phase_df):
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


def _get_phase_bounds(phase_df):
    if phase_df.empty or not all(
        c in phase_df.columns for c in ("start_time", "end_time", "start_volume", "end_volume")
    ):
        return None, None
    pts = []
    for _, row in phase_df.iterrows():
        st, et, sv, ev = float(row["start_time"]), float(row["end_time"]), float(row["start_volume"]), float(row["end_volume"])
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


def _convert_times(times, phase_df, column_volume, unit):
    if unit == "min":
        return times
    btimes, bvolumes = _get_phase_bounds(phase_df)
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


def _convert_scalar(t, phase_df, column_volume, from_unit, to_unit):
    if from_unit == to_unit:
        return t
    btimes, bvolumes = _get_phase_bounds(phase_df)
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


def _phase_colors(name):
    h = sum(ord(c) for c in name.lower()) % 360
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(h / 360, 0.55, 1)
    return f"rgba({int(r*255)}, {int(g*255)}, {int(b*255)}, 0.15)"


def get_x_label(unit):
    if unit == "min":
        return "Time (min)"
    if unit == "mL":
        return "Volume (mL)"
    return "Column Volumes (CV)"


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

    show_phases = st.checkbox("Show phase overlay", value=st.session_state.show_phases, key="show_phases_chroma")
    st.session_state.show_phases = show_phases

    if len(selected_channels) > 3:
        selected_channels = selected_channels[:3]
        st.warning("Limited to 3 channels.")

    if not selected_channels:
        st.info("Select at least one channel.")
    else:
        x_unit = _xaxis_selector("chroma_x_unit")
        col_vol = selected_runs_data[0].get("column_volume")
        x_label = get_x_label(x_unit)

        fig = go.Figure()

        for run, run_label in zip(selected_runs_data, selected_run_labels):
            cmap = build_curve_map(run)
            raw_phase_df = run.get("phase_df", pd.DataFrame())
            phase_df = _filter_phases(raw_phase_df)
            run_cv = run.get("column_volume", col_vol)
            for ch_name in selected_channels:
                if ch_name not in cmap:
                    continue
                c = cmap[ch_name]
                times = np.array(c.get("times", []), dtype=float)
                values = np.array(c.get("values", []))
                if times.size == 0 or values.size == 0:
                    continue

                v_min, v_max = values.min(), values.max()
                v_range = v_max - v_min if v_max != v_min else 1.0
                scaled = (values - v_min) / v_range

                x_vals = _convert_times(times, phase_df, run_cv, x_unit)

                trace_name = f"{run_label} — {ch_name}"
                fig.add_trace(go.Scattergl(
                    x=x_vals,
                    y=scaled,
                    mode="lines",
                    name=trace_name,
                    hovertemplate=(
                        f"<b>{trace_name}</b><br>"
                        f"{x_label}: %{{x:.2f}}<br>"
                        f"Scaled: %{{y:.3f}}<br>"
                        f"Raw range: [{v_min:.2f}, {v_max:.2f}]<extra></extra>"
                    ),
                    line=dict(width=1.5),
                ))

        if show_phases:
            for run, run_label in zip(selected_runs_data, selected_run_metas):
                raw_phase_df = run.get("phase_df", pd.DataFrame())
                phase_df = _filter_phases(raw_phase_df)
                if phase_df.empty:
                    continue
                run_cv = run.get("column_volume", col_vol)
                for _, row in phase_df.iterrows():
                    pname = row.get("name", "Unknown")
                    s = _convert_scalar(row["start_time"], phase_df, run_cv, "min", x_unit)
                    e = _convert_scalar(row["end_time"], phase_df, run_cv, "min", x_unit)
                    if e <= s:
                        continue
                    fig.add_vrect(
                        x0=s, x1=e,
                        fillcolor=_phase_colors(pname),
                        line=dict(width=0),
                        layer="below",
                    )

            phase_names = []
            for run in selected_runs_data:
                raw_pdf = run.get("phase_df", pd.DataFrame())
                pdf = _filter_phases(raw_pdf)
                if not pdf.empty and "name" in pdf.columns:
                    phase_names.extend(pdf["name"].tolist())
            unique_phases = list(dict.fromkeys(phase_names))

            for pname in unique_phases:
                fig.add_trace(go.Scatter(
                    x=[None], y=[None],
                    mode="markers",
                    marker=dict(color=_phase_colors(pname).replace("0.15", "0.5"), size=8),
                    name=pname,
                    showlegend=True,
                ))

            for run in selected_runs_data:
                raw_phase_df = run.get("phase_df", pd.DataFrame())
                phase_df = _filter_phases(raw_phase_df)
                if phase_df.empty:
                    continue
                run_cv = run.get("column_volume", col_vol)
                for _, row in phase_df.iterrows():
                    pname = row.get("name", "Unknown")
                    s = _convert_scalar(row["start_time"], phase_df, run_cv, "min", x_unit)
                    e = _convert_scalar(row["end_time"], phase_df, run_cv, "min", x_unit)
                    if e <= s:
                        continue
                    mid = (s + e) / 2
                    fig.add_annotation(
                        x=mid, y=-0.10,
                        xref="x",
                        yref="paper",
                        yanchor="top",
                        text=pname,
                        showarrow=False,
                        font=dict(size=10),
                    )

        fig.update_layout(
            hovermode="x unified",
            xaxis_title=x_label,
            yaxis_title="Normalized (0–1)",
            yaxis_range=[0, 1],
            height=500,
            margin=dict(b=80),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, width='stretch', key="chromatogram")

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
        auc_phase_df = _filter_phases(chosen_run.get("phase_df", pd.DataFrame()))
        auc_cv = chosen_run.get("column_volume")

        if "UV" not in cmap:
            st.info("No curve named 'UV' found in this run.")
        else:
            uv_c = cmap["UV"]
            uv_times = np.array(uv_c["times"], dtype=float)
            uv_values = np.array(uv_c["values"])
            t_min, t_max = float(uv_times.min()), float(uv_times.max())
            amp_unit = uv_c.get("amplitude_unit", "")

            x_unit = _xaxis_selector("auc_x_unit")
            x_label = get_x_label(x_unit)

            auc_widget_key = f"{chosen_rpm['path']}:UV"

            if st.session_state.auc_range is None:
                st.session_state.auc_range = (t_min, t_max)
                st.session_state.auc_range_unit = "min"

            if st.session_state.auc_range_unit != x_unit:
                old_unit = st.session_state.auc_range_unit
                old_range = st.session_state.auc_range
                try:
                    new_start = _convert_scalar(old_range[0], auc_phase_df, auc_cv, old_unit, x_unit)
                    new_end = _convert_scalar(old_range[1], auc_phase_df, auc_cv, old_unit, x_unit)
                    st.session_state.auc_range = (new_start, new_end)
                except (ValueError, TypeError):
                    if x_unit == "min":
                        st.session_state.auc_range = (t_min, t_max)
                    else:
                        btimes, bvolumes = _get_phase_bounds(auc_phase_df)
                        if btimes is not None:
                            v_min = float(np.interp(t_min, btimes, bvolumes))
                            v_max = float(np.interp(t_max, btimes, bvolumes))
                            if x_unit == "CV" and auc_cv and auc_cv > 0:
                                v_min, v_max = v_min / auc_cv, v_max / auc_cv
                            st.session_state.auc_range = (v_min, v_max)
                        else:
                            st.session_state.auc_range = (t_min, t_max)
                st.session_state.auc_range_unit = x_unit

            if x_unit == "min":
                s_min, s_max = t_min, t_max
                slider_step = 0.01
            else:
                btimes, bvolumes = _get_phase_bounds(auc_phase_df)
                if btimes is not None:
                    v_min_b = float(np.interp(t_min, btimes, bvolumes))
                    v_max_b = float(np.interp(t_max, btimes, bvolumes))
                    if x_unit == "CV" and auc_cv and auc_cv > 0:
                        s_min, s_max = v_min_b / auc_cv, v_max_b / auc_cv
                    else:
                        s_min, s_max = v_min_b, v_max_b
                    slider_step = max(0.01, (s_max - s_min) / 1000)
                else:
                    s_min, s_max = t_min, t_max
                    slider_step = 0.01

            new_range = st.slider(
                "Integration range",
                min_value=s_min,
                max_value=s_max,
                value=st.session_state.auc_range,
                step=slider_step,
                key=f"auc_slider_{auc_widget_key}_{x_unit}",
                format=f"%.2f {x_unit}",
            )
            range_start_disp, range_end_disp = new_range
            st.session_state.auc_range = new_range

            range_start_t = _convert_scalar(range_start_disp, auc_phase_df, auc_cv, x_unit, "min")
            range_end_t = _convert_scalar(range_end_disp, auc_phase_df, auc_cv, x_unit, "min")

            interp_times = np.linspace(range_start_t, range_end_t, 1000)
            interp_values = np.interp(interp_times, uv_times, uv_values)
            auc_raw = float(np.trapezoid(interp_values, interp_times))
            dur_t = float(interp_times[-1] - interp_times[0])

            dur_disp = range_end_disp - range_start_disp

            conversion_factors = {280: 0.0001, 260: 0.0002}
            auc_conc = auc_raw * conversion_factors[wavelength]

            max_pts = 2000
            if len(uv_times) > max_pts:
                step = max(1, len(uv_times) // max_pts)
                plot_t, plot_v = uv_times[::step], uv_values[::step]
            else:
                plot_t, plot_v = uv_times, uv_values

            plot_x = _convert_times(plot_t, auc_phase_df, auc_cv, x_unit)

            plot_seg_mask = (plot_x >= range_start_disp) & (plot_x <= range_end_disp)
            plot_seg_x = plot_x[plot_seg_mask]
            plot_seg_v = plot_v[plot_seg_mask]

            v_at_start = np.interp(range_start_t, plot_t, plot_v)
            v_at_end = np.interp(range_end_t, plot_t, plot_v)
            fill_x = np.concatenate([[range_start_disp], plot_seg_x, [range_end_disp]])
            fill_v = np.concatenate([[v_at_start], plot_seg_v, [v_at_end]])

            fig_auc = go.Figure()
            fig_auc.add_trace(go.Scatter(
                x=plot_x, y=plot_v, mode="lines", name="UV",
                line=dict(color="steelblue", width=1.5),
                hovertemplate=f"{x_label}: %{{x:.2f}}<br>Value: %{{y:.2f}} {amp_unit}<extra></extra>",
            ))

            if fill_x.size > 2:
                fig_auc.add_trace(go.Scatter(
                    x=np.concatenate([fill_x, fill_x[::-1]]),
                    y=np.concatenate([fill_v, np.zeros_like(fill_v)]),
                    fill="toself", fillcolor="rgba(70, 130, 180, 0.25)",
                    line=dict(color="rgba(70, 130, 180, 0)"),
                    hoverinfo="skip", showlegend=False,
                ))

            pv_min, pv_max = float(min(plot_v)), float(max(plot_v))
            fig_auc.add_shape(
                type="line", x0=range_start_disp, y0=pv_min, x1=range_start_disp, y1=pv_max,
                line=dict(color="orange", width=2, dash="dash"))
            fig_auc.add_shape(
                type="line", x0=range_end_disp, y0=pv_min, x1=range_end_disp, y1=pv_max,
                line=dict(color="orange", width=2, dash="dash"))

            if st.session_state.show_phases and not auc_phase_df.empty:
                for _, row in auc_phase_df.iterrows():
                    pname = row.get("name", "Unknown")
                    s = _convert_scalar(row["start_time"], auc_phase_df, auc_cv, "min", x_unit)
                    e = _convert_scalar(row["end_time"], auc_phase_df, auc_cv, "min", x_unit)
                    if e <= s:
                        continue
                    fig_auc.add_vrect(
                        x0=s, x1=e,
                        fillcolor=_phase_colors(pname),
                        line=dict(width=0),
                        layer="below",
                    )

                unique_phases = auc_phase_df["name"].unique().tolist() if "name" in auc_phase_df.columns else []
                for pname in unique_phases:
                    fig_auc.add_trace(go.Scatter(
                        x=[None], y=[None],
                        mode="markers",
                        marker=dict(color=_phase_colors(pname).replace("0.15", "0.5"), size=8),
                        name=pname,
                        showlegend=True,
                    ))

                for _, row in auc_phase_df.iterrows():
                    pname = row.get("name", "Unknown")
                    s = _convert_scalar(row["start_time"], auc_phase_df, auc_cv, "min", x_unit)
                    e = _convert_scalar(row["end_time"], auc_phase_df, auc_cv, "min", x_unit)
                    if e <= s:
                        continue
                    mid = (s + e) / 2
                    fig_auc.add_annotation(
                        x=mid, y=-0.10,
                        xref="x",
                        yref="paper",
                        yanchor="top",
                        text=pname,
                        showarrow=False,
                        font=dict(size=10),
                    )

            fig_auc.update_layout(
                hovermode="x unified",
                xaxis_title=x_label,
                yaxis_title=f"Signal ({amp_unit})" if amp_unit else "Signal",
                height=450,
                margin=dict(b=80),
            )

            st.plotly_chart(
                fig_auc,
                width='stretch',
                key=f"auc_chart_{auc_widget_key}",
            )

            auc_unit_label = x_unit
            auc_c1, auc_c2, auc_c3, auc_c4 = st.columns(4)
            auc_c1.metric("AUC", f"{auc_raw:,.2f} {amp_unit}.{auc_unit_label}")
            auc_c2.metric("Range", f"{range_start_disp:.2f} \u2013 {range_end_disp:.2f} {auc_unit_label}")
            auc_c3.metric("Duration", f"{dur_disp:.2f} {auc_unit_label}")
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
        st.plotly_chart(fig_peaks, width='stretch', key="peak_chart")

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

        display_params = data_params.copy()
        display_params["Value"] = display_params["Value"].astype(str)
        st.dataframe(display_params.set_index("Parameter").style.format(fmt_val))

# ================================================================
# TAB: System Infos
# ================================================================
with tab_sysinfo:
    first_ri = selected_run_metas[0]["run_info"]
    st.json(first_ri)
