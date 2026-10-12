#!/usr/bin/env bash
#
# Deploy the Chromatography Viewer to Azure App Service (Linux Web App).
#
# The dataset is self-contained: it is bundled into the deployment zip from
# ./data and redeployed whenever the data changes.
#
# Prerequisites:
#   - Azure CLI logged in:        az login
#   - A subscription selected:    az account set --subscription "<name-or-id>"
#   - Python 3 on PATH (used to build the deployment zip)
#
# Override any default via environment variables, e.g.:
#   APP_NAME=my-chroma LOCATION=westeurope ./azure/deploy.sh
#
set -euo pipefail
cd "$(dirname "$0")/.."   # run from the repo root so the package is complete

# ---------- Config (override via env) ----------
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-chroma-viz}"
LOCATION="${LOCATION:-francecentral}"
PLAN_NAME="${PLAN_NAME:-asp-chroma-viz}"
APP_NAME="${APP_NAME:-chroma-viz}"
PYTHON_VERSION="${PYTHON_VERSION:-3.11}"
SKU="${SKU:-B1}"                       # B1 = always-on (no idle sleep)
DATA_PATH="/home/site/wwwroot/data"     # where ./data lands in the Web App
STARTUP='streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true'

# ---------- 0. Validate the self-contained dataset ----------
if ! ls data/*.json >/dev/null 2>&1; then
  echo "ERROR: no JSON files found in ./data." >&2
  echo "       Copy your AKTA exports into ./data before deploying." >&2
  exit 1
fi
echo "Bundling $(ls -1 data/*.json | wc -l | tr -d ' ') JSON export(s) from ./data ..."

# ---------- 1. Resource group + App Service plan (Linux) ----------
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --no-wait
az group wait --name "$RESOURCE_GROUP" --created

if ! az appservice plan show --name "$PLAN_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  az appservice plan create --name "$PLAN_NAME" --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" --is-linux --sku "$SKU"
fi

# ---------- 2. Create (or reuse) the Linux Web App ----------
if az webapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  echo "Web app '$APP_NAME' already exists — reusing it."
else
  az webapp create --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" \
    --plan "$PLAN_NAME" --runtime-stack "PYTHON|${PYTHON_VERSION}"
fi

# App settings: point the app at the bundled data + pin the startup command.
az webapp config set --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" \
  --app-settings "CHROMA_DATA_DIR=${DATA_PATH}" \
  --startup-command "$STARTUP"

# ---------- 3. Build the deployment package (code + self-contained data) ----
python - <<'PY'
import os, zipfile
from pathlib import Path

EXCLUDE_DIRS = {
    ".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache",
    "azure", "tests", ".streamlit", ".idea", ".vscode",
}
EXCLUDE_FILES = {"deployment.zip"}

with zipfile.ZipFile("deployment.zip", "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for name in files:
            path = Path(root) / name
            if name in EXCLUDE_FILES or name.endswith(".pyc"):
                continue
            zf.write(path)
print("Wrote deployment.zip")
PY

# ---------- 4. Deploy ----------
az webapp deploy --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --zip deployment.zip

# ---------- 5. Report the URL ----------
HOSTNAME=$(az webapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --query defaultHostname -o tsv)
echo
echo "✔ Deployed."
echo "  URL: https://${HOSTNAME}"
echo
echo "To redeploy with new data: add files to ./data, then re-run ./azure/deploy.sh"
