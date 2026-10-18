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

### Manual refresh parameters

In GitHub Actions, select **Refresh data > Run workflow**:

| Input | Default | Behavior |
| --- | --- | --- |
| `airlines`, `years`, `periods` | Current airline set / latest completed period | Space-separated lists; all selected combinations are eligible for financial updates. |
| `sources` | `both` | `both` maps to `--sources auto manual`; `auto` or `manual` runs only that source. |
| `overwrite` | `false` | Replace supplied populated financial metrics only in the selected slice; otherwise fill gaps only. Nulls never erase stored values. |
| `use_filing_parser` | `true` | Add `--use-filing-parser` for auto enrichment; automatically skipped when `sources=manual`. |
| `share_data` | `false` | Add `--share-data` to rebuild the full, unscoped buyback/share-sale history. |
| `generate_insights` | `true` | Run the SEC/LLM insights pipeline; disable for a metrics-only refresh. |

For an offline manual-metrics update, select `sources=manual` and
`generate_insights=false`. Existing insights and auto financial metrics are
preserved, unless the manual input explicitly supplies those financial metrics
and `overwrite=true`. Publishing and redeployment still run.

Scheduled refreshes use both financial sources, gap filling without overwrite,
the filing parser enabled, share history unchanged, and insights enabled. The
filing parser is also enabled by default on the manual Run workflow form. The financial `overwrite` input does not overwrite existing
insights.

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

To refresh share repurchase/share sale history in `buybacks.json` during a local
refresh, pass `--share-data` to the build command:

```powershell
python -m scripts.build_data --years 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026 --share-data
```

Set `SEC_USER_AGENT` and `OPENAI_API_KEY` in `core/.env` first. For a network
free sample dataset, run `python -m scripts.make_sample_data` instead.
