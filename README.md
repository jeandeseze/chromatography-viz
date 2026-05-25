# Chromatography Viz

Streamlit-based viewer for AKTA Unicorn chromatography data exports. Compare chromatograms across runs, calculate AUC with mass estimation, and inspect peaks, phases, events, and experimental parameters.

## Features

- **Chromatogram comparison** — Overlay up to 3 channels (e.g. UV, Conductivity) from multiple runs, normalized to 0–1
- **Phase overlay** — Color-coded method phase boundaries on chromatograms
- **AUC calculation** — Trapezoidal integration on UV signal with configurable range and mass estimation (280 nm / 260 nm)
- **Peak inspection** — Detected peaks with area bar chart
- **Method phases & events** — Tabular view of phase boundaries and event logs
- **Experimental parameters** — Key-value table of run metadata
- **Flexible x-axis** — Switch between time (min), volume (mL), and column volumes (CV)

## Requirements

- Python >= 3.11
- `uv` package manager

## Installation

```bash
uv sync
```

## Usage

Set the data directory path in `app.py` (line 27) to point to the folder containing your AKTA Unicorn JSON export files, then run:

```bash
streamlit run app.py
```

The app serves on port **8506** (configurable in `.streamlit/config.toml`).

### Making the data directory configurable

The data directory is currently hardcoded in `app.py`. To change it without editing the source, you can override it via environment variable by replacing the `DATA_DIR` block in `app.py` with:

```python
import os
DATA_DIR = Path(os.environ.get("CHROMA_DATA_DIR", "<default path>"))
```

Then launch with:

```bash
CHROMA_DATA_DIR=/path/to/json/exports streamlit run app.py
```

## Project Structure

```
chromatography-viz/
├── app.py              # Main entry point and tab dispatch
├── loaders.py          # AKTA Unicorn JSON parsing
├── run_index.py        # Run discovery, indexing, and caching
├── sidebar.py          # Study/run multi-select sidebar
├── ui_helpers.py       # Shared UI components (x-axis selector, curve helpers)
├── units.py            # Unit conversions (min ↔ mL ↔ CV), phase filtering, phase colors
├── pyproject.toml      # Project metadata and dependencies
├── .streamlit/
│   └── config.toml     # Streamlit server config (port 8506)
└── tabs/
    ├── chromatogram.py # Chromatogram plotting with phase bands
    ├── auc.py          # Area-under-curve calculator and mass estimation
    ├── peaks.py        # Peak detection results table and chart
    ├── phases.py       # Method phase table
    ├── events.py       # Method event log
    ├── params.py       # Experimental parameters
    └── sysinfo.py      # Raw run info dump
```

## Tabs

| Tab | Description |
|---|---|
| **Chromatogram** | Interactive plot of selected channels across runs with optional phase overlay. X-axis switchable between min, mL, and CV. |
| **AUC** | Integration range picker for UV signal. Computes AUC and estimates mass using wavelength-specific conversion factors (280 nm: 0.0001, 260 nm: 0.0002). |
| **Peaks** | Table of detected peaks with area bar chart. |
| **Phases** | Method phase boundaries (start/end times, volumes, names). |
| **Events** | Method event log for the selected run. |
| **Params** | Experimental parameters and metadata. |
| **System Infos** | Raw `run_info` dict from the JSON export. |

## Development

```bash
# Lint and format
ruff check .
ruff format .
```
