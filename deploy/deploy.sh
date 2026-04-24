#!/usr/bin/env bash
# Maango MCP — Hetzner deploy script
#
# Prerequisites on the target server:
#   - Docker 20.10+      (docker --version)
#   - nginx              (nginx -v)
#   - certbot            (certbot --version)
#
# Usage (from the server, as root):
#   export MAANGO_API_KEY=maango_sk_xxxxxxxx
#   export MCP_DOMAIN=mcp.maango.io              # optional, defaults to this
#   export MCP_HOST_PORT=8000                    # optional, defaults to this
#   curl -fsSL https://raw.githubusercontent.com/21nkant/maango-mcp/main/deploy/deploy.sh | bash
#
# Or clone first, review, then run:
#   cd /srv && git clone https://github.com/21nkant/maango-mcp.git
#   cd maango-mcp/deploy && MAANGO_API_KEY=... ./deploy.sh
#
# The script is idempotent — safe to re-run for updates.

set -euo pipefail

# ----- Config ----------------------------------------------------------------

REPO_URL="${REPO_URL:-https://github.com/21nkant/maango-mcp.git}"
INSTALL_DIR="${INSTALL_DIR:-/srv/maango-mcp}"
MCP_DOMAIN="${MCP_DOMAIN:-mcp.maango.io}"
MCP_HOST_PORT="${MCP_HOST_PORT:-8000}"
CONTAINER_NAME="${CONTAINER_NAME:-maango-mcp}"
IMAGE_TAG="${IMAGE_TAG:-maango-mcp:latest}"
NGINX_SITE="/etc/nginx/sites-available/${MCP_DOMAIN}"
NGINX_SITE_ENABLED="/etc/nginx/sites-enabled/${MCP_DOMAIN}"

if [ -z "${MAANGO_API_KEY:-}" ]; then
    echo "ERROR: MAANGO_API_KEY env var must be set." >&2
    echo "       export MAANGO_API_KEY=maango_sk_xxxxxxxx" >&2
    exit 1
fi

# ----- Preflight -------------------------------------------------------------

echo "▶ Preflight checks"
for cmd in docker nginx certbot git; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: '$cmd' is not installed on this server." >&2
        exit 1
    fi
done
echo "  ✓ docker, nginx, certbot, git all installed"

# ----- Clone or pull ---------------------------------------------------------

echo "▶ Fetching repo"
if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR"
    git fetch origin
    git reset --hard origin/main
    echo "  ✓ Pulled latest from main at $INSTALL_DIR"
else
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    echo "  ✓ Cloned to $INSTALL_DIR"
fi

# ----- Build Docker image ----------------------------------------------------

echo "▶ Building Docker image"
docker build --pull -t "$IMAGE_TAG" . >/dev/null
echo "  ✓ $IMAGE_TAG built"

# ----- Stop old container, run new one ---------------------------------------

echo "▶ Restarting container"
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    -p "127.0.0.1:${MCP_HOST_PORT}:8000" \
    -e MAANGO_API_KEY="$MAANGO_API_KEY" \
    -e MAANGO_MCP_TRANSPORT=sse \
    -e MAANGO_API_BASE_URL="${MAANGO_API_BASE_URL:-https://api.maango.io}" \
    "$IMAGE_TAG" >/dev/null

# Wait for server to be ready
sleep 3
if ! curl -sf -o /dev/null -H "Accept: text/event-stream" --max-time 3 \
    "http://127.0.0.1:${MCP_HOST_PORT}/sse"; then
    echo "WARN: container started but /sse endpoint not responding yet"
    echo "      check: docker logs $CONTAINER_NAME"
fi
echo "  ✓ Container running on 127.0.0.1:${MCP_HOST_PORT}"

# ----- Write nginx config ----------------------------------------------------

echo "▶ Writing nginx config"
cat > "$NGINX_SITE" <<NGINX
# Maango MCP — managed by deploy.sh, do not edit by hand.
# Regenerate: run deploy.sh again from /srv/maango-mcp/deploy/.

server {
    listen 80;
    listen [::]:80;
    server_name ${MCP_DOMAIN};

    # ACME HTTP-01 challenge (keep this above the rest for certbot).
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # After certbot runs, this block will redirect to HTTPS.
    # Before that, it proxies so you can test over HTTP.
    location / {
        proxy_pass http://127.0.0.1:${MCP_HOST_PORT};
        proxy_http_version 1.1;

        # SSE essentials
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        chunked_transfer_encoding off;

        # Standard forwarding headers
        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # Long idle timeout — SSE connections stay open
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
NGINX

ln -sf "$NGINX_SITE" "$NGINX_SITE_ENABLED"
nginx -t
systemctl reload nginx
echo "  ✓ nginx configured for ${MCP_DOMAIN}"

# ----- Done ------------------------------------------------------------------

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  DEPLOY COMPLETE"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Next steps (in order):"
echo ""
echo "  1. DNS (in Porkbun): add A record"
echo "       Host:   mcp"
echo "       Type:   A"
echo "       Answer: \$(this server's public IP)"
echo ""
echo "  2. Wait for DNS to propagate (~1-5 min). Verify:"
echo "       dig ${MCP_DOMAIN} +short"
echo ""
echo "  3. Get SSL cert from Let's Encrypt:"
echo "       certbot --nginx -d ${MCP_DOMAIN}"
echo ""
echo "  4. Verify from outside:"
echo "       curl https://${MCP_DOMAIN}/sse -H 'Accept: text/event-stream' --max-time 2"
echo "       (should stream: event: endpoint / data: /messages/?session_id=...)"
echo ""
echo "Updating later:"
echo "       cd ${INSTALL_DIR}/deploy && MAANGO_API_KEY=\$KEY ./deploy.sh"
echo ""
echo "Logs:      docker logs -f ${CONTAINER_NAME}"
echo "Restart:   docker restart ${CONTAINER_NAME}"
echo "Status:    docker ps -f name=${CONTAINER_NAME}"
