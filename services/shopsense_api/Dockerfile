# ShopSense API (M8 packaging). Build from the repository root:
#   docker build -f services/shopsense_api/Dockerfile -t shopsense-api .
# Not built on the development machine (Docker was not available); the image is the deployment unit.
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
RUN pip install --no-cache-dir "uv>=0.5"
WORKDIR /app
COPY . .
RUN uv sync --package shopsense-api --frozen --no-dev
# Bake the reranker model into the image so the container never downloads it at start-up
ENV FASTEMBED_CACHE_PATH=/app/.fastembed_cache
RUN /app/.venv/bin/python -c "from fastembed.rerank.cross_encoder import TextCrossEncoder; TextCrossEncoder('Xenova/ms-marco-MiniLM-L-6-v2')"
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "shopsense_api.entrypoints.api:app", "--host", "0.0.0.0", "--port", "8000"]
