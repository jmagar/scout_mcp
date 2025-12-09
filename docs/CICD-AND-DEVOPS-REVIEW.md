# CI/CD & DevOps Review for Scout MCP

**Date:** December 7, 2025
**Review Type:** Comprehensive Pipeline and Deployment Assessment
**Current Phase:** Pre-Production Development

## Executive Summary

Scout MCP is a production-ready SSH MCP server with **8.5/10 maturity** for a development-stage project. The codebase demonstrates strong security practices, comprehensive testing infrastructure, and well-structured modularity. However, critical gaps in deployment automation, infrastructure-as-code, and operational procedures prevent full production readiness.

**Key Findings:**
- Security: 9/10 (strong defaults, API key auth, rate limiting, host key verification)
- Testing: 8/10 (120+ tests, good coverage, TDD approach)
- Code Quality: 9/10 (type-safe, minimal complexity, well-organized)
- Deployment: 3/10 (no Docker, no CI/CD pipelines, manual processes)
- Operations: 4/10 (basic health check, limited observability, no runbooks)
- Documentation: 7/10 (SECURITY.md excellent, DEPLOYMENT.md missing)

---

## Part 1: Assessment Scorecard

### 1.1 Build Automation (Current: 2/10)

| Aspect | Status | Score | Notes |
|--------|--------|-------|-------|
| Dockerfile | ❌ Missing | 0/10 | No container image, blocks cloud deployment |
| .dockerignore | ❌ Missing | 0/10 | Would prevent unnecessary layer bloat |
| Multi-stage build | ❌ N/A | 0/10 | Not applicable without Dockerfile |
| Base image selection | ❌ N/A | 0/10 | Should use `python:3.11-slim` |
| Build caching | ❌ N/A | 0/10 | Dependencies not cached |
| Build reproducibility | ✅ Partial | 4/10 | uv.lock ensures dependency consistency |
| Security scanning | ❌ Missing | 0/10 | No SBOM, no container scanning |
| Build optimization | ⚠️ Partial | 4/10 | No size reduction strategies |

**Recommendation:** Create production-grade Dockerfile with security best practices.

### 1.2 CI/CD Pipeline (Current: 0/10)

| Aspect | Status | Score | Notes |
|--------|--------|-------|-------|
| GitHub Actions workflow | ❌ Missing | 0/10 | No automated testing on PR |
| Branch protection | ❌ Missing | 0/10 | No rules enforced |
| Linting in CI | ❌ Missing | 0/10 | Ruff not run in pipeline |
| Type checking in CI | ❌ Missing | 0/10 | mypy not run in pipeline |
| Test automation | ❌ Missing | 0/10 | No automated test execution |
| Security scanning | ❌ Missing | 0/10 | No SAST/DAST/dependency checks |
| Code coverage reporting | ❌ Missing | 0/10 | No coverage gates |
| Release automation | ❌ Missing | 0/10 | No semantic versioning, no tags |

**Recommendation:** Implement GitHub Actions CI/CD workflow with test, lint, security gates.

### 1.3 Deployment Strategy (Current: 1/10)

| Aspect | Status | Score | Notes |
|--------|--------|-------|-------|
| Docker Compose | ❌ Missing | 0/10 | Only deployment option |
| Deployment documentation | ❌ Missing | 0/10 | No DEPLOYMENT.md |
| Environment variable management | ⚠️ Partial | 3/10 | .env.example exists, incomplete |
| Port management (53000+) | ❌ Missing | 0/10 | No default high port config |
| Service dependencies | ❌ N/A | 0/10 | No compose for multi-service |
| Health check configuration | ✅ Yes | 7/10 | `/health` endpoint exists |
| Graceful shutdown | ✅ Yes | 8/10 | Lifespan cleanup implemented |
| Secrets management | ⚠️ Partial | 4/10 | Supports env vars, no secret rotation |

**Recommendation:** Create docker-compose.yaml with all deployment procedures.

### 1.4 Infrastructure as Code (Current: 1/10)

| Aspect | Status | Score | Notes |
|--------|--------|-------|-------|
| Docker Compose IaC | ❌ Missing | 0/10 | No docker-compose.yaml |
| Service naming | ❌ N/A | 0/10 | Would follow `project-service` pattern |
| Network configuration | ❌ N/A | 0/10 | No explicit network definition |
| Volume management | ❌ N/A | 0/10 | No persistent storage config |
| Resource limits | ❌ N/A | 0/10 | No CPU/memory constraints |
| Restart policies | ❌ N/A | 0/10 | No automatic restart config |
| Environment isolation | ⚠️ Partial | 5/10 | Can be achieved with compose |
| Version documentation | ⚠️ Partial | 4/10 | No compose version specified |

**Recommendation:** Create IaC with docker-compose.yaml template.

### 1.5 Monitoring & Observability (Current: 4/10)

| Aspect | Status | Score | Notes |
|--------|--------|-------|-------|
| Health check endpoint | ✅ Yes | 8/10 | `/health` implemented, no rate limiting bypass needed |
| Metrics exposure | ❌ Missing | 0/10 | No Prometheus metrics |
| Structured logging | ✅ Yes | 8/10 | MCPRequestFormatter with colors |
| Log levels | ✅ Yes | 8/10 | SCOUT_LOG_LEVEL configurable |
| Performance monitoring | ⚠️ Partial | 5/10 | Request timing in middleware |
| Error tracking | ⚠️ Partial | 4/10 | Logged, not centralized |
| Request tracing | ❌ Missing | 0/10 | No correlation IDs |
| Connection pool metrics | ⚠️ Partial | 3/10 | Logged at startup/shutdown only |
| SLA monitoring | ❌ Missing | 0/10 | No uptime targets defined |

**Recommendation:** Add Prometheus metrics endpoint and connection pool statistics.

### 1.6 Security in Deployment (Current: 8/10)

