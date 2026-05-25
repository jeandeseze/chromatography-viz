import streamlit as st


def render(selected_run_metas: list[dict]) -> None:
    if not selected_run_metas:
        return
    first_ri = selected_run_metas[0]["run_info"]
    st.json(first_ri)
