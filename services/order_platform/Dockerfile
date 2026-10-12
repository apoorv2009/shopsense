# Order Platform (mock order system). Build from the repository root:
#   docker build -f services/order_platform/Dockerfile -t order-platform .
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
RUN pip install --no-cache-dir "uv>=0.5"
WORKDIR /app
COPY . .
RUN uv sync --package order-platform --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8001
CMD ["uvicorn", "order_platform.entrypoints.api:app", "--host", "0.0.0.0", "--port", "8001"]