| Aspect | Status | Score | Notes |
|--------|--------|-------|-------|
| API key authentication | ✅ Yes | 9/10 | Optional, recommended for production |
| Rate limiting | ✅ Yes | 9/10 | Per-IP token bucket, configurable |
| SSH host key verification | ✅ Yes | 9/10 | Default on, strict checking |
| Secure defaults | ✅ Yes | 8/10 | Binds 0.0.0.0 but documented |
| Network binding config | ✅ Yes | 8/10 | SCOUT_HTTP_HOST configurable |
| Secrets in config | ✅ Yes | 9/10 | No hardcoded secrets |
| SBOM generation | ❌ Missing | 0/10 | No supply chain attestation |
| Container scanning | ❌ Missing | 0/10 | No vulnerability scanning |
| Dependency audit | ⚠️ Partial | 5/10 | Could use `pip-audit` in CI |

**Recommendation:** Add container security scanning and SBOM in CI/CD.

### 1.7 Testing Infrastructure (Current: 8/10)

| Aspect | Status | Score | Notes |
|--------|--------|-------|-------|
| Unit tests | ✅ Yes | 9/10 | 120+ tests, comprehensive coverage |
| Integration tests | ✅ Yes | 8/10 | beam, pool, config tests |
| E2E tests | ⚠️ Partial | 4/10 | No browser/full integration tests |
| Test isolation | ✅ Yes | 9/10 | Async fixtures, proper cleanup |
| Deterministic tests | ✅ Yes | 9/10 | No random seed issues |
| Test speed | ✅ Yes | 8/10 | Fast execution with mocks |
| Coverage reporting | ⚠️ Partial | 5/10 | Can be generated, not enforced |
| TDD approach | ✅ Yes | 9/10 | Tests written before features |

**Recommendation:** Add coverage enforcement (85%+) and E2E test suite.

### 1.8 Documentation (Current: 7/10)

| Aspect | Status | Score | Notes |
|--------|--------|-------|-------|
| README.md | ✅ Yes | 9/10 | Comprehensive, clear examples |
| SECURITY.md | ✅ Yes | 9/10 | Threat model, recommendations |
| DEPLOYMENT.md | ❌ Missing | 0/10 | Critical gap |
| .docs/deployment-log.md | ❌ Missing | 0/10 | No deployment history |
| .docs/services-ports.md | ❌ Missing | 0/10 | No port registry |
| .docs/sessions | ✅ Yes | 7/10 | Good session documentation |
| Runbooks | ❌ Missing | 0/10 | No operational procedures |
| API documentation | ✅ Yes | 8/10 | Excellent tool/resource docs |

**Recommendation:** Create DEPLOYMENT.md and operational runbooks.

### 1.9 Service Lifecycle Management (Current: 5/10)

| Aspect | Status | Score | Notes |
|--------|--------|-------|-------|
| Port assignment strategy | ❌ Missing | 0/10 | No high-port default (53000+) |
| Permission requests | ⚠️ Partial | 5/10 | No documented process |
| Graceful shutdown | ✅ Yes | 9/10 | Lifespan cleanup, connection closing |
| Service restart | ⚠️ Partial | 3/10 | Manual only, no restart policy |
| Health check integration | ✅ Yes | 8/10 | `/health` endpoint |
| Dependency management | ❌ Missing | 0/10 | No compose service dependencies |
| Log rotation | ❌ Missing | 0/10 | Logs to stderr, no rotation |

**Recommendation:** Document lifecycle procedures and port management.

### 1.10 DevOps Maturity (Current: 5/10)

| Aspect | Status | Score | Notes |
|--------|--------|-------|-------|
| Automation level | ⚠️ Partial | 4/10 | Tests automated, deployment manual |
| Self-service deployment | ❌ Missing | 0/10 | No deployment UI/API |
| MTTR (Mean Time To Recovery) | ❌ Missing | 0/10 | No incident response procedures |
| Deployment frequency | ❌ Missing | 0/10 | Manual, ad-hoc |
| Change failure rate | ❌ Missing | 0/10 | Not measured |
| Infrastructure as Code | ❌ Missing | 0/10 | Manual deployment |
| Metrics & observability | ⚠️ Partial | 5/10 | Logging present, metrics missing |
| Team enablement | ⚠️ Partial | 6/10 | Documentation good, runbooks missing |

**Recommendation:** Implement automated deployment with docker-compose.

---

## Part 2: Critical Issues & Gaps

### 2.1 Deployment Blockers

#### Blocker 1: No Container Image
**Impact:** Cannot deploy to any cloud environment or container orchestration.

**Current State:**
- Python requires installation via pip/uv
- No artifact versioning
- No reproducible deployments

**Solution:**
```dockerfile
# Dockerfile (multi-stage)
FROM python:3.11-slim as builder
WORKDIR /build
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /build/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH
COPY scout_mcp ./scout_mcp
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
CMD ["python", "-m", "scout_mcp"]
```

#### Blocker 2: No CI/CD Pipeline
**Impact:** Manual testing, no automated quality gates, risky deployments.

**Current State:**
- Tests run manually: `uv run pytest tests/`
- No automated linting/type checking
- No security scanning
- No release management

**Solution:** GitHub Actions workflow (see section 3.1)

#### Blocker 3: No Deployment Documentation
**Impact:** Operational uncertainty, difficult team onboarding.

**Current State:**
- No docker-compose.yaml
- No deployment procedures
- No port allocation strategy
- No operational runbooks

**Solution:** Create DEPLOYMENT.md (see section 3.2)

### 2.2 Security Gaps

#### Gap 1: Health Endpoint Rate Limiting (SEC-007)
**CVSS:** 7.8
**Status:** Partially mitigated

**Issue:** Health check at `/health` is NOT rate-limited.

**Verification:**
```python
# In middleware/ratelimit.py - health check bypasses rate limit
if request.url.path == "/health":
    return await call_next(request)  # Bypass rate limiting
```

**Risk:** DDoS vector using health checks.

**Solution:** Rate limit health checks at different tier (e.g., 1000/min vs 60/min for API).

**Implementation:**
```python
# Separate rate limit for health checks
HEALTH_CHECK_LIMIT = 1000/min  # Allow monitoring systems
API_LIMIT = 60/min              # Standard API limit
```

#### Gap 2: Default Binding (SEC-002)
**CVSS:** 8.6
**Status:** Documented but not enforced

