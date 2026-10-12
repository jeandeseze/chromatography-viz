# Data (self-contained dataset)

This folder holds the AKTA Unicorn **JSON exports** that the app visualizes.
It is the *single source of truth* for the deployed app: the dataset travels
with the deployment package and is baked into the Web App, and the app reads
it from `CHROMA_DATA_DIR` (set to `/home/site/wwwroot/data` on Azure).

## Workflow (redeploy on new data)

1. Drop your `.json` export files into this folder (`data/`).
   One JSON file per run. Non-recursive: files must live directly in `data/`.
2. Rebuild the deployment package and redeploy — see `azure/README.md`.

```
data/
├── study_A_run1.json
├── study_A_run2.json
└── study_B_run1.json
```

## Notes

- Contents are **git-ignored** (`data/*`), except this `README.md`.
  They are still shipped inside the deployment zip (see `azure/deploy.sh`).
- Local development does not need this folder: `app.py` defaults to your local
  AKTA export folder and can be overridden with `CHROMA_DATA_DIR`.
- If this folder is empty when you deploy, the app will show
  "Data directory not found or empty" — add exports before deploying.
