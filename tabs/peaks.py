import plotly.graph_objects as go
import streamlit as st


def render(selected_run_metas: list[dict]) -> None:
    runs_with_peaks = [
        rpm for rpm in selected_run_metas
        if not st.session_state.run_data[rpm["path"]]["peak_df"].empty
    ]

    if not runs_with_peaks:
        st.info("No selected runs have peak data.")
        return

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