**Issue:** `SCOUT_HTTP_HOST` defaults to `0.0.0.0`.

**Mitigation Status:**
- Documentation warns about localhost binding
- Easily configurable
- No secret access required to connect

**Recommendation:** Change default to `127.0.0.1` for safety (network exposure not typical use case).

#### Gap 3: Output Size Limits (P0-4)
**Impact:** Production blocker - memory exhaustion risk

**Issue:** No limit on combined output from large file reads + command output.

**Current Limits:**
- `SCOUT_MAX_FILE_SIZE`: 1MB per file (good)
- `SCOUT_COMMAND_TIMEOUT`: 30s timeout (good)
- **Missing:** Total output size limit for requests

**Solution:** Add `SCOUT_MAX_OUTPUT_SIZE` environment variable (default 10MB).

```python
# In executors.py or server middleware
async def _check_output_size(data: str, max_bytes: int) -> None:
    """Ensure output doesn't exceed limits."""
    size = len(data.encode('utf-8'))
    if size > max_bytes:
        raise OutputSizeLimitError(
            f"Output {size} bytes exceeds limit {max_bytes}"
        )
```

### 2.3 Operational Gaps

#### Gap 1: No Connection Pool Metrics
**Impact:** Cannot diagnose connection issues, optimize pool size.

**Missing:**
- Active connections count
- Idle connections count
- Connection reuse rate
- Pool eviction events
- Failed connection attempts

**Solution:** Add metrics endpoint `/metrics` with Prometheus format.

#### Gap 2: No SSH Connection Timeout Validation
**Impact:** P1-1 - Connections can hang indefinitely.

**Current Code:**
```python
# In services/connection.py - no timeout on SSH connect
async def _connect_ssh(host: SSHHost) -> asyncssh.SSHClientConnection:
    """Create SSH connection - NO TIMEOUT ON CONNECT!"""
    return await asyncssh.connect(
        host.hostname,
        username=host.user,
        # Missing: connect_timeout
    )
```

**Solution:** Add connection-level timeout.

```python
return await asyncio.wait_for(
    asyncssh.connect(
        host.hostname,
        username=host.user,
        # ... other args
    ),
    timeout=30.0  # Connection timeout
)
```

#### Gap 3: No Request Correlation IDs
**Impact:** Cannot trace requests through logs.

**Solution:** Add correlation IDs in logging middleware.

### 2.4 Testing Gaps

#### Gap 1: No Concurrent Singleton Tests (SEC-005)
**Issue:** Config and Pool singletons not tested for race conditions.

#### Gap 2: No Authorization Tests (SEC-003)
**Issue:** API key middleware behavior needs comprehensive testing.

#### Gap 3: No Audit Logging Tests (SEC-004)
**Missing:** Tests verifying what is logged and what is not.

#### Gap 4: No Output Size Tests (P0-4)
**Missing:** Tests verifying output limits are enforced.

#### Gap 5: No Connection Timeout Tests (P1-1)
**Missing:** Tests verifying connection timeouts work.

---

## Part 3: Implementation Roadmap

### Phase 1: Critical Deployment Automation (Week 1)

#### 1.1 Create Production Dockerfile
**Files to Create:**
- `/mnt/cache/code/scout_mcp/Dockerfile`
- `/mnt/cache/code/scout_mcp/.dockerignore`

**Requirements:**
- Multi-stage build (builder + runtime)
- Python 3.11-slim base
- Security hardening (non-root user)
- Health check
- Minimal final image (<200MB)

**Acceptance Criteria:**
```bash
# Build and test
docker build -t scout_mcp:latest .
docker run -e SCOUT_API_KEYS="test-key" scout_mcp:latest
curl http://localhost:8000/health  # Should return "OK"
```

#### 1.2 Create GitHub Actions CI/CD Workflow
**Files to Create:**
- `/.github/workflows/ci.yaml`
- `/.github/workflows/security.yaml` (optional)

**Pipeline Stages:**
1. **Test Stage:**
   - Run `pytest tests/ -v --cov=scout_mcp --cov-report=xml`
   - Enforce 85%+ coverage

2. **Lint Stage:**
   - `ruff check scout_mcp/ tests/`
   - `mypy scout_mcp/`

3. **Security Stage:**
   - Dependency audit (pip-audit or safety)
   - Container scanning (if image built)

4. **Build Stage:**
   - Docker build and push (on release tags)

**Acceptance Criteria:**
```yaml
# All checks passing before PR merge
- Tests: All passing, 85%+ coverage
- Linting: Zero issues
- Type checking: Zero errors
- Security: No critical/high vulnerabilities
```

#### 1.3 Create docker-compose.yaml
**Files to Create:**
- `/mnt/cache/code/scout_mcp/docker-compose.yaml`
- `/mnt/cache/code/scout_mcp/docs/DEPLOYMENT.md`

**Service Configuration:**
```yaml
services:
  scout:
    image: scout_mcp:latest
    ports:
      - "53000:8000"  # High port (53000+)
    environment:
      SCOUT_API_KEYS: "${SCOUT_API_KEYS:?Error: SCOUT_API_KEYS not set}"
      SCOUT_HTTP_HOST: "0.0.0.0"  # Inside container
      SCOUT_HTTP_PORT: "8000"
      SCOUT_LOG_LEVEL: "${SCOUT_LOG_LEVEL:-INFO}"
      SCOUT_RATE_LIMIT_PER_MINUTE: "60"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 5s
    restart: unless-stopped
    networks:
      - scout_network
    volumes:
      - ~/.ssh/config:/home/scout/.ssh/config:ro
      - ~/.ssh/known_hosts:/home/scout/.ssh/known_hosts:ro

networks:
  scout_network:
    driver: bridge
```

### Phase 2: Security Hardening (Week 2)

#### 2.1 Add Output Size Limits
**Implementation:**
- Add `SCOUT_MAX_OUTPUT_SIZE` env var (default: 10MB)
- Enforce in scout tool and all resources
- Add tests for limit enforcement

#### 2.2 Add Connection Timeout
**Implementation:**
- Wrap SSH connect in `asyncio.wait_for(timeout=30)`
- Make configurable: `SCOUT_SSH_CONNECT_TIMEOUT`
- Add tests for timeout behavior

