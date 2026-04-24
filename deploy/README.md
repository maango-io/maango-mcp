# Deploying Maango MCP on Hetzner

One-command deploy to a Hetzner (or any Ubuntu/Debian) server that already
runs nginx + certbot + Docker. Idempotent — safe to re-run for updates.

## Prerequisites

The target server must have:

- `docker` 20.10+
- `nginx`
- `certbot` (with `python3-certbot-nginx`)
- `git`
- Ports 80 and 443 open publicly

Check with: `docker --version && nginx -v && certbot --version && git --version`

If you're adding this to the box that already runs `api.maango.io`, all four
are already there.

## One-shot deploy

SSH into the server, then:

```bash
export MAANGO_API_KEY=maango_sk_xxxxxxxx
curl -fsSL https://raw.githubusercontent.com/21nkant/maango-mcp/main/deploy/deploy.sh | sudo -E bash
```

Or the safer path — clone first, inspect, run:

```bash
cd /srv
sudo git clone https://github.com/21nkant/maango-mcp.git
cd maango-mcp/deploy
sudo MAANGO_API_KEY=maango_sk_xxxxxxxx ./deploy.sh
```

The script will:

1. Pull the latest code
2. Build the Docker image
3. Stop any previous container, start a fresh one bound to `127.0.0.1:8000`
4. Write the nginx config at `/etc/nginx/sites-available/mcp.maango.io`
5. Enable the site, test config, reload nginx

Takes 2–5 minutes. Output tells you what to do next.

## After the script runs

### 1. DNS (Porkbun → maango.io → DNS)

Add:

| Type | Host | Answer | TTL |
|------|------|--------|-----|
| `A`  | `mcp` | `<server's public IPv4>` | 600 |

Wait for propagation (`dig mcp.maango.io +short` returns your IP).

### 2. SSL

```bash
sudo certbot --nginx -d mcp.maango.io
```

Certbot proves ownership via the HTTP-01 challenge (the script already put
the right nginx block in place), installs the cert, patches nginx to redirect
HTTP → HTTPS, reloads.

### 3. Verify from outside

From your laptop (not the server):

```bash
curl https://mcp.maango.io/sse -H "Accept: text/event-stream" --max-time 2
```

Expected output:

```
event: endpoint
data: /messages/?session_id=<random-hex>
```

If you see that, the server is live.

### 4. Test from Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "maango": {
      "url": "https://mcp.maango.io/sse"
    }
  }
}
```

Restart Claude Desktop. Ask Claude *"Check if I can scrape nytimes.com for training."*

## Configurable env vars for deploy.sh

| Var | Default | Purpose |
|-----|---------|---------|
| `MAANGO_API_KEY` | — | **Required.** Service-level API key for calling api.maango.io |
| `MCP_DOMAIN` | `mcp.maango.io` | Hostname used in the nginx server_name |
| `MCP_HOST_PORT` | `8000` | Host port the container binds to (nginx upstream) |
| `CONTAINER_NAME` | `maango-mcp` | Docker container name |
| `IMAGE_TAG` | `maango-mcp:latest` | Docker image tag |
| `INSTALL_DIR` | `/srv/maango-mcp` | Where the repo is cloned |
| `REPO_URL` | `https://github.com/21nkant/maango-mcp.git` | Source repo |
| `MAANGO_API_BASE_URL` | `https://api.maango.io` | Upstream REST API |

## Operational commands

```bash
# Follow logs
docker logs -f maango-mcp

# Restart container (picks up new env vars)
docker restart maango-mcp

# Stop + remove (keeps the image)
docker rm -f maango-mcp

# Status
docker ps -f name=maango-mcp

# Update to latest main
cd /srv/maango-mcp/deploy && sudo MAANGO_API_KEY=$KEY ./deploy.sh
```

## Rollback

```bash
cd /srv/maango-mcp
sudo git log --oneline -10                # find the commit to roll back to
sudo git reset --hard <commit-sha>
cd deploy && sudo MAANGO_API_KEY=$KEY ./deploy.sh
```

## Uninstall

```bash
docker rm -f maango-mcp
docker rmi maango-mcp:latest
sudo rm /etc/nginx/sites-enabled/mcp.maango.io
sudo rm /etc/nginx/sites-available/mcp.maango.io
sudo nginx -t && sudo systemctl reload nginx
sudo rm -rf /srv/maango-mcp
```
