# CI/CD & DevOps Quick Reference

**For:** Scout MCP Project
**Updated:** December 7, 2025
**Status:** Implementation Phase 1

---

## Assessment Summary

| Category | Score | Status |
|----------|-------|--------|
| **Build Automation** | 2/10 | ❌ Needs Dockerfile |
| **CI/CD Pipeline** | 0/10 | ❌ Needs GitHub Actions |
| **Deployment** | 1/10 | ❌ Needs docker-compose |
| **Infrastructure** | 1/10 | ❌ Needs IaC |
| **Monitoring** | 4/10 | ⚠️ Partial |
| **Security** | 8/10 | ✅ Strong |
| **Testing** | 8/10 | ✅ Good |
| **Documentation** | 7/10 | ⚠️ Gaps |
| **Overall** | **4/10** | **Development** |

---

## Critical Gaps (Must Fix)

### 1. No Container Image
**Blocker:** Cannot deploy to cloud/orchestration
**Effort:** 2 hours
**Fix:** Create Dockerfile with multi-stage build

```dockerfile
FROM python:3.11-slim as builder
# ... dependencies installation ...
FROM python:3.11-slim
# ... copy venv, app, set user ...
EXPOSE 8000
HEALTHCHECK ...
CMD ["python", "-m", "scout_mcp"]
```

### 2. No CI/CD Pipeline
**Blocker:** No automated testing/quality gates
**Effort:** 3 hours
**Fix:** Create .github/workflows/ci.yaml with:
- Test suite (pytest)
- Linting (ruff, mypy)
- Security scan (pip-audit)
- Docker build

### 3. No docker-compose.yaml
**Blocker:** Manual deployment, operational uncertainty
**Effort:** 1 hour
**Fix:** Create docker-compose.yaml with:
- scout service (port 53000)
- Environment variables
- Health checks
- Volume mounts (SSH)
- Restart policy

### 4. No Deployment Documentation
**Blocker:** Team onboarding, operational procedures
**Effort:** 3 hours
**Fix:** Create DEPLOYMENT.md with:
- Architecture overview
- Prerequisites
- Deployment steps
- Configuration guide
- Troubleshooting
- Scaling procedures

---

## Quick Implementation Timeline

### Week 1: Core Deployment Automation
- **Day 1:** Dockerfile (2h) + .dockerignore
- **Day 2:** docker-compose.yaml (1h) + DEPLOYMENT.md (2h)
- **Day 3:** GitHub Actions CI (2h) + testing
- **Day 4:** Testing & verification
- **Day 5:** Documentation & review

### Week 2: Security Hardening
- Output size limits (SEC-P0-4)
- Connection timeouts (P1-1)
- Health check rate limiting (SEC-007)
- Add security tests

### Week 3: Operational Readiness
- Connection pool metrics
- Operational runbooks
- Port/service registry
- Deployment log template

### Week 4: Coverage & Quality
- Test coverage enforcement (85%+)
- Additional security tests
- E2E test suite (if applicable)

---

## Key Metrics to Track

### Build Quality
- Test coverage: **Target 85%+** (currently ~75%)
- Test execution time: < 30 seconds
- Lint issues: 0
- Type errors: 0
- Security findings: 0 critical

### Deployment Success
- Deployment frequency: > 1x/week
- Deployment duration: < 5 minutes
- Deployment failure rate: < 5%
- MTTR (Mean Time To Recovery): < 15 minutes

### Operational Health
- Uptime: > 99.5%
- Error rate: < 1%
- Health check passing: 100%
- Connection pool utilization: < 75%

---

## Security Checklist

### Pre-Deployment
- [ ] API key authentication enabled
- [ ] Rate limiting configured
- [ ] SSH host key verification enabled
- [ ] Network binding appropriate (0.0.0.0 or 127.0.0.1)
- [ ] File/output size limits configured
- [ ] Connection timeouts configured
- [ ] All tests passing
- [ ] No security warnings in logs

### Post-Deployment
- [ ] Health check responding
- [ ] API key auth working
- [ ] Rate limiting enforcing
- [ ] Can connect to SSH hosts
- [ ] No errors in logs (first hour)
- [ ] Resource usage normal

---

## Port Management

**Requirement:** All services must use high ports (53000+)

### Scout MCP Ports

| Service | Port | Environment | Notes |
|---------|------|-------------|-------|
| scout-mcp | 53000 | production | Primary API |
| scout-mcp | 53001 | staging | Testing |
| scout-mcp | 8000 | development | Local dev |