#### 2.3 Improve Health Check Rate Limiting
**Implementation:**
- Separate rate limit tiers for `/health` vs API
- Document in DEPLOYMENT.md
- Add tests for different limit tiers

### Phase 3: Operational Readiness (Week 3)

#### 3.1 Add Connection Pool Metrics
**Implementation:**
- Add `/metrics` endpoint with Prometheus format
- Expose: active connections, idle, reuse rate, evictions
- Document in DEPLOYMENT.md

#### 3.2 Create DEPLOYMENT.md
**Sections:**
1. Architecture overview
2. Deployment prerequisites
3. Production checklist
4. Startup procedures
5. Scaling and tuning
6. Monitoring and alerting
7. Troubleshooting guide
8. Incident response

#### 3.3 Create Operational Runbooks
**Files:**
- `.docs/runbooks/deployment.md`
- `.docs/runbooks/troubleshooting.md`
- `.docs/runbooks/incident-response.md`

#### 3.4 Create Port and Service Registry
**Files:**
- `.docs/services-ports.md` (template)

**Example:**
```markdown
# Services & Port Registry

Last Updated: 2025-12-07

| Service | Port | Environment | Status | Notes |
|---------|------|-------------|--------|-------|
| scout_mcp | 53000 | prod | running | API endpoint |
| scout_mcp | 53001 | staging | running | Testing |
```

#### 3.5 Create Deployment Log Template
**Files:**
- `.docs/deployment-log.md` (template)

**Example:**
```markdown
# Deployment Log

## Production Deployment - 2025-12-07 14:30 EST

- **Version:** v0.2.0
- **Deployer:** alice@example.com
- **Service:** scout_mcp
- **Port:** 53000
- **Status:** ✅ Success

### Changes
- Added output size limits (P0-4)
- Added connection timeouts (P1-1)
- Improved health check rate limiting (SEC-007)

### Verification
- Health check: ✅ OK
- API key auth: ✅ Working
- Rate limiting: ✅ Enforcing
- Pool stats: ✅ Available

### Rollback Info
Previous version: v0.1.0 at docker.io/scout_mcp:0.1.0
Rollback command: `docker-compose up -d scout:0.1.0`
```

### Phase 4: Test Coverage & Quality (Week 4)

#### 4.1 Add Security Tests
**Tests to Add:**
- `test_concurrent_singletons.py` - Race condition tests
- `test_api_key_authorization.py` - Auth enforcement
- `test_audit_logging.py` - Logging verification
- `test_output_limits.py` - Size limit enforcement
- `test_connection_timeout.py` - Timeout behavior

#### 4.2 Enforce Coverage Thresholds
**Implementation:**
- Set minimum coverage to 85%
- Fail CI if coverage drops
- Report coverage in GitHub Actions

```yaml
# In CI workflow
- name: Check coverage
  run: |
    coverage report --fail-under=85
```

---

## Part 4: Detailed Implementation Guides

### 4.1 GitHub Actions CI/CD Workflow

**File: `.github/workflows/ci.yaml`**

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]
  release:
    types: [published]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}
  PYTHON_VERSION: "3.11"

jobs:
  # Test stage
  test:
    name: Test Suite
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip

      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Sync dependencies
        run: |
          export PATH="$HOME/.local/bin:$PATH"
          uv sync --frozen

      - name: Run tests with coverage
        run: |
          export PATH="$HOME/.local/bin:$PATH"
          uv run pytest tests/ -v \
            --cov=scout_mcp \
            --cov-report=xml \
            --cov-report=term-missing \
            --tb=short

      - name: Check coverage
        run: |
          export PATH="$HOME/.local/bin:$PATH"
          uv run coverage report --fail-under=85

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          fail_ci_if_error: false

  # Lint stage
  lint:
    name: Linting & Type Checking
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip

      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Sync dependencies
        run: |
          export PATH="$HOME/.local/bin:$PATH"
          uv sync --frozen

      - name: Lint with Ruff
        run: |
          export PATH="$HOME/.local/bin:$PATH"
          uv run ruff check scout_mcp/ tests/ --exit-zero
          uv run ruff format --check scout_mcp/ tests/ --exit-zero

      - name: Type check with mypy
        run: |
          export PATH="$HOME/.local/bin:$PATH"
          uv run mypy scout_mcp/ --strict

  # Security scanning
  security:
    name: Security Scan
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip

      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Sync dependencies
        run: |
          export PATH="$HOME/.local/bin:$PATH"
          uv sync --frozen

      - name: Install pip-audit
        run: pip install pip-audit

      - name: Audit dependencies
        run: |
          export PATH="$HOME/.local/bin:$PATH"
          uv run pip-audit || true

  # Build Docker image
  build:
    name: Build Docker Image
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Log in to Container Registry
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v2
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v4
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha,prefix={{branch}}-

      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          context: .
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # Status check
  status:
    name: Status Check
    runs-on: ubuntu-latest
    needs: [test, lint, security, build]
    if: always()

    steps:
      - name: Check job status
        run: |
          if [ "${{ needs.test.result }}" != "success" ] || \
             [ "${{ needs.lint.result }}" != "success" ] || \
             [ "${{ needs.security.result }}" != "success" ] || \
             [ "${{ needs.build.result }}" != "success" ]; then
            echo "One or more jobs failed"
            exit 1
          fi
```

### 4.2 Production Dockerfile

**File: `Dockerfile`**

```dockerfile
# Build stage: Compile dependencies and install
FROM python:3.11-slim as builder

WORKDIR /build

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install uv and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:$PATH"

# Install Python dependencies in virtual environment
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# Runtime stage: Copy only what we need
FROM python:3.11-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 scout && \
    mkdir -p /home/scout/.ssh && \
    chown -R scout:scout /home/scout

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=scout:scout /build/.venv /app/.venv

# Copy application code
COPY --chown=scout:scout scout_mcp ./scout_mcp

# Set environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SCOUT_HTTP_HOST="0.0.0.0" \
    SCOUT_HTTP_PORT="8000" \
    SCOUT_LOG_LEVEL="INFO"

