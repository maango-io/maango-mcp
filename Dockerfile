# Maango MCP Server — production container (multi-stage)
#
# Build:  docker build -t maango-mcp .
# Run:    docker run -p 8000:8000 \
#           --env-file /etc/maango-mcp.env \
#           maango-mcp
#
# Multi-stage: the builder image installs uv + project deps into a self-
# contained venv at /opt/venv, the runtime image only copies that venv +
# adds curl for the HEALTHCHECK. Cuts ~150MB off the runtime image.

# ----- Builder stage ----------------------------------------------------------

FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN pip install --no-cache-dir uv

WORKDIR /build

# Copy lock + project metadata first so the install layer caches when source changes.
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src

# Install into a self-contained venv that the runtime stage will copy whole.
RUN uv venv /opt/venv \
 && uv pip install --no-cache --python /opt/venv/bin/python .

# ----- Runtime stage ----------------------------------------------------------

FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# curl is used by the HEALTHCHECK below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user.
RUN useradd --create-home --shell /bin/bash maango

# Pull the prepared venv across.
COPY --from=builder /opt/venv /opt/venv

USER maango

# Hosted mode defaults — override at runtime via --env-file or -e.
ENV MAANGO_MCP_TRANSPORT=sse \
    MAANGO_MCP_HOST=0.0.0.0 \
    MAANGO_MCP_PORT=8000 \
    MAANGO_API_BASE_URL=https://api.maango.io

EXPOSE 8000

# Liveness check — hits the unauthenticated /health endpoint on the bound port.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${MAANGO_MCP_PORT}/health" || exit 1

CMD ["maango-mcp"]
