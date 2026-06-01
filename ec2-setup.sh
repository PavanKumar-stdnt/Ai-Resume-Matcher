#!/bin/bash
# ec2-setup.sh — One-time EC2 instance bootstrap script
#
# Run this on a fresh Ubuntu 22.04 EC2 instance:
#   chmod +x ec2-setup.sh && sudo ./ec2-setup.sh
#
# Recommended instance type: t3.medium (2 vCPU, 4GB RAM) minimum
#                            t3.large  (2 vCPU, 8GB RAM) recommended

set -e

echo "=== AI Resume Matcher — EC2 Bootstrap ==="
echo "Starting at $(date)"

# ── System updates ─────────────────────────────────────────────────────────────
apt-get update && apt-get upgrade -y
apt-get install -y curl git unzip htop nginx certbot python3-certbot-nginx

# ── Install Docker ─────────────────────────────────────────────────────────────
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker
usermod -aG docker ubuntu

# ── Install Docker Compose v2 ──────────────────────────────────────────────────
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-linux-x86_64" \
     -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
docker compose version

# ── Create app directory ───────────────────────────────────────────────────────
mkdir -p /opt/ai-resume-matcher
chown ubuntu:ubuntu /opt/ai-resume-matcher

# ── Create systemd service for auto-restart ────────────────────────────────────
cat > /etc/systemd/system/resume-matcher.service << 'SERVICE'
[Unit]
Description=AI Resume Matcher Docker Compose
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/ai-resume-matcher
ExecStart=/usr/local/lib/docker/cli-plugins/docker-compose up -d --remove-orphans
ExecStop=/usr/local/lib/docker/cli-plugins/docker-compose down
TimeoutStartSec=300
User=ubuntu

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable resume-matcher.service

# ── Configure UFW firewall ─────────────────────────────────────────────────────
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8000/tcp    # Direct API access (disable after nginx is set up)
ufw allow 5000/tcp    # MLflow UI (restrict to your IP in production)
ufw --force enable

# ── Create log rotation ────────────────────────────────────────────────────────
cat > /etc/logrotate.d/resume-matcher << 'LOGROTATE'
/opt/ai-resume-matcher/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
LOGROTATE

echo ""
echo "=== EC2 Bootstrap Complete ==="
echo ""
echo "Next steps:"
echo "  1. cd /opt/ai-resume-matcher"
echo "  2. git clone https://github.com/YOUR_USERNAME/ai-resume-matcher.git ."
echo "  3. cp .env.example .env && nano .env  (fill in your secrets)"
echo "  4. docker compose up -d"
echo "  5. curl http://localhost:8000/api/v1/health"
echo ""
echo "For SSL (HTTPS):"
echo "  certbot --nginx -d api.yourdomain.com"
