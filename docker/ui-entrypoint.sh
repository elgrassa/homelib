#!/bin/sh
# UI container: Streamlit on 8501 + clean /read HTML on 8502.
set -eu

# READ_PORT has two different meanings in this container: the compose env
# passes through the *host-facing* port (for apps/ui to render into
# /read/{book_id} link text), but the read server's own bind must always stay
# the fixed container-internal 8502 that the compose port mapping and the
# healthcheck both target — otherwise a non-default READ_PORT would move the
# server off the port the container promises to serve. Pin it explicitly here
# rather than inheriting the host-facing value from the environment.
READ_PORT=8502 python -m apps.ui.read_server &
READ_SERVER_PID=$!
sleep 1
kill -0 "$READ_SERVER_PID" 2>/dev/null || { echo "read_server failed to start" >&2; exit 1; }

exec streamlit run apps/ui/app.py \
  --server.port=8501 \
  --server.address=0.0.0.0 \
  --server.headless=true
