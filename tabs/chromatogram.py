import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from units import (
    convert_scalar,
    convert_times,
    filter_phases,
    get_elution_start,
    get_x_label,
    phase_colors,
)
from ui_helpers import build_curve_map, get_common_channels, xaxis_selector


def render(selected_run_metas: list[dict]) -> None:
    selected_runs_data = [
        st.session_state.run_data[rpm["path"]] for rpm in selected_run_metas
    ]
    selected_run_labels = [
        rpm['run_name'] for rpm in selected_run_metas
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

    normalize = st.checkbox("Normalize curves", value=True, key="chroma_normalize")

    align_elution = st.checkbox("Align to elution start", value=False, key="chroma_align_elution")

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
    left_values = []
    right_values = []

    dual_axis = not normalize and len(selected_channels) >= 2
    left_ch = selected_channels[0] if dual_axis else None
    right_ch = selected_channels[1] if dual_axis else None

    for run, run_label in zip(selected_runs_data, selected_run_labels):
        cmap = build_curve_map(run)
        raw_phase_df = run.get("phase_df", pd.DataFrame())
        phase_df_filtered = filter_phases(raw_phase_df)
        run_cv = run.get("column_volume", col_vol)

        elution_offset = None
        if align_elution:
            elution_time = get_elution_start(raw_phase_df)
            if elution_time is not None:
                elution_offset = convert_scalar(elution_time, phase_df_filtered, run_cv, "min", x_unit)

        for ch_name in selected_channels:
            if ch_name not in cmap:
                continue
            c = cmap[ch_name]
            times = np.array(c.get("times", []), dtype=float)
            values = np.array(c.get("values", []))
            if times.size == 0 or values.size == 0:
                continue

            plot_values = values
            if normalize:
                v_min, v_max = values.min(), values.max()
                v_range = v_max - v_min if v_max != v_min else 1.0
                plot_values = (values - v_min) / v_range
                hover_extra = f"Scaled: %{{y:.3f}}<br>Raw range: [{v_min:.2f}, {v_max:.2f}]"
            else:
                hover_extra = f"Value: %{{y:.3f}}"

            x_vals = convert_times(times, phase_df_filtered, run_cv, x_unit)

            if align_elution and elution_offset is not None:
                x_vals = np.array(x_vals) - elution_offset

            if dual_axis and ch_name == left_ch:
                yaxis = "y"
                left_values.extend(plot_values.tolist())
            elif dual_axis and ch_name == right_ch:
                yaxis = "y2"
                right_values.extend(plot_values.tolist())
            else:
                yaxis = "y"
                left_values.extend(plot_values.tolist())

            trace_name = f"{run_label} — {ch_name}"
            fig.add_trace(go.Scattergl(
                x=x_vals,
                y=plot_values,
                mode="lines",
                name=trace_name,
                yaxis=yaxis if dual_axis else None,
                hovertemplate=(
                    f"<b>{trace_name}</b><br>"
                    f"{x_label}: %{{x:.2f}}<br>"
                    f"{hover_extra}<extra></extra>"
                ),
                line=dict(width=2.5),
            ))

    if show_phases:
        _render_phase_bands(fig, selected_runs_data, selected_run_metas, col_vol, x_unit, align_elution)

    layout_kwargs = {
        "hovermode": "x unified",
        "xaxis_title": x_label if not align_elution else f"{x_label} (offset to elution start)",
        "height": 500,
        "margin": dict(b=50),
        "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    }

    if dual_axis:
        def _range(vals):
            if not vals:
                return None
            mn, mx = min(vals), max(vals)
            pad = (mx - mn) * 0.05 if mx != mn else 1.0
            return [mn - pad, mx + pad]

        layout_kwargs["yaxis_title"] = left_ch
        layout_kwargs["yaxis_range"] = _range(left_values)
        layout_kwargs["yaxis2"] = {
            "title": right_ch,
            "overlaying": "y",
            "side": "right",
            "range": _range(right_values),
        }
    else:
        all_values = left_values + right_values
        y_title = "Normalized (0–1)" if normalize else "Raw Signal"
        layout_kwargs["yaxis_title"] = y_title
        layout_kwargs["yaxis_range"] = [0, 1] if normalize else None
        if not normalize and all_values:
            mn, mx = min(all_values), max(all_values)
            pad = (mx - mn) * 0.05 if mx != mn else 1.0
            layout_kwargs["yaxis_range"] = [mn - pad, mx + pad]

    fig.update_layout(**layout_kwargs)
    st.plotly_chart(fig, width='stretch', key="chromatogram")

    _render_params_table(selected_run_metas, selected_runs_data)


def _render_phase_bands(fig, selected_runs_data, selected_run_metas, col_vol, x_unit, align_elution=False):
    for run, run_label in zip(selected_runs_data, selected_run_metas):
        raw_phase_df = run.get("phase_df", pd.DataFrame())
        phase_df_filtered = filter_phases(raw_phase_df)
        if phase_df_filtered.empty:
            continue
        run_cv = run.get("column_volume", col_vol)

        elution_offset = None
        if align_elution:
            elution_time = get_elution_start(raw_phase_df)
            if elution_time is not None:
                elution_offset = convert_scalar(elution_time, phase_df_filtered, run_cv, "min", x_unit)

        for _, row in phase_df_filtered.iterrows():
            pname = row.get("name", "Unknown")
            s = convert_scalar(row["start_time"], phase_df_filtered, run_cv, "min", x_unit)
            e = convert_scalar(row["end_time"], phase_df_filtered, run_cv, "min", x_unit)
            if e <= s:
                continue
            if align_elution and elution_offset is not None:
                s = s - elution_offset
                e = e - elution_offset
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

        elution_offset = None
        if align_elution:
            elution_time = get_elution_start(raw_phase_df)
            if elution_time is not None:
                elution_offset = convert_scalar(elution_time, phase_df_filtered, run_cv, "min", x_unit)

        for _, row in phase_df_filtered.iterrows():
            pname = row.get("name", "Unknown")
            s = convert_scalar(row["start_time"], phase_df_filtered, run_cv, "min", x_unit)
            e = convert_scalar(row["end_time"], phase_df_filtered, run_cv, "min", x_unit)
            if e <= s:
                continue
            mid = (s + e) / 2
            if align_elution and elution_offset is not None:
                mid = mid - elution_offset
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


def _render_params_table(selected_run_metas: list[dict], selected_runs_data: list[dict]) -> None:
    meta_keys = {"excel_row", "excel_match_date", "excel_match_run"}

    params_by_run = {}
    all_keys = []
    for rpm, run in zip(selected_run_metas, selected_runs_data):
        exp_params = run.get("exp_params", {})
        if not exp_params:
            continue
        run_label = rpm['run_name']
        filtered = {k: v for k, v in exp_params.items() if k not in meta_keys}
        if not filtered:
            continue
        params_by_run[run_label] = filtered
        for k in filtered:
            if k not in all_keys:
                all_keys.append(k)

    if not params_by_run:
        return

    def fmt_val(v):
        try:
            return f"{float(v):.4g}"
        except (ValueError, TypeError):
            return str(v)

    st.markdown("#### Experimental Parameters")

    run_labels = list(params_by_run.keys())
    html = '<table style="width:100%; table-layout:fixed; border-collapse:collapse;">\n'
    html += '<thead><tr><th style="width:200px; text-align:left; padding:4px; border:1px solid #ddd;">Parameter</th>'
    for rl in run_labels:
        html += f'<th style="width:120px; text-align:left; padding:4px; border:1px solid #ddd; word-wrap:break-word; white-space:normal;">{rl}</th>'
    html += '</tr></thead>\n<tbody>\n'
    for k in all_keys:
        html += f'<tr><td style="padding:4px; border:1px solid #ddd;">{k}</td>'
        for rl in run_labels:
            val = fmt_val(params_by_run[rl].get(k, "")) if k in params_by_run[rl] else ""
            html += f'<td style="padding:4px; border:1px solid #ddd; word-wrap:break-word; white-space:normal;">{val}</td>'
        html += '</tr>\n'
    html += '</tbody></table>'
    st.markdown(html, unsafe_allow_html=True)
