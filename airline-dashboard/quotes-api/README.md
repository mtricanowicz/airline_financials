# quotes-api

A minimal FastAPI microservice that returns the most recent daily closing price
for the airline tickers. It is the only piece of the dashboard that needs live
network access at request time. All financial statement data is precomputed into
static JSON by the core pipeline and served by the front ends directly.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Liveness probe, returns `{"status": "ok"}`. |
| GET | `/quotes?tickers=AAL,DAL,UAL,LUV` | Last close, day change, and change percent per ticker. |

Quotes are cached in-memory for the current trading day, so the upstream provider
is queried at most once per ticker per day.

## Local development

```powershell
cd quotes-api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
```

Then visit `http://localhost:8080/quotes` or `http://localhost:8080/docs`.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `PORT` | `8080` | Port the server binds to (set by Cloud Run). |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins. Set to the deployed front-end origin in production. |

## Container

```powershell
docker build -t quotes-api .
docker run -p 8080:8080 -e ALLOWED_ORIGINS=https://your-app.web.app quotes-api
```

The image runs as a non-root user and listens on `$PORT`, ready for Cloud Run.
