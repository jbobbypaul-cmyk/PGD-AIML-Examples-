FROM python:3.11-slim

WORKDIR /app

# curl is kept for the Render/docker-compose health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
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
