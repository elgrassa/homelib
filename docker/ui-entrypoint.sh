#!/bin/sh
# UI container: Streamlit on 8501 + clean /read HTML on 8502.
set -eu
python -m apps.ui.read_server &
exec streamlit run apps/ui/app.py \
  --server.port=8501 \
  --server.address=0.0.0.0 \
  --server.headless=true
