import streamlit as st


def render(selected_run_metas: list[dict]) -> None:
    runs_with_phases = [
        rpm for rpm in selected_run_metas
        if not st.session_state.run_data[rpm["path"]]["phase_df"].empty
    ]

    if not runs_with_phases:
        st.info("No selected runs have phase data.")
        return

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
