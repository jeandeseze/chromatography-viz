import pandas as pd
import streamlit as st


def render(selected_run_metas: list[dict]) -> None:
    runs_with_params = [
        rpm for rpm in selected_run_metas
        if st.session_state.run_data[rpm["path"]]["exp_params"]
    ]

    if not runs_with_params:
        st.info("No selected runs have experimental parameters.")
        return

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
