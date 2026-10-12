import shutil
import subprocess
from pathlib import Path

import streamlit as st

BATCH_EXPORT_SCRIPT = (
    Path(__file__).resolve().parent
    / "../../Julia/AKTAUnicornParser/scripts/batch_export.jl"
).resolve()

# Where batch_export.jl writes its JSON exports (its configured output_dir).
# After a successful run we copy these into the app's data folder so it stays
# self-contained and ready to deploy.
BATCH_EXPORT_OUTPUT_DIR = (
    "/mnt/c/Users/JeandeSEZE/Veyton/"
    "C-R&D-Process dev - Documents/"
    "20_Internal Studies/05_Model studies/xtodata"
)


def _copy_exports_to(data_dir: Path) -> int:
    """Copy freshly exported JSON files into the app's data directory.

    Returns the number of files copied (0 if the source folder is missing).
    """
    src = Path(BATCH_EXPORT_OUTPUT_DIR)
    if not src.is_dir():
        return 0
    data_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for f in sorted(src.glob("*.json")):
        shutil.copy2(f, data_dir / f.name)
        copied += 1
    return copied


def _run_batch_export(data_dir: Path) -> None:
    """Run the Julia batch export script, then sync its output into data_dir."""
    if not BATCH_EXPORT_SCRIPT.is_file():
        st.error(f"Batch export script not found: {BATCH_EXPORT_SCRIPT}")
        return
    # AKTAUnicornParser is a local dev package: activate its own project
    # environment so `using AKTAUnicornParser` resolves.
    julia_project = str(BATCH_EXPORT_SCRIPT.parent.parent)
    julia_bin = shutil.which("julia") or str(Path.home() / ".juliaup/bin/julia")
    with st.spinner("Running batch_export.jl ... this can take a few minutes"):
        try:
            proc = subprocess.run(
                [julia_bin, f"--project={julia_project}", str(BATCH_EXPORT_SCRIPT)],
                capture_output=True,
                text=True,
                timeout=3600,
            )
        except FileNotFoundError:
            st.error(f"julia executable not found (looked for: {julia_bin})")
            return
        except subprocess.TimeoutExpired:
            st.error("Batch export timed out after 1 hour.")
            return
    if proc.returncode == 0:
        # Sync the fresh exports into the app's data folder, then refresh the
        # run cache so newly exported JSON files are picked up.
        n = _copy_exports_to(data_dir)
        st.session_state.run_data = {}
        st.success(
            f"Batch export finished — synced {n} JSON file(s) into the data folder."
        )
    else:
        st.error(f"Batch export failed (exit code {proc.returncode}).")
    if proc.stdout:
        st.code(proc.stdout[-4000:], language=None)
    if proc.returncode != 0 and proc.stderr:
        st.code(proc.stderr[-4000:], language=None)


def render_sidebar(runs_by_study: dict, data_dir: Path) -> None:
    """Render sidebar with study filter and run checkboxes."""
    # Batch export runs a local Julia script; only offer it where that script
    # exists (i.e. not in the self-contained Azure deployment).
    if BATCH_EXPORT_SCRIPT.is_file():
        if st.sidebar.button("Run batch export", type="primary", width="stretch"):
            _run_batch_export(data_dir)

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
