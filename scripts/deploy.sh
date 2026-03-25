#!/bin/bash
# Manual deployment script — run from the Mac mini or any machine with SSH access.
# Usage: ./scripts/deploy.sh [--skip-tests] [--no-build]
#
# Prerequisites:
#   - SSH key at ~/dev/terraform/procurement-intel-key.pem (or set DEPLOY_KEY env var)
#   - EC2 host reachable (set EC2_HOST env var to override default)

set -euo pipefail

# ── Configuration ──────────────────────────────────────────
EC2_HOST="${EC2_HOST:-16.54.103.248}"
EC2_USER="${EC2_USER:-ec2-user}"
DEPLOY_KEY="${DEPLOY_KEY:-$HOME/dev/terraform/procurement-intel-key.pem}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/procurement-intel}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ── Parse flags ────────────────────────────────────────────
SKIP_TESTS=false
NO_BUILD=false
for arg in "$@"; do
  case "$arg" in
    --skip-tests) SKIP_TESTS=true ;;
    --no-build)   NO_BUILD=true ;;
    --help|-h)
      echo "Usage: $0 [--skip-tests] [--no-build]"
      echo "  --skip-tests  Skip running pytest before deploying"
      echo "  --no-build    Sync files but don't rebuild Docker images"
      exit 0
      ;;
    *) echo "Unknown flag: $arg"; exit 1 ;;
  esac
done

# ── Preflight checks ──────────────────────────────────────
if [ ! -f "$DEPLOY_KEY" ]; then
  echo "ERROR: SSH key not found at $DEPLOY_KEY"
  echo "Set DEPLOY_KEY env var to the correct path."
  exit 1
fi

SSH_CMD="ssh -i $DEPLOY_KEY -o StrictHostKeyChecking=no -o ConnectTimeout=10 $EC2_USER@$EC2_HOST"

echo "🚀 Deploying to $EC2_HOST..."
echo "   Source: $REPO_ROOT"
echo "   Target: $DEPLOY_PATH"

# ── Run tests locally ─────────────────────────────────────
if [ "$SKIP_TESTS" = false ]; then
  echo ""
  echo "🧪 Running tests..."
  cd "$REPO_ROOT"
  if command -v pytest &>/dev/null; then
    pytest scraper/tests/ api/tests/ -v --tb=short -x || {
      echo "❌ Tests failed. Deploy aborted."
      echo "   Use --skip-tests to deploy anyway."
      exit 1
    }
    echo "✅ Tests passed"
  else
    echo "⚠️  pytest not found locally — skipping tests"
  fi
fi

# ── Sync code ─────────────────────────────────────────────
echo ""
echo "📦 Syncing code to EC2..."
rsync -azP --delete \
  -e "ssh -i $DEPLOY_KEY -o StrictHostKeyChecking=no" \
  --exclude '.git' \
  --exclude '.github' \
  --exclude 'terraform' \
  --exclude '.planning' \
  --exclude '.env' \
  --exclude 'node_modules' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude '.next' \
  --exclude 'web/.next' \
  --exclude 'web/node_modules' \
  --exclude 'postgres_data' \
  "$REPO_ROOT/" "$EC2_USER@$EC2_HOST:$DEPLOY_PATH/"

echo "✅ Code synced"

# ── Build and restart ─────────────────────────────────────
if [ "$NO_BUILD" = false ]; then
  echo ""
  echo "🔨 Building and restarting containers..."
  $SSH_CMD << 'REMOTE_SCRIPT'
  set -euo pipefail
  cd /opt/procurement-intel
  COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

  # Build
  $COMPOSE build --no-cache

  # Rolling restart
  $COMPOSE up -d --no-deps api
  $COMPOSE up -d --no-deps web
  $COMPOSE up -d --no-deps scraper
  $COMPOSE up -d --no-deps nginx

  sleep 5
  $COMPOSE ps
  docker image prune -f
REMOTE_SCRIPT

  echo "✅ Containers rebuilt and restarted"
fi

echo ""
echo "🎉 Deployment complete!"
echo "   https://procurement.eliastools.com"
