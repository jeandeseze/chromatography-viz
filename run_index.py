import json
from pathlib import Path

from loaders import load_json_run


def discover_json_files(data_dir: Path) -> list[str]:
    """Find all .json files in data_dir (non-recursive)."""
    if not data_dir.is_dir():
        return []
    return sorted(str(f) for f in data_dir.iterdir() if f.suffix.lower() == ".json")


def build_run_index(json_paths: list[str]) -> dict:
    """Build {study_id: {study_name, runs: [...]}} from JSON paths."""
    runs_by_study = {}
    for jp in json_paths:
        try:
            with open(jp, "r") as f:
                raw = json.load(f)
            ri = raw.get("run_info", {})
            study_id = raw.get("study_id", "N/A")
            study_name = raw.get("study_name", study_id)
            run_name = ri.get("name", Path(jp).stem)
            if study_id not in runs_by_study:
                runs_by_study[study_id] = {
                    "study_name": study_name,
                    "runs": [],
                }
            runs_by_study[study_id]["runs"].append({
                "path": jp,
                "run_id": study_id,
                "run_name": run_name,
                "display": f"[{study_id}] {run_name}",
                "study_name": study_name,
                "run_info": ri,
                "column_info": raw.get("column_info", ""),
            })
        except Exception as e:
            import streamlit as st
            st.error(f"Failed to read {Path(jp).name}: {e}")
    return runs_by_study


def load_selected_runs(selected_paths: list[str], run_data: dict) -> dict:
    """Load/run cache selected runs into run_data dict."""
    for rp in selected_paths:
        if rp not in run_data or run_data[rp].get("column_volume") is None:
            run_data[rp] = load_json_run(rp)
    return run_data
