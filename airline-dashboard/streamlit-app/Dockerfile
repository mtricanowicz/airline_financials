# Build from the airline-dashboard root so both the app and the generated data
# are inside the build context:
#   docker build -f streamlit-app/Dockerfile -t airline-streamlit .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    DASHBOARD_DATA_DIR=/app/data/generated

WORKDIR /app

COPY streamlit-app/requirements.txt ./requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir pillow

COPY streamlit-app/ ./streamlit-app/
COPY assets/ ./assets/
COPY data/generated/ ./data/generated/

RUN python - <<'PY'
from pathlib import Path
from PIL import Image

src = Path('/app/assets/branding/site_favicon.png')
dst = Path('/app/assets/branding/site_favicon.ico')
img = Image.open(src).convert('RGBA')
img.save(dst, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (180, 180)])
PY

COPY streamlit-app/nginx.conf /etc/nginx/nginx.conf
COPY streamlit-app/start.sh /app/streamlit-app/start.sh
RUN chmod +x /app/streamlit-app/start.sh

RUN useradd --create-home appuser
USER appuser

EXPOSE 8080
CMD ["/app/streamlit-app/start.sh"]
