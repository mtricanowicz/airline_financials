# Deployment

All components target Google Cloud. The primary front end is a static site on
Firebase Hosting; the two services run on Cloud Run; data is refreshed by a
scheduled GitHub Actions workflow.

## Components and hosting

| Component | Path | Hosting |
| --- | --- | --- |
| Static site (primary) | `web/` | Firebase Hosting (`web/out`) |
| Quotes API | `quotes-api/` | Cloud Run |
| Streamlit app (fallback) | `streamlit-app/` | Cloud Run |
| Data build + insights | `core/` | GitHub Actions (scheduled) |

## Workflows

The workflows in `.github/workflows/` assume the repository root contains the
`airline-dashboard/` folder. If `airline-dashboard/` is itself the repository
root, move `.github/` up one level and drop the `airline-dashboard/` prefixes
from the `paths`, `working-directory`, and `--source` values.

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| `ci.yml` | push / PR | Run core tests and the web type-check and build. |
| `deploy.yml` | manual / after CI on main | Deploy quotes-api, Streamlit, and the static site. |
| `refresh-data.yml` | quarterly cron / manual | Rebuild datasets and insights, then redeploy Streamlit and the site. |

## Required secrets

| Secret | Used by | Description |
| --- | --- | --- |
| `GCP_PROJECT_ID` | deploy, refresh | Google Cloud / Firebase project id. |
| `GCP_WORKLOAD_IDP` | deploy, refresh | Workload Identity Federation provider resource. |
| `GCP_DEPLOY_SA` | deploy, refresh | Deploy service account email. |
| `FIREBASE_SERVICE_ACCOUNT` | deploy, refresh | Firebase Hosting deploy credentials (JSON). |
| `QUOTES_API_URL` | deploy, refresh | Public URL of the deployed quotes-api, used by Streamlit and baked into the web build. |
| `SEC_USER_AGENT` | refresh | Contact string for SEC EDGAR requests. |
| `OPENAI_API_KEY` | refresh | Key for embeddings and insight summarization. |

## Manual deploy

```powershell
# From the airline-dashboard folder.

# 1. Quotes API
gcloud run deploy quotes-api --source quotes-api --region us-central1 --allow-unauthenticated

# 2. Streamlit (build from this folder so data is in context)
$env:QUOTES_API_URL = "https://quotes-xxxx.run.app"
$env:STREAMLIT_TAG = "manual-001"
gcloud builds submit . --config deploy/cloudbuild.streamlit.yaml --substitutions=SHORT_SHA="$env:STREAMLIT_TAG",_QUOTES_API_URL="$env:QUOTES_API_URL"

# 3. Static site
cd web
npm ci
$env:NEXT_PUBLIC_QUOTES_API_URL = "https://quotes-xxxx.run.app"
npm run build
cd ..
firebase deploy --only hosting
```

## Local data refresh

```powershell
cd core
pip install -e .
python -m scripts.build_data --years 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026
python -m sec_pipeline.pipeline --airlines AAL DAL UAL LUV ALK JBLU ULCC --years 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026
```

Set `SEC_USER_AGENT` and `OPENAI_API_KEY` in `core/.env` first. For a network
free sample dataset, run `python -m scripts.make_sample_data` instead.