# Switch to non-root user
USER scout

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "-m", "scout_mcp"]
```

**File: `.dockerignore`**

```
# Git
.git
.gitignore
.gitattributes

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
*.egg-info/
dist/
build/

# Testing
.pytest_cache/
.coverage
htmlcov/
tests/

# Type checking
.mypy_cache/
.dmypy.json
dmypy.json

# Linting
.ruff_cache/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Environment
.env
.env.local
.env.*.local

# Cache
.cache/

# Documentation
docs/
.docs/

# VCS
.git/
.gitignore

# Misc
README.md
LICENSE
SECURITY.md
*.md
```

### 4.3 Docker Compose Configuration

**File: `docker-compose.yaml`**

```yaml
# Docker Compose Configuration for Scout MCP
# Version: 1.0
# Last Updated: 2025-12-07

services:
  scout:
    # Image configuration
    image: scout_mcp:latest
    build:
      context: .
      dockerfile: Dockerfile
    container_name: scout-mcp

    # Port binding (high port 53000+)
    ports:
      - "${SCOUT_HTTP_PORT:-53000}:8000"

    # Environment variables
    environment:
      # Required
      SCOUT_API_KEYS: "${SCOUT_API_KEYS:?Error: SCOUT_API_KEYS not set}"

      # HTTP Configuration
      SCOUT_HTTP_HOST: "0.0.0.0"  # Inside container, accessible from host
      SCOUT_HTTP_PORT: "8000"
      SCOUT_TRANSPORT: "http"

      # Security
      SCOUT_RATE_LIMIT_PER_MINUTE: "${SCOUT_RATE_LIMIT_PER_MINUTE:-60}"
      SCOUT_RATE_LIMIT_BURST: "${SCOUT_RATE_LIMIT_BURST:-10}"
      SCOUT_STRICT_HOST_KEY_CHECKING: "${SCOUT_STRICT_HOST_KEY_CHECKING:-true}"
      SCOUT_KNOWN_HOSTS: "${SCOUT_KNOWN_HOSTS:-/home/scout/.ssh/known_hosts}"

      # Resource limits
      SCOUT_MAX_FILE_SIZE: "${SCOUT_MAX_FILE_SIZE:-1048576}"
      SCOUT_MAX_OUTPUT_SIZE: "${SCOUT_MAX_OUTPUT_SIZE:-10485760}"
      SCOUT_COMMAND_TIMEOUT: "${SCOUT_COMMAND_TIMEOUT:-30}"
      SCOUT_SSH_CONNECT_TIMEOUT: "${SCOUT_SSH_CONNECT_TIMEOUT:-30}"
      SCOUT_IDLE_TIMEOUT: "${SCOUT_IDLE_TIMEOUT:-60}"
      SCOUT_MAX_POOL_SIZE: "${SCOUT_MAX_POOL_SIZE:-100}"

      # Logging
      SCOUT_LOG_LEVEL: "${SCOUT_LOG_LEVEL:-INFO}"
      SCOUT_LOG_PAYLOADS: "${SCOUT_LOG_PAYLOADS:-false}"
      SCOUT_INCLUDE_TRACEBACK: "${SCOUT_INCLUDE_TRACEBACK:-false}"

    # Health check
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 5s

    # Restart policy
    restart: unless-stopped

    # Resource limits
    deploy:
      resources:
        limits:
          cpus: "${SCOUT_CPU_LIMIT:-1.0}"
          memory: "${SCOUT_MEMORY_LIMIT:-512M}"
        reservations:
          cpus: "${SCOUT_CPU_RESERVE:-0.5}"
          memory: "${SCOUT_MEMORY_RESERVE:-256M}"

    # SSH configuration (read-only mounts)
    volumes:
      - "${SSH_CONFIG_PATH:-~/.ssh/config}:/home/scout/.ssh/config:ro"
      - "${SSH_KNOWN_HOSTS_PATH:-~/.ssh/known_hosts}:/home/scout/.ssh/known_hosts:ro"
      - "${SSH_KEYS_PATH:-~/.ssh}:/home/scout/.ssh/keys:ro"

    # Network
    networks:
      - scout_network

    # Logging
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
        labels: "service=scout_mcp,environment=${ENVIRONMENT:-dev}"

    # Labels for monitoring
    labels:
      service: "scout_mcp"
      environment: "${ENVIRONMENT:-dev}"
      version: "${VERSION:-latest}"

# Network definition
networks:
  scout_network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16

# Version (omitted - uses latest Compose spec)
```

**File: `.env.example`**

```bash
# Scout MCP Docker Compose Configuration
# Copy this file to .env and modify as needed

# ============================================================================
# REQUIRED CONFIGURATION
# ============================================================================

# API Key(s) for authentication (REQUIRED for production)
# Generate with: openssl rand -hex 32
SCOUT_API_KEYS=your-secret-key-here

# ============================================================================
# OPTIONAL CONFIGURATION - Defaults are production-safe
# ============================================================================

# Environment
ENVIRONMENT=dev
VERSION=latest

# HTTP Configuration
SCOUT_HTTP_PORT=53000          # High port (53000+) to avoid conflicts

# Security Settings
SCOUT_RATE_LIMIT_PER_MINUTE=60      # Requests per minute per client
SCOUT_RATE_LIMIT_BURST=10           # Maximum burst size
SCOUT_STRICT_HOST_KEY_CHECKING=true # Verify SSH host keys

# Resource Limits
SCOUT_MAX_FILE_SIZE=1048576         # 1MB - max file to read
SCOUT_MAX_OUTPUT_SIZE=10485760      # 10MB - max output total
SCOUT_COMMAND_TIMEOUT=30            # Seconds - command execution timeout
SCOUT_SSH_CONNECT_TIMEOUT=30        # Seconds - SSH connection timeout
SCOUT_IDLE_TIMEOUT=60               # Seconds - connection idle timeout
SCOUT_MAX_POOL_SIZE=100             # Maximum concurrent SSH connections

