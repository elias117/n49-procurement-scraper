# Deployment Guide

## CI/CD Pipeline (GitHub Actions)

The pipeline runs automatically on every push to `main`:

1. **Test** — Runs scraper and API tests against a PostgreSQL service container
2. **Deploy** — Syncs code to EC2 via rsync, rebuilds Docker images, rolling restarts services

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `EC2_SSH_KEY` | Contents of `procurement-intel-key.pem` (full RSA private key) |
| `EC2_HOST` | EC2 Elastic IP address (currently `16.54.103.248`) |

### Optional GitHub Secrets

| Secret | Default | Description |
|--------|---------|-------------|
| `EC2_USER` | `ec2-user` | SSH username on EC2 |
| `DEPLOY_PATH` | `/opt/procurement-intel` | Remote directory for the application |

### Setting Up Secrets

```bash
# From a machine with the PEM key:
gh secret set EC2_SSH_KEY < ~/dev/terraform/procurement-intel-key.pem
gh secret set EC2_HOST -b "16.54.103.248"
```

### Manual Trigger

You can also trigger a deploy manually from the GitHub Actions tab or via CLI:

```bash
gh workflow run deploy.yml
```

## Manual Deployment

If you need to deploy without pushing to main:

```bash
./scripts/deploy.sh              # Full deploy (test + sync + build)
./scripts/deploy.sh --skip-tests # Skip local tests
./scripts/deploy.sh --no-build   # Sync files only, don't rebuild containers
```

The script uses SSH key at `~/dev/terraform/procurement-intel-key.pem` by default.
Override with `DEPLOY_KEY=/path/to/key.pem ./scripts/deploy.sh`.

## Architecture

```
GitHub (push to main)
  └─ GitHub Actions
       ├─ Test (pytest in CI)
       └─ Deploy
            ├─ rsync code → EC2:/opt/procurement-intel/
            └─ SSH → docker compose build + rolling restart
                 ├─ api (FastAPI)
                 ├─ web (Next.js)
                 ├─ scraper (Playwright + Xvfb)
                 └─ nginx (reverse proxy + TLS)
```

## EC2 Services

| Service | Port | Description |
|---------|------|-------------|
| db | 5432 (internal) | PostgreSQL 17 + pgvector |
| api | 8000 (internal) | FastAPI backend |
| web | 3000 (internal) | Next.js frontend |
| scraper | — | Playwright scraper (cron-triggered) |
| nginx | 80, 443 | Reverse proxy with Let's Encrypt TLS |

## Rollback

If a deployment breaks something:

```bash
# SSH into EC2
ssh -i ~/dev/terraform/procurement-intel-key.pem ec2-user@16.54.103.248

# Check logs
cd /opt/procurement-intel
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=50 api
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=50 web

# Revert to previous git commit locally, then redeploy
git revert HEAD
git push origin main  # triggers automatic redeploy
```
