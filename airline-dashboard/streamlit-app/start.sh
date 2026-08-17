#!/bin/sh
set -eu

streamlit run /app/streamlit-app/app.py --server.port 8501 --server.address 127.0.0.1 &

exec nginx -g "daemon off;"
