# Data (self-contained dataset)

This folder holds the AKTA Unicorn **JSON exports** that the app visualizes.
It is the *single source of truth* for the app: the dataset travels with the
deployment package and the app reads it from here (`./data`, relative to
`app.py` — i.e. `/home/site/wwwroot/data` on Azure).

## Workflow (redeploy on new data)

1. Click **"Run batch export"** in the sidebar. This runs `batch_export.jl`
   and automatically copies the fresh JSON exports into this folder, so it
   always reflects the latest data.
   (Or drop `.json` files here manually — one file per run, directly in `data/`.)
2. Redeploy the app — see `azure/README.md`.

```
data/
├── study_A_run1.json
├── study_A_run2.json
└── study_B_run1.json
```

## Notes

- Contents are **git-ignored** (`data/*`), except this `README.md`.
  They are still shipped inside the deployment zip (see `azure/deploy.sh`).
- `app.py` defaults to this folder (`./data`), so it works both locally and on
  Azure with no configuration. Override with `CHROMA_DATA_DIR` to point
  elsewhere.
- If this folder is empty when you deploy, the app will show
  "Data directory not found or empty" — run the batch export before deploying.
