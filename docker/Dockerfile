FROM python:3.11-slim

WORKDIR /app

# curl is kept for the Render/docker-compose health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install PyTorch CPU-only wheel FIRST (~200 MB) before the rest of requirements.
# Without this, pip resolves torch from PyPI and downloads the CUDA variant (~2 GB),
# which causes 2+ hour builds and OOM on Render Starter (512 MB RAM).
RUN pip install --no-cache-dir \
    torch==2.3.1+cpu \
    --extra-index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data/chroma data/audit_logs

# PORT is injected by Render at runtime (defaults to 8501 for local use).
# Shell form is required so ${PORT:-8501} is expanded by the shell.
EXPOSE 8501
CMD streamlit run app/streamlit_app.py \
    --server.port=${PORT:-8501} \
    --server.address=0.0.0.0 \
    --server.headless=true
