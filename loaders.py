import json
from pathlib import Path
from typing import Any

import pandas as pd


def load_json_run(json_path: str) -> dict[str, Any]:
    """Load a single JSON export file and return structured data."""
    with open(json_path, "r") as f:
        raw = json.load(f)

    study_id = raw.get("study_id", "")
    study_name = raw.get("study_name", "")
    run_info = raw.get("run_info", {})
    column_info = raw.get("column_info", "")
    curves_raw = raw.get("curves", [])
    peak_tables_raw = raw.get("peak_tables", [])
    phases_raw = raw.get("phases", [])
    events_raw = raw.get("method_events", [])
    exp_params = raw.get("experimental_params", {})

    # Build curve list: name -> {name, times, values, amplitude_unit, ...}
    curves = []
    column_volume = None
    for c in curves_raw:
        times = c.get("subsampled_times", [])
        values = c.get("subsampled_data", [])
        if times and values:
            if column_volume is None:
                column_volume = c.get("column_volume")
            curves.append({
                "name": c["name"],
                "times": times,
                "values": values,
                "amplitude_unit": c.get("amplitude_unit", ""),
                "data_type": c.get("data_type", ""),
                "original_points": c.get("original_points", 0),
                "subsampled_points": c.get("subsampled_points", 0),
            })

    # Flatten peak tables into a single DataFrame
    peaks = []
    for table in peak_tables_raw:
        table_name = table.get("name", "")
        for peak in table.get("peaks", []):
            p = dict(peak)
            p["table_name"] = table_name
            peaks.append(p)
    peak_df = pd.DataFrame(peaks) if peaks else pd.DataFrame()

    phase_df = pd.DataFrame(phases_raw) if phases_raw else pd.DataFrame()
    event_df = pd.DataFrame(events_raw) if events_raw else pd.DataFrame()

    return {
        "study_id": study_id,
        "study_name": study_name,
        "run_info": run_info,
        "column_info": column_info,
        "column_volume": column_volume,
        "curves": curves,
        "peak_df": peak_df,
        "phase_df": phase_df,
        "event_df": event_df,
        "exp_params": exp_params,
    }


def discover_json_files(path: str) -> list[str]:
    """Find all .json files in a directory (non-recursive)."""
    p = Path(path)
    if p.is_file() and p.suffix.lower() == ".json":
        return [str(p)]
    if p.is_dir():
        return sorted(str(f) for f in p.iterdir() if f.suffix.lower() == ".json")
    return []
