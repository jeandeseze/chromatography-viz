import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from units import (
    convert_scalar,
    convert_times,
    filter_phases,
    get_x_label,
    phase_colors,
)
from ui_helpers import build_curve_map, get_common_channels, xaxis_selector


def render(selected_run_metas: list[dict]) -> None:
    selected_runs_data = [
        st.session_state.run_data[rpm["path"]] for rpm in selected_run_metas
    ]
    selected_run_labels = [
        f"{rpm['study_name']} > {rpm['run_name']}" for rpm in selected_run_metas
    ]

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
        return

    x_unit = xaxis_selector("chroma_x_unit")
    col_vol = selected_runs_data[0].get("column_volume")
    x_label = get_x_label(x_unit)

    fig = go.Figure()

    for run, run_label in zip(selected_runs_data, selected_run_labels):
        cmap = build_curve_map(run)
        raw_phase_df = run.get("phase_df", pd.DataFrame())
        phase_df_filtered = filter_phases(raw_phase_df)
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

            x_vals = convert_times(times, phase_df_filtered, run_cv, x_unit)

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
                line=dict(width=2.5),
            ))

    if show_phases:
        _render_phase_bands(fig, selected_runs_data, selected_run_metas, col_vol, x_unit)

    fig.update_layout(
        hovermode="x unified",
        xaxis_title=x_label,
        yaxis_title="Normalized (0–1)",
        yaxis_range=[0, 1],
        height=500,
        margin=dict(b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, width='stretch', key="chromatogram")


def _render_phase_bands(fig, selected_runs_data, selected_run_metas, col_vol, x_unit):
    for run, run_label in zip(selected_runs_data, selected_run_metas):
        raw_phase_df = run.get("phase_df", pd.DataFrame())
        phase_df_filtered = filter_phases(raw_phase_df)
        if phase_df_filtered.empty:
            continue
        run_cv = run.get("column_volume", col_vol)
        for _, row in phase_df_filtered.iterrows():
            pname = row.get("name", "Unknown")
            s = convert_scalar(row["start_time"], phase_df_filtered, run_cv, "min", x_unit)
            e = convert_scalar(row["end_time"], phase_df_filtered, run_cv, "min", x_unit)
            if e <= s:
                continue
            fig.add_vrect(
                x0=s, x1=e,
                fillcolor=phase_colors(pname),
                line=dict(width=0),
                layer="below",
            )

    y_positions = [0.96, 0.92, 0.88]
    idx = 0
    for run in selected_runs_data:
        raw_phase_df = run.get("phase_df", pd.DataFrame())
        phase_df_filtered = filter_phases(raw_phase_df)
        if phase_df_filtered.empty:
            continue
        run_cv = run.get("column_volume", col_vol)
        for _, row in phase_df_filtered.iterrows():
            pname = row.get("name", "Unknown")
            s = convert_scalar(row["start_time"], phase_df_filtered, run_cv, "min", x_unit)
            e = convert_scalar(row["end_time"], phase_df_filtered, run_cv, "min", x_unit)
            if e <= s:
                continue
            mid = (s + e) / 2
            pos = y_positions[idx % 3]
            fig.add_annotation(
                x=mid, y=pos,
                xref="x",
                yref="paper",
                yanchor="bottom",
                text=f"<i>{pname}</i>",
                showarrow=False,
                font=dict(size=10),
            )
            idx += 1