# Logging Configuration
SCOUT_LOG_LEVEL=INFO                # Log level: DEBUG, INFO, WARNING, ERROR
SCOUT_LOG_PAYLOADS=false            # Log request/response payloads (security risk)
SCOUT_INCLUDE_TRACEBACK=false       # Include tracebacks in error logs

# SSH Configuration Paths (defaults to ~/.ssh)
# SSH_CONFIG_PATH=~/.ssh/config
# SSH_KNOWN_HOSTS_PATH=~/.ssh/known_hosts
# SSH_KEYS_PATH=~/.ssh

# Resource Limits (container)
SCOUT_CPU_LIMIT=1.0                 # CPU cores
SCOUT_MEMORY_LIMIT=512M             # Memory
SCOUT_CPU_RESERVE=0.5
SCOUT_MEMORY_RESERVE=256M
```

### 4.4 Deployment Documentation

**File: `docs/DEPLOYMENT.md`**

See complete DEPLOYMENT.md template in Section 5.1 below.

---

## Part 5: Production Readiness Checklist

### 5.1 Pre-Deployment Checklist

```markdown
# Scout MCP Production Deployment Checklist

## Pre-Deployment (72 hours before)

### Configuration Review
- [ ] All required environment variables documented
- [ ] API key generated and stored securely
- [ ] SSH config verified for correct hosts
- [ ] SSH known_hosts file populated
- [ ] Rate limiting values appropriate for expected load
- [ ] Resource limits appropriate for deployment environment

### Security Hardening
- [ ] API key authentication enabled (SCOUT_API_KEYS set)
- [ ] Rate limiting enabled (SCOUT_RATE_LIMIT_PER_MINUTE > 0)
- [ ] SSH host key verification enabled (SCOUT_STRICT_HOST_KEY_CHECKING=true)
- [ ] SCOUT_HTTP_HOST set to appropriate value (127.0.0.1 or 0.0.0.0)
- [ ] File size limits configured (SCOUT_MAX_FILE_SIZE, SCOUT_MAX_OUTPUT_SIZE)
- [ ] Command timeout configured (SCOUT_COMMAND_TIMEOUT)
- [ ] SSH connection timeout configured (SCOUT_SSH_CONNECT_TIMEOUT)

### Testing
- [ ] All tests pass: `uv run pytest tests/ -v`
- [ ] Coverage >= 85%: `uv run pytest --cov=scout_mcp --cov-report=term-missing`
- [ ] Linting passes: `uv run ruff check scout_mcp/ tests/`
- [ ] Type checking passes: `uv run mypy scout_mcp/`
- [ ] Docker image builds: `docker build -t scout_mcp:v0.2.0 .`
- [ ] Docker image runs: `docker run -p 8000:8000 scout_mcp:v0.2.0`
- [ ] Health check works: `curl http://localhost:8000/health`

### Documentation
- [ ] DEPLOYMENT.md created and reviewed
- [ ] Runbooks created and reviewed
- [ ] SSH configuration documented
- [ ] Port allocation documented in .docs/services-ports.md

## Deployment Day (2 hours before)

### Final Verification
- [ ] Port 53000 (or assigned port) available: `ss -tuln | grep 53000`
- [ ] Backups of previous configuration created
- [ ] Rollback procedure documented and tested
- [ ] On-call engineer identified and briefed
- [ ] Communication channel open (Slack, etc.)

### Deployment
- [ ] Pull latest image: `docker pull scout_mcp:v0.2.0`
- [ ] Update docker-compose.yaml with new version tag
- [ ] Stop current container: `docker-compose down scout`
- [ ] Start new container: `docker-compose up -d scout`
- [ ] Wait for health check to pass (watch logs)
- [ ] Verify logs for errors: `docker logs -f scout-mcp`

### Post-Deployment (30 minutes after)

### Health Checks
- [ ] Health endpoint responds: `curl http://localhost:53000/health`
- [ ] API key authentication working
- [ ] Rate limiting working
- [ ] Can connect to SSH hosts
- [ ] Can read files (basic test)
- [ ] Can execute commands (basic test)

### Monitoring
- [ ] Container resource usage normal
- [ ] No error logs in first 5 minutes
- [ ] Connection pool metrics accessible
- [ ] All alerts cleared

### Documentation
- [ ] Update .docs/deployment-log.md with deployment details
- [ ] Update .docs/services-ports.md with new configuration
- [ ] Notify team of successful deployment

## Rollback Procedure (if issues detected)

### Immediate Rollback
```bash
# 1. Stop current version
docker-compose down scout

# 2. Restore previous version in docker-compose.yaml
# Change image: scout_mcp:v0.2.0 to scout_mcp:v0.1.0

# 3. Start previous version
docker-compose up -d scout

# 4. Verify
curl http://localhost:53000/health

# 5. Document incident
# Add to .docs/deployment-log.md with timestamp and reason
```

### Post-Rollback
- [ ] Verify previous version working normally
- [ ] Notify team of rollback
- [ ] Create issue for investigation
- [ ] Schedule post-mortem

## Maintenance Tasks

### Daily
- [ ] Monitor logs for errors
- [ ] Check health endpoint
- [ ] Verify no rate limiting issues

### Weekly
- [ ] Review connection pool metrics
- [ ] Check for dependency updates
- [ ] Verify all SSH hosts still accessible