**Checking Port Availability:**
```bash
# Before deployment
ss -tuln | grep 53000
# If empty, port is available

# If occupied
lsof -i :53000
```

---

## Environment Variables Reference

### Required
```bash
SCOUT_API_KEYS="your-generated-key"
```

### Recommended (Production)
```bash
SCOUT_HTTP_PORT=53000
SCOUT_RATE_LIMIT_PER_MINUTE=60
SCOUT_STRICT_HOST_KEY_CHECKING=true
SCOUT_LOG_LEVEL=INFO
SCOUT_MAX_FILE_SIZE=1048576
SCOUT_MAX_OUTPUT_SIZE=10485760
SCOUT_COMMAND_TIMEOUT=30
SCOUT_SSH_CONNECT_TIMEOUT=30
```

### Optional
```bash
SCOUT_HTTP_HOST=0.0.0.0
SCOUT_IDLE_TIMEOUT=60
SCOUT_MAX_POOL_SIZE=100
SCOUT_LOG_PAYLOADS=false
SCOUT_INCLUDE_TRACEBACK=false
```

---

## Common Operations

### Deploy
```bash
# Using docker-compose
docker-compose up -d scout

# Verify
curl http://localhost:53000/health
docker logs -f scout-mcp
```

### Stop
```bash
# Graceful shutdown
docker-compose down scout

# Force shutdown (emergency)
docker-compose kill scout
docker rm scout-mcp
```

### Restart
```bash
docker-compose restart scout
```

### View Logs
```bash
# All logs
docker logs scout-mcp

# Follow in real-time
docker logs -f scout-mcp

# Last 100 lines
docker logs --tail=100 scout-mcp

# Filter for errors
docker logs scout-mcp | grep ERROR
```

### Update Configuration
```bash
# 1. Edit .env
nano .env

# 2. Recreate container (picks up new env)
docker-compose down scout
docker-compose up -d scout

# 3. Verify
docker exec scout-mcp env | grep SCOUT_
```

### Check Resource Usage
```bash
docker stats scout-mcp
# Shows: CPU%, Memory%, Network I/O
```

---

## Troubleshooting Quick Wins

### Container Won't Start
```bash
# 1. Check logs
docker logs scout-mcp

# 2. Common fixes
#    - Missing SCOUT_API_KEYS? Set in .env
#    - Port in use? Change SCOUT_HTTP_PORT
#    - SSH issue? Verify ~/.ssh/config mounted
```

### Slow Responses
```bash
# 1. Check network latency
docker exec scout-mcp ping -c 3 tootie

# 2. Check resource usage
docker stats scout-mcp

# 3. If memory high, reduce pool size
# Edit .env: SCOUT_MAX_POOL_SIZE=50
```

### Rate Limiting Too Strict
```bash
# Edit .env
SCOUT_RATE_LIMIT_PER_MINUTE=120  # Increase from 60
docker-compose restart scout
```

### SSH Connection Fails
```bash
# 1. Test SSH from container
docker exec scout-mcp ssh tootie "whoami"

# 2. Check known_hosts
docker exec scout-mcp cat /home/scout/.ssh/known_hosts | grep tootie

# 3. If missing, add host
docker exec scout-mcp ssh-keyscan tootie >> ~/.ssh/known_hosts
docker-compose restart scout
```

---

## GitHub Actions Workflow Outline

```yaml
name: CI/CD

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
      - run: curl -LsSf https://astral.sh/uv/install.sh | sh
      - run: uv sync
      - run: uv run pytest tests/ -v --cov=scout_mcp
      - run: uv run coverage report --fail-under=85

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
      - run: uv sync
      - run: uv run ruff check scout_mcp/ tests/
      - run: uv run mypy scout_mcp/

  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v2
      - run: docker build -t scout_mcp:latest .
```

---

## Dockerfile Template

```dockerfile
# Build stage
FROM python:3.11-slim as builder
WORKDIR /build
COPY pyproject.toml uv.lock ./
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"
RUN uv sync --frozen --no-dev

# Runtime stage
FROM python:3.11-slim
RUN apt-get update && apt-get install -y curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 scout
WORKDIR /app
COPY --from=builder --chown=scout:scout /build/.venv /app/.venv
COPY --chown=scout:scout scout_mcp ./scout_mcp
USER scout
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=30s CMD curl -f http://localhost:8000/health
CMD ["python", "-m", "scout_mcp"]
```

---

## docker-compose.yaml Template

