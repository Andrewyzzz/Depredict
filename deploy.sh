#!/usr/bin/env bash
set -euo pipefail

# ── DePredict Deployment Script ──
# Run this on a fresh Ubuntu 22.04+ VPS

echo "=== DePredict Deployment ==="

# 1. Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    echo "Docker installed. Please log out and back in, then re-run this script."
    exit 0
fi

# 2. Install Docker Compose plugin if not present
if ! docker compose version &> /dev/null; then
    echo "Installing Docker Compose plugin..."
    sudo apt-get update && sudo apt-get install -y docker-compose-plugin
fi

# 3. Check .env file
if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and fill in your keys:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    exit 1
fi

# 4. Check DOMAIN is set
if ! grep -q "^DOMAIN=" .env || grep -q "DOMAIN=your-domain.com" .env; then
    echo "ERROR: Set your DOMAIN in .env (e.g. DOMAIN=depredict.example.com)"
    exit 1
fi

# 5. Export DOMAIN for Caddy
export $(grep ^DOMAIN .env)

# 6. Build and start
echo "Building containers..."
docker compose build

echo "Starting services..."
docker compose up -d

echo ""
echo "=== Deployment complete ==="
echo "Site: https://$DOMAIN"
echo ""
echo "Useful commands:"
echo "  docker compose logs -f        # View logs"
echo "  docker compose restart        # Restart all services"
echo "  docker compose down           # Stop all services"
echo "  docker compose up -d --build  # Rebuild and restart"
