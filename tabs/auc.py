import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from units import (
    convert_scalar,
    convert_times,
    filter_phases,
    get_phase_bounds,
    get_x_label,
    phase_colors,
)
from ui_helpers import build_curve_map, xaxis_selector


def render(selected_run_metas: list[dict]) -> None:
    if not selected_run_metas:
        st.info("Select at least one run from the sidebar.")
        return

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
    auc_phase_df = filter_phases(chosen_run.get("phase_df", pd.DataFrame()))
    auc_cv = chosen_run.get("column_volume")

    if "UV" not in cmap:
        st.info("No curve named 'UV' found in this run.")
        return

    uv_c = cmap["UV"]
    uv_times = np.array(uv_c["times"], dtype=float)
    uv_values = np.array(uv_c["values"])
    t_min, t_max = float(uv_times.min()), float(uv_times.max())
    amp_unit = uv_c.get("amplitude_unit", "")

    x_unit = xaxis_selector("auc_x_unit")
    x_label = get_x_label(x_unit)

    auc_widget_key = f"{chosen_rpm['path']}:UV"

    _sync_auc_range(x_unit, auc_phase_df, auc_cv, t_min, t_max)

    s_min, s_max, slider_step = _slider_bounds(x_unit, auc_phase_df, auc_cv, t_min, t_max)

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

    range_start_t = convert_scalar(range_start_disp, auc_phase_df, auc_cv, x_unit, "min")
    range_end_t = convert_scalar(range_end_disp, auc_phase_df, auc_cv, x_unit, "min")

    interp_times = np.linspace(range_start_t, range_end_t, 1000)
    interp_values = np.interp(interp_times, uv_times, uv_values)

    interp_volumes = convert_times(interp_times, auc_phase_df, auc_cv, "mL")
    auc_raw = float(np.trapezoid(interp_values, interp_volumes))

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

    plot_x = convert_times(plot_t, auc_phase_df, auc_cv, x_unit)

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
        _render_auc_phases(fig_auc, auc_phase_df, auc_cv, x_unit)

    fig_auc.update_layout(
        hovermode="x unified",
        xaxis_title=x_label,
        yaxis_title=f"Signal ({amp_unit})" if amp_unit else "Signal",
        height=450,
        margin=dict(b=50),
    )

    st.plotly_chart(
        fig_auc,
        width='stretch',
        key=f"auc_chart_{auc_widget_key}",
    )

    auc_c1, auc_c2, auc_c3, auc_c4 = st.columns(4)
    auc_c1.metric("AUC", f"{auc_raw:,.2f} {amp_unit}.mL")
    auc_c2.metric("Range", f"{range_start_disp:.2f} \u2013 {range_end_disp:.2f} {x_unit}")
    auc_c3.metric("Duration", f"{dur_disp:.2f} {x_unit}")
    auc_c4.metric("Mass", f"{auc_conc:,.4f} mg")


def _sync_auc_range(x_unit, auc_phase_df, auc_cv, t_min, t_max):
    if st.session_state.auc_range is None:
        st.session_state.auc_range = (t_min, t_max)
        st.session_state.auc_range_unit = "min"

    if st.session_state.auc_range_unit != x_unit:
        old_unit = st.session_state.auc_range_unit
        old_range = st.session_state.auc_range
        try:
            new_start = convert_scalar(old_range[0], auc_phase_df, auc_cv, old_unit, x_unit)
            new_end = convert_scalar(old_range[1], auc_phase_df, auc_cv, old_unit, x_unit)
            st.session_state.auc_range = (new_start, new_end)
        except (ValueError, TypeError):
            if x_unit == "min":
                st.session_state.auc_range = (t_min, t_max)
            else:
                btimes, bvolumes = get_phase_bounds(auc_phase_df)
                if btimes is not None:
                    v_min = float(np.interp(t_min, btimes, bvolumes))
                    v_max = float(np.interp(t_max, btimes, bvolumes))
                    if x_unit == "CV" and auc_cv and auc_cv > 0:
                        v_min, v_max = v_min / auc_cv, v_max / auc_cv
                    st.session_state.auc_range = (v_min, v_max)
                else:
                    st.session_state.auc_range = (t_min, t_max)
        st.session_state.auc_range_unit = x_unit


def _slider_bounds(x_unit, auc_phase_df, auc_cv, t_min, t_max):
    if x_unit == "min":
        return t_min, t_max, 0.01

    btimes, bvolumes = get_phase_bounds(auc_phase_df)
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
    return s_min, s_max, slider_step


def _render_auc_phases(fig, auc_phase_df, auc_cv, x_unit):
    for _, row in auc_phase_df.iterrows():
        pname = row.get("name", "Unknown")
        s = convert_scalar(row["start_time"], auc_phase_df, auc_cv, "min", x_unit)
        e = convert_scalar(row["end_time"], auc_phase_df, auc_cv, "min", x_unit)
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
    for _, row in auc_phase_df.iterrows():
        pname = row.get("name", "Unknown")
        s = convert_scalar(row["start_time"], auc_phase_df, auc_cv, "min", x_unit)
        e = convert_scalar(row["end_time"], auc_phase_df, auc_cv, "min", x_unit)
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
