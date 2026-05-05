# Maango MCP Server — production container
#
# Build:  docker build -t maango-mcp .
# Run:    docker run -p 8000:8000 \
#           -e MAANGO_API_KEY=maango_sk_xxx \
#           -e MAANGO_MCP_TRANSPORT=sse \
#           maango-mcp

FROM python:3.12-slim

WORKDIR /app

# curl is used by the HEALTHCHECK below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager) once, then use it for the install.
RUN pip install --no-cache-dir uv

# Copy project files and install dependencies.
COPY pyproject.toml ./
COPY src ./src
RUN uv pip install --system --no-cache .

# Non-root user.
RUN useradd --create-home --shell /bin/bash maango
USER maango

# Hosted mode defaults — override at runtime.
ENV MAANGO_MCP_TRANSPORT=sse \
    MAANGO_MCP_HOST=0.0.0.0 \
    MAANGO_MCP_PORT=8000 \
    MAANGO_API_BASE_URL=https://api.maango.io

EXPOSE 8000

# Liveness check — hits the unauthenticated /health endpoint on the bound port.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${MAANGO_MCP_PORT}/health" || exit 1

CMD ["maango-mcp"]
