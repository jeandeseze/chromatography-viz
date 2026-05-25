import streamlit as st


def render(selected_run_metas: list[dict]) -> None:
    runs_with_events = [
        rpm for rpm in selected_run_metas
        if not st.session_state.run_data[rpm["path"]]["event_df"].empty
    ]

    if not runs_with_events:
        st.info("No selected runs have method events.")
        return

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