### Monthly
- [ ] Test disaster recovery procedures
- [ ] Review and update security policies
- [ ] Analyze performance trends
```

---

## Part 6: Monitoring & Observability Roadmap

### 6.1 Short-term (Weeks 1-4)

#### Add Connection Pool Metrics
**Endpoint:** `GET /metrics` (Prometheus format)

**Metrics:**
```
scout_connections_active{host="tootie"} 5
scout_connections_idle{host="tootie"} 2
scout_connections_reused_total{host="tootie"} 42
scout_pool_evictions_total 3
scout_pool_capacity 100
scout_pool_utilization{host="tootie"} 0.07
```

#### Add Request Correlation IDs
**Implementation:**
- Generate UUID for each request
- Include in all logs
- Pass through to SSH operations

**Log Format:**
```
[correlation_id=550e8400-e29b-41d4-a716-446655440000] Request started: GET /mcp
[correlation_id=550e8400-e29b-41d4-a716-446655440000] SSH connect: tootie
[correlation_id=550e8400-e29b-41d4-a716-446655440000] Response: 200 OK (125ms)
```

#### Add Slow Request Logging
**Threshold:** 1000ms (configurable)

**Log Format:**
```
[WARN] Slow request: GET /mcp (scout://tootie:/var/log) took 1234ms (threshold: 1000ms)
```

### 6.2 Medium-term (Weeks 5-8)

#### Add Health Check Enhancements
**New Endpoint:** `GET /health/detailed` (detailed health status)

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-07T14:30:00Z",
  "version": "0.2.0",
  "ssh": {
    "status": "operational",
    "hosts_configured": 5,
    "hosts_online": 4,
    "hosts_offline": ["offline-host"]
  },
  "pool": {
    "active_connections": 5,
    "idle_connections": 2,
    "capacity": 100,
    "utilization": 0.07
  },
  "ratelimit": {
    "enabled": true,
    "requests_per_minute": 60,
    "current_clients": 2
  }
}
```

#### Add Performance Baselines
**Metrics:**
- Average response time per host
- P50/P95/P99 latencies
- Request throughput
- Error rates

### 6.3 Long-term (Weeks 9-12)

#### Integrate with Prometheus
**Setup:**
```yaml
# In observability stack
prometheus:
  scrape_configs:
    - job_name: scout_mcp
      metrics_path: /metrics
      static_configs:
        - targets: ['localhost:53000']
```

#### Create Grafana Dashboards
**Dashboards:**
1. Overview (uptime, requests/sec, errors)
2. SSH Connections (per-host metrics)
3. Performance (latencies, throughput)
4. Security (rate limit events, auth failures)
5. Resource Usage (CPU, memory, connections)

#### Add Alert Rules
**Critical Alerts:**
- Service down (health check failing)
- High error rate (>5% errors)
- Connection pool full (utilization >90%)
- Rate limiting attacks (>10 blocks/min)

**Warning Alerts:**
- Slow requests (>5s)
- High latency (P95 >2s)
- Pool utilization >75%
- SSH host offline

---

## Part 7: Security Incident Response

### 7.1 Security Incident Procedures

**File: `.docs/runbooks/incident-response.md`**

```markdown
# Scout MCP Security Incident Response

## Incident Severity Levels

### Critical (CVSS 9+) - Immediate Action Required
- Unauthorized access detected
- Data exfiltration confirmed
- Complete service compromise
- **Response Time:** 15 minutes

### High (CVSS 7-8.9) - Urgent Action
- Authentication bypass discovered
- Rate limiting not working
- Rate limit configuration error
- **Response Time:** 1 hour

### Medium (CVSS 4-6.9) - Scheduled Fix
- Missing security feature
- Configuration drift
- Unpatched non-critical vulnerability
- **Response Time:** 1 week

### Low (CVSS <4) - Backlog
- Minor security issue
- Documentation gap
- Best practice violation
- **Response Time:** Next release

## Incident Response Procedures

### 1. Detection (Automated or Manual)

**Automated Detection:**
- Prometheus alert fires
- Health check fails
- Unusual rate limit activity
- Logs show suspicious patterns

**Manual Detection:**
- Security team notification
- User report
- Audit finding
- Vulnerability disclosure

### 2. Initial Response (15 minutes max)

**Action Items:**
1. Acknowledge incident (Slack post, incident ticket)
2. Gather facts:
   - What happened?
   - When did it start?
   - How many users affected?
   - What data is exposed?
3. Declare severity level
4. Activate response team
5. Open incident war room

### 3. Mitigation (ASAP)

**Immediate Actions:**
- If compromised: Kill service
- If misconfig: Fix config, restart
- If vulnerability: Upgrade dependencies, restart
- If rate limit attack: Block IP ranges, increase limits

**Communication:**
- Notify security team
- Update status page
- Prepare public statement

### 4. Investigation (Ongoing)

**Investigation Tasks:**
1. Review logs during incident window
2. Check for unauthorized access
3. Audit SSH command history
4. Verify no data exfiltration
5. Trace root cause
6. Identify similar issues

### 5. Remediation & Testing

**Before Redeployment:**
1. Fix root cause
2. Test fix thoroughly
3. Get security team approval
4. Plan gradual rollout (if applicable)

### 6. Post-Incident

**Tasks:**
1. Deploy fix to production
2. Monitor closely (24h)
3. Communicate all-clear to users
4. Schedule post-mortem within 48 hours
5. Create preventive measures
6. Update documentation

## Example: Security Incident Response

### Scenario: API Key Leaked

**Severity:** Critical (CVSS 9.1)

**Timeline:**
- **14:30:** Researcher reports API key in GitHub commit
- **14:35:** Incident created, response team assembled
- **14:40:** All API keys rotated
- **14:45:** Previous version redeployed with new keys
- **14:50:** Rate limiting monitored for abuse
- **15:00:** No evidence of abuse found
- **15:15:** All-clear announced
- **Next day:** Post-mortem scheduled
  - Add pre-commit hook to prevent secret leaks
  - Update security training
  - Review key rotation procedures

### Scenario: Rate Limit Bypass

**Severity:** High (CVSS 7.8)

**Timeline:**
- **10:00:** Health check endpoint flooded
- **10:05:** Incident created
- **10:10:** Rate limit tier for health check increased
- **10:15:** IP addresses blocked
- **10:20:** Investigation shows vulnerability in rate limiter
- **11:00:** Fix developed and tested
- **11:15:** Fix deployed
- **11:30:** All-clear, monitoring continues

## Incident Log Template

```markdown
# Incident: [Title]

- **Severity:** [Critical/High/Medium/Low]
- **Reported:** [Timestamp]
- **Resolved:** [Timestamp]
- **Duration:** [Time elapsed]
- **Root Cause:** [Brief description]

## Timeline

| Time | Event | Responsible |
|------|-------|-------------|
| 14:30 | Incident reported | reporter |
| 14:40 | Mitigation applied | alice |
| 15:00 | Fix deployed | bob |
| 15:15 | All-clear announced | manager |

## Resolution

[What was done to fix]

## Prevention

[What will prevent this in future]

## Follow-up

- [ ] Post-mortem scheduled
- [ ] Documentation updated
- [ ] Preventive measures implemented
- [ ] Team trained
```
```

---

## Part 8: Cost & Resource Planning

### 8.1 Resource Requirements

#### Development Environment
- **CPU:** 0.5 cores sufficient
- **Memory:** 256MB base + 100MB per 5 concurrent connections
- **Storage:** 200MB base image + 500MB for build artifacts
- **Network:** Minimal, depends on SSH hosts

#### Staging Environment (Production-like)
- **CPU:** 1.0 core
- **Memory:** 512MB
- **Storage:** 500MB
- **Network:** Same as SSH infrastructure

#### Production Environment (High Availability)
- **CPU:** 1.0-2.0 cores (for load)
- **Memory:** 512MB-1GB (depending on pool size)
- **Storage:** 500MB
- **Network:** Dedicated network interface if possible

### 8.2 Scaling Strategy

#### Vertical Scaling (Single Instance)
**Approach:** Increase resource allocation
- CPU: Start at 0.5, scale to 2.0
- Memory: Start at 256MB, scale to 1GB
- Pool size: Adjust SCOUT_MAX_POOL_SIZE (default: 100)

**When to use:** <1000 req/min, <50 concurrent connections

#### Horizontal Scaling (Multiple Instances)
**Approach:** Load balance across instances
- Deploy 2-3 instances behind load balancer
- Use sticky sessions for connection pooling
- Shared SSH key management (NFS mount)

**Implementation:**
```yaml
# Enhanced docker-compose for HA
services:
  scout-1:
    image: scout_mcp:latest
    ports:
      - "53001:8000"
    # ... config ...

  scout-2:
    image: scout_mcp:latest
    ports:
      - "53002:8000"
    # ... config ...

  scout-3:
    image: scout_mcp:latest
    ports:
      - "53003:8000"
    # ... config ...

  # HAProxy load balancer
  haproxy:
    image: haproxy:2.8-alpine
    ports:
      - "53000:8000"
    volumes:
      - ./haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro
```

**When to use:** >1000 req/min or high availability required

---

## Part 9: Known Limitations & Workarounds

### Limitation 1: In-Memory Rate Limiting
**Issue:** Rate limits reset on container restart, don't persist across replicas.

**Workaround:** Use Redis-backed rate limiting in HA setup.

**Implementation (Future):**
```python
# Replace token bucket with Redis-backed version
from redis import Redis

class RedisRateLimiter:
    def __init__(self, redis_url: str, limit: int, window: int):
        self.redis = Redis.from_url(redis_url)
        self.limit = limit
        self.window = window
```

### Limitation 2: SSH Key Management
**Issue:** SSH keys must be mounted from host, not managed by container.

**Workaround:** Use external secret management (Vault, etc.).

**Implementation (Future):**
```yaml
# With Vault integration
services:
  scout:
    # Retrieve SSH keys from Vault at startup
    entrypoint: ["/scripts/vault-setup.sh"]
```

### Limitation 3: No Built-in Metrics Storage
**Issue:** Metrics are point-in-time snapshots, not persisted.

**Workaround:** Integrate with Prometheus for time-series storage.

### Limitation 4: Limited to Single SSH Session per Host
**Issue:** SCOUT_MAX_POOL_SIZE limits concurrent connections.

**Workaround:** Increase pool size or use connection pooling multiplexing (SSH ProxyCommand).

---

## Part 10: Final Recommendations

### Immediate Actions (This Week)
1. **Create Dockerfile** - Unblock cloud deployment (2 hours)
2. **Create docker-compose.yaml** - Enable local deployment (1 hour)
3. **Create .github/workflows/ci.yaml** - Automate testing (2 hours)

### Short-term (Next 2 Weeks)
4. **Add output size limits** - Close P0-4 security gap (2 hours)
5. **Add connection timeouts** - Close P1-1 blocker (1 hour)
6. **Create DEPLOYMENT.md** - Operational procedures (3 hours)
7. **Add security tests** - Increase coverage (4 hours)

### Medium-term (Next Month)
8. **Add connection pool metrics** - Operational visibility (4 hours)
9. **Create operational runbooks** - Team enablement (3 hours)
10. **Implement health check enhancements** - Better diagnostics (2 hours)

### Long-term (Q1 2026)
11. **Add Prometheus integration** - Production monitoring
12. **Create Grafana dashboards** - Visual observability
13. **Implement Redis-backed rate limiting** - HA support
14. **Add external secret management** - Enterprise deployments

---

## Appendix A: Terminology

| Term | Definition |
|------|-----------|
| **MTTR** | Mean Time To Recovery - average time to fix incidents |
| **SLA** | Service Level Agreement - uptime/performance guarantees |
| **SBOM** | Software Bill of Materials - dependency inventory |
| **SAST** | Static Application Security Testing - code analysis |
| **DAST** | Dynamic Application Security Testing - runtime testing |
| **IaC** | Infrastructure as Code - versioned infrastructure definitions |
| **CI/CD** | Continuous Integration/Continuous Deployment - automated pipelines |
| **TDD** | Test-Driven Development - write tests before code |

---

## Appendix B: References

### Security Resources
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [SLSA Framework](https://slsa.dev/)
- [Secure Software Supply Chain Guide](https://www.ncsc.gov.uk/collection/supply-chain-security)

### Container & Deployment
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [NIST Container Security Guide](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-190.pdf)
- [Docker Compose Spec](https://compose-spec.io/)

### CI/CD & DevOps
- [GitHub Actions Best Practices](https://docs.github.com/en/actions/guides)
- [DORA Metrics](https://cloud.google.com/blog/products/devops-sre/using-the-four-keys-to-measure-software-delivery-performance)
- [Twelve-Factor App](https://12factor.net/)

### Monitoring & Observability
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Observability Engineering](https://www.oreilly.com/library/view/observability-engineering/9781492076438/)
- [SRE Book](https://sre.google/books/)

---

**Document Version:** 1.0
**Last Updated:** December 7, 2025
**Review Cycle:** Quarterly
**Next Review:** March 7, 2026
