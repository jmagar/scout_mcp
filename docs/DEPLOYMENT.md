# Scout MCP Deployment Guide

**Latest Update:** December 7, 2025
**Version:** 0.2.0 (In Development)
**Status:** Production-Ready (with prerequisites)

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture Overview](#architecture-overview)
3. [Prerequisites](#prerequisites)
4. [Local Development](#local-development)
5. [Production Deployment](#production-deployment)
6. [Configuration](#configuration)
7. [Monitoring & Health](#monitoring--health)
8. [Troubleshooting](#troubleshooting)
9. [Scaling](#scaling)
10. [Disaster Recovery](#disaster-recovery)

---

## Quick Start

### Local Development (5 minutes)

```bash
# 1. Clone and setup
git clone https://github.com/jmagar/scout_mcp.git
cd scout_mcp
uv sync

# 2. Configure (optional)
cp .env.example .env
# Edit .env to set SCOUT_API_KEYS

# 3. Run tests
uv run pytest tests/ -v

# 4. Start server
uv run python -m scout_mcp
# Server runs on http://localhost:8000
# Health check: curl http://localhost:8000/health
```

### Docker Deployment (10 minutes)

```bash
# 1. Build image
docker build -t scout_mcp:latest .

# 2. Run container
docker run -d \
  --name scout-mcp \
  -e SCOUT_API_KEYS="your-secret-key" \
  -e SCOUT_HTTP_HOST="0.0.0.0" \
  -e SCOUT_HTTP_PORT="8000" \
  -p 53000:8000 \
  -v ~/.ssh/config:/home/scout/.ssh/config:ro \
  -v ~/.ssh/known_hosts:/home/scout/.ssh/known_hosts:ro \
  scout_mcp:latest

# 3. Verify
curl http://localhost:53000/health
# Response: OK
```

### Docker Compose Deployment (5 minutes)

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env - at minimum set SCOUT_API_KEYS

# 2. Deploy
docker-compose up -d scout

# 3. Verify
curl http://localhost:53000/health
docker logs -f scout-mcp

# 4. Stop
docker-compose down scout
```

---

## Architecture Overview

### Components

```
┌─────────────────────────────────────────────────────┐
│          MCP Client                                 │
│  (Claude Desktop, IDE, etc.)                        │
└────────────────────┬────────────────────────────────┘
                     │
                     │ HTTP/SSE or STDIO
                     │
┌────────────────────▼────────────────────────────────┐
│     Scout MCP Server (8.0)                          │
│  ┌──────────────────────────────────────────────┐  │
│  │ Middleware Stack                             │  │
│  │ - API Key Authentication                     │  │
│  │ - Rate Limiting (per-IP token bucket)        │  │
│  │ - Error Handling                             │  │
│  │ - Logging & Timing                           │  │
│  └──────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────┐  │
│  │ Tools & Resources                            │  │
│  │ - scout() tool for file/command operations   │  │
│  │ - scout://host/path resources                │  │
│  │ - hosts://list resource                      │  │
│  │ - Docker, Docker Compose, ZFS resources      │  │
│  └──────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────┐  │
│  │ Services                                     │  │
│  │ - SSH Connection Pool (LRU, 100 max)         │  │
│  │ - Configuration (SSH config parsing)         │  │
│  │ - Executors (file, command, stat ops)       │  │
│  └──────────────────────────────────────────────┘  │
└────────────────┬──────────────────────────────────┘
                 │
                 │ SSH (Key-based auth)
                 │
┌────────────────▼──────────────────────────────────┐
│     Remote SSH Hosts                               │
│  - File system access                              │
│  - Command execution                               │
│  - System information (Docker, ZFS, etc.)         │
└────────────────────────────────────────────────────┘
```

### Data Flow

**File Read Request:**
1. MCP Client sends `scout://tootie:/var/log/app.log`
2. Server validates path (blocks traversal attacks)
3. Authentication middleware checks API key
4. Rate limiting checks per-IP quota
5. Connection pool gets or creates SSH connection
6. File is read with size limits enforced
7. Response returned to client

**Command Execution:**
1. MCP Client sends command to execute on host
2. Path validation blocks injection attempts
3. Authentication and rate limiting applied
4. SSH connection established/reused
5. Command executed with timeout
6. Output size checked before returning
7. Results streamed to client

---

## Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 0.5 cores | 1.0-2.0 cores |
| Memory | 256MB | 512MB-1GB |
| Storage | 200MB | 1GB |
| Python | 3.11 | 3.11+ |

### Required Files

```
~/.ssh/config          # SSH host configurations (required)
~/.ssh/known_hosts     # SSH host key database (required)
~/.ssh/id_rsa          # SSH private key (required)
~/.ssh/id_rsa.pub      # SSH public key (optional)
```

### SSH Setup

```bash
# 1. Ensure SSH keys exist
ls -la ~/.ssh/
# Expected: id_rsa, id_rsa.pub, config, known_hosts

# 2. Configure SSH hosts (~/.ssh/config)
Host tootie
    HostName 192.168.1.100
    User admin
    IdentityFile ~/.ssh/id_rsa
    Port 22

Host squirts
    HostName 192.168.1.101
    User root
    IdentityFile ~/.ssh/id_rsa

# 3. Populate known_hosts
ssh-keyscan tootie >> ~/.ssh/known_hosts
ssh-keyscan squirts >> ~/.ssh/known_hosts

# 4. Test SSH access
ssh tootie "whoami"
ssh squirts "whoami"
```

### Docker Installation (if using Docker)

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify
docker --version
docker compose --version
```

---

## Local Development

### Setup Development Environment

```bash
# 1. Clone repository
git clone https://github.com/jmagar/scout_mcp.git
cd scout_mcp

# 2. Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# 3. Sync dependencies
uv sync

# 4. Setup pre-commit hooks (optional)
uv run pre-commit install
```

### Running Tests

```bash
# All tests
uv run pytest tests/ -v

# Specific test file
uv run pytest tests/test_security.py -v

# With coverage
uv run pytest tests/ --cov=scout_mcp --cov-report=html

# Open coverage report
open htmlcov/index.html
```

### Running Linting & Type Checking

```bash
# Lint
uv run ruff check scout_mcp/ tests/

# Format
uv run ruff format scout_mcp/ tests/

# Type check
uv run mypy scout_mcp/
```

### Running Server Locally

```bash
# Development mode
uv run python -m scout_mcp

# With custom log level
SCOUT_LOG_LEVEL=DEBUG uv run python -m scout_mcp

# With authentication
SCOUT_API_KEYS="test-key-12345" uv run python -m scout_mcp

# On custom port
SCOUT_HTTP_PORT=9000 uv run python -m scout_mcp

# Localhost only
SCOUT_HTTP_HOST=127.0.0.1 uv run python -m scout_mcp
```

### Development Configuration

```bash
# Copy template
cp .env.example .env

# Edit for development
cat > .env << 'EOF'
# Development settings
SCOUT_API_KEYS=dev-key-12345
SCOUT_HTTP_HOST=127.0.0.1
SCOUT_HTTP_PORT=8000
SCOUT_LOG_LEVEL=DEBUG
SCOUT_LOG_PAYLOADS=true
SCOUT_INCLUDE_TRACEBACK=true
EOF
```

---

## Production Deployment

### Pre-Deployment Checklist

- [ ] All tests passing: `uv run pytest tests/ -v`
- [ ] Code coverage >= 85%
- [ ] Linting passing: `uv run ruff check scout_mcp/ tests/`
- [ ] Type checking passing: `uv run mypy scout_mcp/`
- [ ] Docker image built: `docker build -t scout_mcp:v0.2.0 .`
- [ ] Docker image tested locally
- [ ] SSH keys available on deployment host
- [ ] SSH known_hosts populated
- [ ] Firewall rules allow SSH connections
- [ ] Port 53000+ available on deployment host
- [ ] API key generated and secured
- [ ] Environment variables documented
- [ ] Backup/rollback plan documented

### Docker Image Build

```bash
# Build image with version tag
docker build -t scout_mcp:v0.2.0 .

# Tag for registry
docker tag scout_mcp:v0.2.0 ghcr.io/username/scout_mcp:v0.2.0
docker tag scout_mcp:v0.2.0 ghcr.io/username/scout_mcp:latest

# Push to registry
docker push ghcr.io/username/scout_mcp:v0.2.0
docker push ghcr.io/username/scout_mcp:latest
```

### Docker Compose Deployment

#### 1. Prepare Configuration

```bash
# Copy and edit .env
cp .env.example .env

# Set production values
cat > .env << 'EOF'
# Production configuration
ENVIRONMENT=production
VERSION=v0.2.0
SCOUT_HTTP_PORT=53000
SCOUT_API_KEYS=your-generated-random-key-here
SCOUT_RATE_LIMIT_PER_MINUTE=60
SCOUT_STRICT_HOST_KEY_CHECKING=true
SCOUT_LOG_LEVEL=INFO
SCOUT_LOG_PAYLOADS=false
SCOUT_INCLUDE_TRACEBACK=false
SCOUT_MAX_FILE_SIZE=1048576
SCOUT_MAX_OUTPUT_SIZE=10485760
SCOUT_COMMAND_TIMEOUT=30
SCOUT_SSH_CONNECT_TIMEOUT=30
SCOUT_IDLE_TIMEOUT=60
SCOUT_MAX_POOL_SIZE=100
SCOUT_CPU_LIMIT=1.0
SCOUT_MEMORY_LIMIT=512M
SCOUT_CPU_RESERVE=0.5
SCOUT_MEMORY_RESERVE=256M
EOF

# Secure the .env file
chmod 600 .env

# Verify configuration
cat .env
```

#### 2. Pull/Build Image

```bash
# Option A: Pull from registry
docker pull ghcr.io/username/scout_mcp:v0.2.0

# Option B: Build locally
docker build -t scout_mcp:v0.2.0 .

# Update docker-compose.yaml image reference
# image: scout_mcp:v0.2.0
```

#### 3. Deploy

```bash
# Start service
docker-compose up -d scout

# Verify service started
sleep 5
docker-compose ps
# Status: Up

# Check logs
docker logs -f scout-mcp

# Health check
curl http://localhost:53000/health
# Response: OK
```

#### 4. Verify Deployment

```bash
# Container running
docker ps | grep scout-mcp

# Container stats
docker stats scout-mcp

# Logs for errors
docker logs scout-mcp | grep ERROR

# Test API
curl -H "X-API-Key: $(grep SCOUT_API_KEYS .env | cut -d= -f2)" \
  http://localhost:53000/mcp

# Test specific operation
docker exec scout-mcp ssh tootie "whoami"
```

### Troubleshooting Deployment

#### Port Already in Use

```bash
# Check what's using port 53000
ss -tuln | grep 53000
lsof -i :53000

# If occupied, use different port
# Edit docker-compose.yaml: ports: - "53001:8000"
```

#### SSH Connection Failures

```bash
# Check SSH config mounted
docker exec scout-mcp ls -la /home/scout/.ssh/

# Check SSH keys
docker exec scout-mcp ssh -v tootie "echo test"

# Check host key verification
docker exec scout-mcp cat /home/scout/.ssh/known_hosts
```

#### Memory Issues

```bash
# Check memory usage
docker stats scout-mcp

# Reduce pool size if needed
# Edit .env: SCOUT_MAX_POOL_SIZE=50
# docker-compose down scout && docker-compose up -d scout
```

---

## Configuration

### Environment Variables

#### Required (Production)

| Variable | Default | Example | Purpose |
|----------|---------|---------|---------|
| `SCOUT_API_KEYS` | (none) | `abc123def456` | Authentication key(s) |

#### HTTP Configuration

| Variable | Default | Example | Purpose |
|----------|---------|---------|---------|
| `SCOUT_HTTP_HOST` | `0.0.0.0` | `127.0.0.1` | Bind address |
| `SCOUT_HTTP_PORT` | `8000` | `53000` | Listen port |
| `SCOUT_TRANSPORT` | `http` | `http` or `stdio` | Transport type |

#### Security Configuration

| Variable | Default | Example | Purpose |
|----------|---------|---------|---------|
| `SCOUT_RATE_LIMIT_PER_MINUTE` | `60` | `120` | Requests per minute per IP |
| `SCOUT_RATE_LIMIT_BURST` | `10` | `20` | Maximum burst size |
| `SCOUT_STRICT_HOST_KEY_CHECKING` | `true` | `true` or `false` | Verify SSH host keys |
| `SCOUT_KNOWN_HOSTS` | `~/.ssh/known_hosts` | `/etc/ssh/known_hosts` | Known hosts file path |

#### Resource Limits

| Variable | Default | Example | Purpose |
|----------|---------|---------|---------|
| `SCOUT_MAX_FILE_SIZE` | `1048576` (1MB) | `5242880` (5MB) | Max file size |
| `SCOUT_MAX_OUTPUT_SIZE` | `10485760` (10MB) | `52428800` (50MB) | Max output size |
| `SCOUT_COMMAND_TIMEOUT` | `30` | `60` | Command timeout (seconds) |
| `SCOUT_SSH_CONNECT_TIMEOUT` | `30` | `45` | SSH connect timeout |
| `SCOUT_IDLE_TIMEOUT` | `60` | `120` | Connection idle timeout |
| `SCOUT_MAX_POOL_SIZE` | `100` | `200` | Max concurrent connections |

#### Logging Configuration

| Variable | Default | Example | Purpose |
|----------|---------|---------|---------|
| `SCOUT_LOG_LEVEL` | `DEBUG` | `INFO` | Log level: DEBUG/INFO/WARNING/ERROR |
| `SCOUT_LOG_PAYLOADS` | `false` | `true` | Log request/response payloads |
| `SCOUT_INCLUDE_TRACEBACK` | `false` | `true` | Include tracebacks in errors |

### Configuration Examples

#### Development (Localhost, Relaxed Security)

```bash
export SCOUT_HTTP_HOST="127.0.0.1"
export SCOUT_HTTP_PORT="8000"
export SCOUT_LOG_LEVEL="DEBUG"
export SCOUT_STRICT_HOST_KEY_CHECKING="true"
```

#### Production (Secure, Rate Limited)

```bash
export SCOUT_API_KEYS="$(openssl rand -hex 32)"
export SCOUT_HTTP_HOST="0.0.0.0"  # Behind firewall
export SCOUT_HTTP_PORT="8000"     # 53000 via docker-compose
export SCOUT_RATE_LIMIT_PER_MINUTE="60"
export SCOUT_STRICT_HOST_KEY_CHECKING="true"
export SCOUT_LOG_LEVEL="INFO"
export SCOUT_LOG_PAYLOADS="false"
export SCOUT_MAX_FILE_SIZE="5242880"
export SCOUT_MAX_OUTPUT_SIZE="52428800"
```

#### High Volume (Scaled Resources)

```bash
export SCOUT_MAX_POOL_SIZE="200"
export SCOUT_RATE_LIMIT_PER_MINUTE="120"
export SCOUT_COMMAND_TIMEOUT="60"
export SCOUT_MAX_FILE_SIZE="10485760"  # 10MB
export SCOUT_MAX_OUTPUT_SIZE="104857600"  # 100MB
```

---

## Monitoring & Health

### Health Check Endpoint

```bash
# Basic health check (no authentication required)
curl http://localhost:53000/health
# Response: OK (200 status)

# Detailed health status (planned for v0.3.0)
curl -H "X-API-Key: your-key" http://localhost:53000/health/detailed
# Response:
# {
#   "status": "healthy",
#   "version": "0.2.0",
#   "timestamp": "2025-12-07T14:30:00Z",
#   "ssh": {
#     "status": "operational",
#     "hosts_configured": 5,
#     "hosts_online": 4
#   },
#   "pool": {
#     "active_connections": 5,
#     "idle_connections": 2,
#     "capacity": 100
#   }
# }
```

### Connection Pool Monitoring

```bash
# View active connections in logs
docker logs scout-mcp | grep "active"

# Expected output:
# [INFO] Pool initialized: capacity=100, idle_timeout=60s
# [INFO] Created SSH connection to tootie
# [DEBUG] Reusing SSH connection to tootie
# [INFO] Closing 2 idle connections, 3 active connections remain
```

### Metrics Endpoint (Planned v0.2.1)

```bash
# Prometheus metrics (when implemented)
curl http://localhost:53000/metrics

# Example output:
# scout_connections_active{host="tootie"} 5
# scout_connections_idle{host="tootie"} 2
# scout_pool_evictions_total 3
# scout_requests_total{path="/"} 42
# scout_request_duration_seconds{quantile="0.95"} 0.123
```

### Log Monitoring

```bash
# Follow logs in real-time
docker logs -f scout-mcp

# Filter for errors
docker logs scout-mcp | grep ERROR

# Filter for specific host
docker logs scout-mcp | grep "tootie"

# Filter for rate limit events
docker logs scout-mcp | grep "rate"

# Count requests per minute
docker logs scout-mcp | grep "Request" | wc -l
```

### Alerting Setup (Recommended)

Create alerts for:
- Container stopped: `docker ps | grep scout-mcp` returns nothing
- High CPU: > 80% sustained
- High memory: > 90% limit
- Health check failing: `/health` returns non-200
- Error rate: > 5% of requests
- Connection pool full: utilization > 90%

---

## Troubleshooting

### Issue: Container won't start

**Symptoms:**
```
docker-compose up scout
Error: scout-mcp exited with code 1
```

**Solution:**
```bash
# Check logs for reason
docker logs scout-mcp

# Common issues:
# 1. Missing SCOUT_API_KEYS
# 2. Port already in use
# 3. SSH config/keys not mounted

# Verify:
docker-compose config | grep -A 20 scout
docker ps -a | grep scout
```

### Issue: SSH connection failures

**Symptoms:**
```
Error: Cannot connect to host 'tootie': Connection refused
```

**Solution:**
```bash
# 1. Verify SSH keys mounted
docker exec scout-mcp ls -la /home/scout/.ssh/

# 2. Test SSH connection
docker exec scout-mcp ssh -v tootie "echo test"

# 3. Check known_hosts
docker exec scout-mcp cat /home/scout/.ssh/known_hosts

# 4. Add host if missing
docker exec scout-mcp ssh-keyscan tootie >> ~/.ssh/known_hosts
docker-compose down scout
docker-compose up -d scout
```

### Issue: Rate limiting too aggressive

**Symptoms:**
```
Error: Rate limit exceeded
Retry-After: 5
```

**Solution:**
```bash
# 1. Increase limit in .env
sed -i 's/SCOUT_RATE_LIMIT_PER_MINUTE=60/SCOUT_RATE_LIMIT_PER_MINUTE=120/' .env

# 2. Restart service
docker-compose down scout
docker-compose up -d scout

# 3. Verify change
docker exec scout-mcp env | grep RATE_LIMIT
```

### Issue: Memory usage high

**Symptoms:**
```
docker stats scout-mcp
MEM: 480M / 512M
```

**Solution:**
```bash
# 1. Reduce pool size
sed -i 's/SCOUT_MAX_POOL_SIZE=100/SCOUT_MAX_POOL_SIZE=50/' .env

# 2. Reduce file size limit
sed -i 's/SCOUT_MAX_OUTPUT_SIZE=10485760/SCOUT_MAX_OUTPUT_SIZE=5242880/' .env

# 3. Restart
docker-compose down scout
docker-compose up -d scout
```

### Issue: Slow file reads

**Symptoms:**
```
Slow request: GET /mcp (scout://tootie:/var/log/app.log) took 5234ms
```

**Solution:**
```bash
# 1. Check network latency
docker exec scout-mcp ping -c 3 tootie

# 2. Check remote file size
docker exec scout-mcp ssh tootie "du -sh /var/log/app.log"

# 3. If file > limit, increase limit
# SCOUT_MAX_FILE_SIZE in .env

# 4. Check connection pool
docker logs scout-mcp | grep "Connection"
```

---

## Scaling

### Vertical Scaling (Single Instance)

**Approach:** Increase resource allocation on single instance

```bash
# Edit docker-compose.yaml
deploy:
  resources:
    limits:
      cpus: '2.0'     # Increase from 1.0
      memory: '1G'    # Increase from 512M
    reservations:
      cpus: '1.0'
      memory: '512M'

# Increase pool size
SCOUT_MAX_POOL_SIZE=200  # Increase from 100

# Restart
docker-compose down scout
docker-compose up -d scout
```

**When to use:**
- < 1000 requests/minute
- < 50 concurrent connections
- Single application instance

### Horizontal Scaling (Multiple Instances)

**Approach:** Deploy multiple instances behind load balancer

```yaml
# docker-compose-ha.yaml
version: '3.8'

services:
  # Instance 1
  scout-1:
    image: scout_mcp:v0.2.0
    ports:
      - "53001:8000"
    environment:
      SCOUT_API_KEYS: "${SCOUT_API_KEYS}"
    volumes:
      - ~/.ssh/config:/home/scout/.ssh/config:ro
      - ~/.ssh/known_hosts:/home/scout/.ssh/known_hosts:ro

  # Instance 2
  scout-2:
    image: scout_mcp:v0.2.0
    ports:
      - "53002:8000"
    environment:
      SCOUT_API_KEYS: "${SCOUT_API_KEYS}"
    volumes:
      - ~/.ssh/config:/home/scout/.ssh/config:ro
      - ~/.ssh/known_hosts:/home/scout/.ssh/known_hosts:ro

  # Instance 3
  scout-3:
    image: scout_mcp:v0.2.0
    ports:
      - "53003:8000"
    environment:
      SCOUT_API_KEYS: "${SCOUT_API_KEYS}"
    volumes:
      - ~/.ssh/config:/home/scout/.ssh/config:ro
      - ~/.ssh/known_hosts:/home/scout/.ssh/known_hosts:ro

  # HAProxy Load Balancer
  haproxy:
    image: haproxy:2.8-alpine
    ports:
      - "53000:8000"
    volumes:
      - ./haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro
    depends_on:
      - scout-1
      - scout-2
      - scout-3

networks:
  scout_network:
    driver: bridge
```

**Deploy HA:**
```bash
docker-compose -f docker-compose-ha.yaml up -d

# Health checks
curl http://localhost:53000/health  # Via load balancer
curl http://localhost:53001/health  # Instance 1
curl http://localhost:53002/health  # Instance 2
curl http://localhost:53003/health  # Instance 3
```

**When to use:**
- > 1000 requests/minute
- High availability required
- Geographic distribution needed

---

## Disaster Recovery

### Backup Strategy

```bash
# Backup SSH config (on host)
tar czf ~/scout-backup-$(date +%Y%m%d).tar.gz ~/.ssh/

# Backup .env file
cp .env .env.backup.$(date +%Y%m%d)

# Store securely
scp ~/scout-backup-*.tar.gz backup-server:/backups/
```

### Recovery Procedures

#### Scenario 1: Container Crash

```bash
# 1. Check logs
docker logs scout-mcp

# 2. Restart container
docker-compose restart scout

# 3. Verify
curl http://localhost:53000/health
```

#### Scenario 2: Host Failure

```bash
# 1. Deploy on new host
docker-compose pull scout
docker-compose up -d scout

# 2. Restore SSH config
tar xzf scout-backup-20251207.tar.gz

# 3. Verify all hosts reachable
docker exec scout-mcp ssh tootie "whoami"
docker exec scout-mcp ssh squirts "whoami"
```

#### Scenario 3: SSH Key Lost

```bash
# 1. Generate new SSH key
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa

# 2. Add public key to remote hosts
ssh-copy-id -i ~/.ssh/id_rsa.pub tootie
ssh-copy-id -i ~/.ssh/id_rsa.pub squirts

# 3. Update known_hosts
ssh-keyscan tootie >> ~/.ssh/known_hosts
ssh-keyscan squirts >> ~/.ssh/known_hosts

# 4. Restart service
docker-compose restart scout
```

#### Scenario 4: Full Service Rebuild

```bash
# 1. Stop service
docker-compose down scout

# 2. Remove container/image (if corrupted)
docker rm scout-mcp
docker rmi scout_mcp:v0.2.0

# 3. Rebuild from scratch
docker build -t scout_mcp:v0.2.0 .

# 4. Redeploy
docker-compose up -d scout

# 5. Verify
curl http://localhost:53000/health
```

### Testing Recovery

```bash
# Monthly: Test restore procedure
# 1. Note current version
docker-compose ps

# 2. Simulate failure
docker-compose down scout

# 3. Follow recovery procedure
docker-compose up -d scout

# 4. Verify
curl http://localhost:53000/health

# 5. Document results
echo "Recovery test $(date): SUCCESS" >> .docs/recovery-tests.log
```

---

## Operations Checklist

### Daily
- [ ] Check health endpoint: `curl http://localhost:53000/health`
- [ ] Review error logs: `docker logs scout-mcp | grep ERROR`
- [ ] Monitor resource usage: `docker stats scout-mcp`

### Weekly
- [ ] Check connection pool metrics in logs
- [ ] Test SSH to all configured hosts
- [ ] Review rate limiting activity
- [ ] Check for container restarts

### Monthly
- [ ] Test disaster recovery procedures
- [ ] Update dependencies: `uv lock --upgrade`
- [ ] Review security settings
- [ ] Analyze performance trends

### Quarterly
- [ ] Full security audit
- [ ] Capacity planning review
- [ ] Document lessons learned
- [ ] Plan next version features

---

## Additional Resources

- [Security Guide](./SECURITY.md)
- [Testing Guide](./docs/TESTING.md)
- [Architecture Docs](./README.md)
- [CI/CD Review](./docs/CICD-AND-DEVOPS-REVIEW.md)

---

**Document Version:** 1.0
**Last Updated:** December 7, 2025
**Maintained By:** Scout MCP Team
**Next Review:** March 7, 2026
