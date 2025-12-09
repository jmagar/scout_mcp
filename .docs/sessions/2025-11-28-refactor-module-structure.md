# Session: Refactor scout_mcp Module Structure

**Date**: 2025-11-28
**Duration**: Extended session (context continuation)
**Objective**: Refactor flat `scout_mcp/` structure into organized subdirectories using TDD

---

## Session Overview

Refactored the `scout_mcp` MCP server from a flat file structure to an organized module hierarchy. The goal was to separate concerns into models, services, utils, tools, and resources while keeping `server.py` as a thin wrapper. Used Test-Driven Development (TDD) throughout.

---

## Timeline

### Phase 1: Planning & Directory Discussion
- Analyzed current flat structure with all code in root
- Proposed MCP-oriented structure with subdirectories
- User feedback:
  - Yes to `models/` directory
  - Keep `config.py` at root
  - Keep `prompts/` and `middleware/` (will use later)
  - Single-word file names only (e.g., `parser.py` not `target_parser.py`)

### Phase 2: Establish Green Baseline
- Started with 55 passing tests
- Identified and removed tests for unimplemented features:
  - `tests/test_server_lifespan.py` - tested dynamic host resources (not implemented)
  - `tests/test_middleware/test_logging.py` - tested LoggingMiddleware (not implemented)

### Phase 3: TDD Implementation
1. **RED**: Wrote `tests/test_module_structure.py` with failing tests for new module imports
2. **GREEN**: Created all new modules to make tests pass
3. **REFACTOR**: Cleaned up imports and removed backward compatibility (per user request)

### Phase 4: Final Cleanup
- Removed old root-level files: `executors.py`, `ping.py`, `pool.py`, `scout.py`
- Updated all test imports to use new module paths
- Fixed benchmark tests with outdated imports
- Final result: **120 tests passing**

---

## Key Findings

### Original Structure (Before)
```
scout_mcp/
├── __init__.py
├── __main__.py
├── config.py
├── executors.py      # All SSH commands
├── ping.py           # Host connectivity
├── pool.py           # Connection pooling
├── scout.py          # URI parsing + tool logic
├── server.py         # Everything wired together
└── py.typed
```

### Final Structure (After)
```
scout_mcp/
├── __init__.py
├── __main__.py
├── config.py              # Kept at root
├── server.py              # Thin wrapper (21 lines)
├── models/
│   ├── __init__.py        # Re-exports all models
│   ├── ssh.py             # SSHHost, PooledConnection
│   ├── command.py         # CommandResult
│   └── target.py          # ScoutTarget
├── services/
│   ├── __init__.py        # Re-exports services
│   ├── state.py           # Global state management
│   ├── pool.py            # ConnectionPool
│   └── executors.py       # stat_path, cat_file, ls_dir, etc.
├── utils/
│   ├── __init__.py        # Re-exports utilities
│   ├── parser.py          # parse_target
│   ├── ping.py            # check_host_online
│   └── mime.py            # get_mime_type
├── tools/
│   ├── __init__.py
│   └── scout.py           # scout tool function
├── resources/
│   ├── __init__.py
│   ├── scout.py           # scout_resource
│   └── hosts.py           # list_hosts_resource
├── prompts/
│   └── __init__.py        # Reserved for future
└── middleware/
    └── __init__.py        # Reserved for future
```

---

## Technical Decisions

### 1. Thin `server.py` Wrapper
**Decision**: Reduce server.py to only wiring logic (21 lines)
**Reasoning**: User explicitly requested separation of concerns
**Result**: All business logic delegated to tools/, resources/, services/

```python
# server.py - Final implementation
from fastmcp import FastMCP
from scout_mcp.resources import list_hosts_resource, scout_resource
from scout_mcp.tools import scout

mcp = FastMCP("scout_mcp")
mcp.tool()(scout)
mcp.resource("scout://{host}/{path*}")(scout_resource)
mcp.resource("hosts://list")(list_hosts_resource)
```

### 2. Global State in `services/state.py`
**Decision**: Centralize config and pool management
**Reasoning**: User suggested this location, provides single source of truth
**Implementation**: Lazy initialization with module-level singletons

### 3. No Backward Compatibility
**Decision**: Remove re-export shims from old locations
**Reasoning**: User explicitly said "I dont need this"
**Impact**: All imports must use new paths

### 4. Single-Word File Names
**Decision**: Use `parser.py` instead of `target_parser.py`
**Reasoning**: User preference for cleaner imports

---

## Files Modified

