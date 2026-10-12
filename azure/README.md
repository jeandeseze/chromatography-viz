# Deploy to Azure App Service

Run the Chromatography Viewer as an **Azure App Service (Linux Web App)**,
serving Streamlit directly. No Docker required.

## Model: self-contained data

The app is stateless (no database) and reads AKTA JSON exports from a
directory. For deployment, that directory is **bundled into the deployment
package**:

```
./data/*.json  ──(zipped)──►  /home/site/wwwroot/data  ──►  CHROMA_DATA_DIR
```

**Redeploying with new data = add JSONs to `./data`, re-run `deploy.sh`.**
App Service is ephemeral (the filesystem resets on each deploy), so baking the
data into the package is exactly the right fit — there is no separate store to
keep in sync.

## What this adds to the repo

| File               | Purpose                                                            |
|--------------------|--------------------------------------------------------------------|
| `requirements.txt` | Pinned runtime deps (App Service installs these into its venv).    |
| `appsettings.json` | Sets the Streamlit startup command (`$PORT`-aware).                |
| `.python-version`  | Pins Python 3.11 for the Web App.                                  |
| `azure/deploy.sh`  | Creates the Web App and deploys the self-contained package.        |
| `data/`            | Your JSON exports (git-ignored, shipped inside the zip).           |

The app code already supports an overridable data path: `app.py` reads
`CHROMA_DATA_DIR` (defaults to your local folder for local dev).

## Prerequisites

- **Azure CLI** installed and logged in:
  ```bash
  az login
  az account set --subscription "<your-subscription>"
  ```
- **Python 3** on PATH (only used to build the deployment zip).
- At least one `.json` file in `./data`.

## Deploy

```bash
./azure/deploy.sh
```

This will:

1. Create a resource group + Linux App Service plan (B1, always-on).
2. Create the Linux Web App with a Python 3.11 stack (reuses it on redeploys).
3. Set `CHROMA_DATA_DIR=/home/site/wwwroot/data` and the Streamlit startup command.
4. Zip the app + `./data` and deploy it.
5. Print the public URL.

Useful overrides:

```bash
APP_NAME=my-chroma LOCATION=westeurope PYTHON_VERSION=3.11 ./azure/deploy.sh
```

## Redeploy with new data

```bash
# 1. put new AKTA exports into ./data
cp /path/to/new_exports/*.json data/
# 2. redeploy
./azure/deploy.sh
```

That's the whole update loop — no migration, no store to manage.

## First-run checklist (one-time)

1. `az login` and select your subscription.
2. Drop your AKTA JSON exports into `./data`.
3. `./azure/deploy.sh`.
4. Open the printed URL. If the sidebar is empty, the data folder didn't land
   in the package — check step 2 and redeploy.

## Notes & troubleshooting

- **App name must be globally unique.** If `chroma-viz` is taken, set
  `APP_NAME=<unique>` and use the same value for all subsequent deploys.
- **Idle sleep:** the default `B1` plan is always-on. The cheaper `F1` plan
  sleeps after inactivity (cold start on first request). Change with `SKU=F1`.
- **Data size:** the dataset ships inside the package. If it grows very large
  (many GBs), App Service package limits may apply — at that point, switch to
  a Blob/Azure Files mount and point `CHROMA_DATA_DIR` at it.
- **Port:** App Service assigns the port via `$PORT`; the startup command in
  `appsettings.json` binds Streamlit to it. Don't hardcode a port.
- **Verify the startup command** if the site returns 404/503:
  ```bash
  az webapp show --name <APP> --resource-group <RG> --query config -o table
  az webapp log tail --name <APP> --resource-group <RG>
  ```
- **Cost:** App Service (Linux) B1 is a paid SKU. Delete it when done:
  ```bash
  az group delete --name rg-chroma-viz --yes
  ```

## (Optional) Container Apps / ACI

If you later prefer a container, the app is already container-ready: it's
stateless and reads `CHROMA_DATA_DIR`. A Dockerfile can be added on top — the
`CHROMA_DATA_DIR` abstraction is the only app change needed either way.