```yaml
version: '3.8'

services:
  scout:
    image: scout_mcp:latest
    build: .
    ports:
      - "${SCOUT_HTTP_PORT:-53000}:8000"
    environment:
      SCOUT_API_KEYS: "${SCOUT_API_KEYS:?Error: set SCOUT_API_KEYS}"
      SCOUT_HTTP_HOST: "0.0.0.0"
      SCOUT_LOG_LEVEL: "${SCOUT_LOG_LEVEL:-INFO}"
      SCOUT_RATE_LIMIT_PER_MINUTE: "${SCOUT_RATE_LIMIT_PER_MINUTE:-60}"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 3s
      retries: 3
    restart: unless-stopped
    volumes:
      - ~/.ssh/config:/home/scout/.ssh/config:ro
      - ~/.ssh/known_hosts:/home/scout/.ssh/known_hosts:ro
```

---

## Testing Commands

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_security.py -v

# Run with coverage
uv run pytest tests/ --cov=scout_mcp --cov-report=html

# Check coverage threshold
uv run coverage report --fail-under=85

# Run linting
uv run ruff check scout_mcp/ tests/
uv run ruff format scout_mcp/ tests/

# Type checking
uv run mypy scout_mcp/ --strict
```

---

## Deployment Checklist

### Pre-Deployment (48 hours before)
- [ ] All tests passing
- [ ] Coverage >= 85%
- [ ] No linting errors
- [ ] No type errors
- [ ] Docker image builds successfully
- [ ] SSH configuration verified
- [ ] Port 53000+ available
- [ ] API key generated

### Deployment Day
- [ ] Backup current configuration
- [ ] Pull latest image
- [ ] Update docker-compose.yaml
- [ ] Deploy: `docker-compose up -d scout`
- [ ] Verify health check
- [ ] Check logs for errors
- [ ] Test basic operations

### Post-Deployment
- [ ] Monitor for 1 hour
- [ ] Verify no errors in logs
- [ ] Check resource usage
- [ ] Test all functionality
- [ ] Update deployment log

---

## Incident Response Quick Guide

### If Service Down
```bash
# 1. Check if container running
docker ps | grep scout-mcp

# 2. Check logs
docker logs scout-mcp

# 3. Restart
docker-compose restart scout

# 4. If still down, rollback
docker-compose down scout
# Update image tag in docker-compose.yaml
docker-compose up -d scout
```

### If Rate Limiting Issues
```bash
# Increase limit
sed -i 's/SCOUT_RATE_LIMIT_PER_MINUTE=60/SCOUT_RATE_LIMIT_PER_MINUTE=120/' .env
docker-compose down scout
docker-compose up -d scout
```

### If SSH Connection Issues
```bash
# Test SSH from container
docker exec scout-mcp ssh tootie "whoami"

# If fails, update known_hosts
docker exec scout-mcp ssh-keyscan tootie >> ~/.ssh/known_hosts
docker-compose restart scout
```

---

## DevOps Maturity Roadmap

### Phase 1: Core Deployment (Current)
- [ ] Dockerfile ✅ TODO
- [ ] docker-compose.yaml ✅ TODO
- [ ] GitHub Actions CI ✅ TODO
- [ ] DEPLOYMENT.md ✅ TODO

### Phase 2: Security Hardening
- [ ] Output size limits
- [ ] Connection timeouts
- [ ] Security tests
- [ ] Vulnerability scanning

### Phase 3: Operational Readiness
- [ ] Connection pool metrics
- [ ] Operational runbooks
- [ ] Health check enhancements
- [ ] Alert rules

### Phase 4: High Availability
- [ ] Multi-instance deployment
- [ ] Load balancing
- [ ] Redis-backed rate limiting
- [ ] Distributed tracing

### Phase 5: Enterprise Ready
- [ ] Prometheus integration
- [ ] Grafana dashboards
- [ ] External secret management
- [ ] Audit logging

---

## Key Contacts & Resources

**Documentation:**
- Security Guide: `./SECURITY.md`
- Deployment Guide: `./docs/DEPLOYMENT.md`
- Testing Guide: `./docs/TESTING.md`
- Full CI/CD Review: `./docs/CICD-AND-DEVOPS-REVIEW.md`

**Tools:**
- GitHub: https://github.com/jmagar/scout_mcp
- Container Registry: ghcr.io/username/scout_mcp
- Project Issues: GitHub Issues

**Community:**
- Python: 3.11+
- Framework: FastMCP (MCP SDK)
- SSH: asyncssh

---

**Version:** 1.0
**Status:** Draft - Implementation Pending
**Target Implementation:** Week of December 7, 2025