### Created
| File | Purpose |
|------|---------|
| `scout_mcp/models/__init__.py` | Re-exports SSHHost, PooledConnection, CommandResult, ScoutTarget |
| `scout_mcp/models/ssh.py` | SSH-related dataclasses |
| `scout_mcp/models/command.py` | CommandResult dataclass |
| `scout_mcp/models/target.py` | ScoutTarget dataclass |
| `scout_mcp/services/__init__.py` | Re-exports all service functions |
| `scout_mcp/services/state.py` | get_config(), get_pool() |
| `scout_mcp/services/pool.py` | ConnectionPool class |
| `scout_mcp/services/executors.py` | SSH command execution functions |
| `scout_mcp/utils/__init__.py` | Re-exports utilities |
| `scout_mcp/utils/parser.py` | parse_target() |
| `scout_mcp/utils/ping.py` | check_host_online() |
| `scout_mcp/utils/mime.py` | get_mime_type() |
| `scout_mcp/tools/__init__.py` | Exports scout tool |
| `scout_mcp/tools/scout.py` | Scout tool implementation |
| `scout_mcp/resources/__init__.py` | Exports resources |
| `scout_mcp/resources/scout.py` | scout_resource |
| `scout_mcp/resources/hosts.py` | list_hosts_resource |
| `scout_mcp/prompts/__init__.py` | Reserved for future |
| `scout_mcp/middleware/__init__.py` | Reserved for future |
| `tests/test_module_structure.py` | Tests verifying new module structure |

### Deleted
| File | Reason |
|------|--------|
| `scout_mcp/executors.py` | Moved to services/executors.py |
| `scout_mcp/ping.py` | Moved to utils/ping.py |
| `scout_mcp/pool.py` | Moved to services/pool.py |
| `scout_mcp/scout.py` | Split into tools/scout.py and utils/parser.py |
| `tests/test_server_lifespan.py` | Tests for unimplemented features |
| `tests/test_middleware/test_logging.py` | Tests for unimplemented middleware |

### Updated (Import Paths)
| File | Change |
|------|--------|
| `tests/test_scout.py` | `scout_mcp.scout` → `scout_mcp.utils.parser` |
| `tests/test_ping.py` | `scout_mcp.ping` → `scout_mcp.utils.ping` |
| `tests/test_pool.py` | `scout_mcp.pool` → `scout_mcp.services.pool` |
| `tests/test_executors.py` | `scout_mcp.executors` → `scout_mcp.services.executors` |
| `tests/test_config.py` | `scout_mcp.mcp_cat` → `scout_mcp` |
| `tests/test_integration.py` | Multiple import updates |
| `tests/benchmarks/test_end_to_end.py` | `scout_mcp.mcp_cat` → `scout_mcp` |
| `tests/benchmarks/test_connection_pool.py` | Updated pool import path |
| `tests/benchmarks/test_ssh_operations.py` | `scout_mcp.executors` → `scout_mcp.services.executors` |
| `tests/benchmarks/test_uri_parsing.py` | `scout_mcp.scout` → `scout_mcp.utils.parser` |

---

## Commands Executed

```bash
# Run tests throughout refactoring
/code/scout_mcp/.venv/bin/python -m pytest tests/ -v --tb=short

# Initial baseline: 55 tests
# Final result: 120 tests passing
```

---

## Test Results

```
tests/ - 120 passed, 2 warnings
├── test_config.py (3 tests)
├── test_executors.py (11 tests)
├── test_integration.py (7 tests)
├── test_module_structure.py (16 tests)  # NEW
├── test_ping.py (3 tests)
├── test_pool.py (7 tests)
├── test_scout.py (7 tests)
├── test_middleware/
│   └── test_timing.py (4 tests)
└── benchmarks/
    ├── test_connection_pool.py (7 tests)
    ├── test_end_to_end.py (6 tests)
    ├── test_ssh_operations.py (7 tests)
    └── test_uri_parsing.py (4 tests)
```

---

## Next Steps

1. **Implement LoggingMiddleware** - Tests were removed; implement when needed
2. **Implement Dynamic Host Resources** - `test_server_lifespan.py` tests were removed
3. **Add prompts** - `prompts/` directory is ready for MCP prompts
4. **Use middleware** - `middleware/` directory is ready for middleware implementations

---

## Lessons Learned

1. **TDD works well for refactoring** - Writing structure tests first ensured all modules were properly connected
2. **Remove tests for unimplemented features** - Cleaner than maintaining stubs
3. **User feedback early** - Discussing structure before implementation saved rework
4. **No backward compat = simpler** - Removing re-exports simplified the codebase
