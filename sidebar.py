import streamlit as st


def render_sidebar(runs_by_study: dict) -> None:
    """Render sidebar with study filter and run checkboxes."""
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

    available_paths = set(
        rm["path"] for sid in selected_studies for rm in runs_by_study[sid]["runs"]
    )
    st.session_state.selected_runs = list(new_selected & available_paths)

    if not st.session_state.selected_runs:
        st.info("Select at least one run from the sidebar.")
        st.stop()

    st.sidebar.success(f"{len(st.session_state.selected_runs)} run(s) selected")
