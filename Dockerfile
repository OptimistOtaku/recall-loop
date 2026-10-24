FROM node:22-slim AS frontend
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RECALL_DATA_DIR=/tmp/recall-data RECALL_MODEL_CACHE=/app/models RECALL_DEMO=1
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml requirements.lock ./
COPY recall_loop ./recall_loop
RUN pip install --no-cache-dir --require-hashes -r requirements.lock && pip install --no-cache-dir --no-deps .
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5',cache_dir='/app/models',threads=2)"
ENV HF_HUB_OFFLINE=1
COPY --from=frontend /ui/dist ./frontend/dist
EXPOSE 7331
CMD ["python","-c","import os,uvicorn;from recall_loop.api import app_factory;uvicorn.run(app_factory(),host='0.0.0.0',port=int(os.environ.get('PORT','7331')))"]
