# Scout MCP Middleware Flow Diagram

## Request/Response Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│ MCP Client (Claude Desktop / HTTP Client)                            │
└────────────────────────────────┬──────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ FastMCP Server (HTTP or STDIO Transport)                             │
│  - Handles MCP protocol (JSON-RPC)                                   │
│  - Routes to middleware stack                                        │
└────────────────────────────────┬──────────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  MIDDLEWARE STACK      │
                    │  (Onion Model)         │
                    └────────────────────────┘
                                 │
                                 ▼
         ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
         ┃  Layer 1: LoggingMiddleware                  ┃
         ┃  • Logs request with ">>> TOOL/RESOURCE"     ┃
         ┃  • Starts timer (time.perf_counter())        ┃
         ┃  • Formats arguments/URIs                    ┃
         ┗━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                           │
                           ▼
         ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
         ┃  Layer 2: ErrorHandlingMiddleware            ┃
         ┃  • Wraps execution in try/except             ┃
         ┃  • Tracks error statistics                   ┃
         ┃  • Calls error callback if set               ┃
         ┃  • Re-raises exceptions                      ┃
         ┗━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                           │
                           ▼
         ┌─────────────────────────────────────────────┐
         │  Handler (Tool / Resource / Prompt)         │
         │  • scout() tool                             │
         │  • scout_resource()                         │
         │  • list_hosts_resource()                    │
         │  • Dynamic host resources (tootie://, etc)  │
         └─────────────────────────────────────────────┘
                           │
                           ▼
         ┌─────────────────────────────────────────────┐
         │  Business Logic (services/)                 │
         │  • ConnectionPool.get_connection()          │
         │  • cat_file() / ls_dir() / run_command()    │
         │  • SSH command execution via asyncssh       │
         └─────────────────────────────────────────────┘
                           │
                           ▼
         ┌─────────────────────────────────────────────┐
         │  Remote SSH Host                            │
         │  • File system operations                   │
         │  • Command execution                        │
         │  • Docker/Compose/ZFS operations            │
         └─────────────────────────────────────────────┘
                           │
                           │ Response
                           ▼
         ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
         ┃  Layer 2: ErrorHandlingMiddleware            ┃
         ┃  • (Pass through on success)                 ┃
         ┃  • On error: log, track stats, re-raise      ┃
         ┗━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                           │
                           ▼
         ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
         ┃  Layer 1: LoggingMiddleware                  ┃
         ┃  • Calculate duration_ms                     ┃
         ┃  • Summarize result (chars, lines, items)    ┃
         ┃  • Log "<<< TOOL/RESOURCE" with timing       ┃
         ┃  • WARNING if duration > slow_threshold_ms   ┃
         ┗━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│ FastMCP Server Response                                              │
│  - Serializes to MCP protocol                                        │
│  - Returns to client                                                 │
└────────────────────────────────┬──────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ MCP Client                                                            │
└─────────────────────────────────────────────────────────────────────┘
```

## Logging Output Example

```
17:23:45.123 12/03 | INFO     | middleware.logging   | >>> TOOL: scout(target='tootie:/etc/hosts')
17:23:45.234 12/03 | INFO     | services.pool        | Reusing existing connection to tootie (pool_size=1)
17:23:45.345 12/03 | INFO     | middleware.logging   | <<< TOOL: scout -> 156 chars, 8 lines [221.4ms]

17:24:10.567 12/03 | INFO     | middleware.logging   | >>> RESOURCE: tootie://var/log/syslog
17:24:10.678 12/03 | WARNING  | middleware.logging   | <<< RESOURCE: tootie://var/log/syslog -> 45623 chars, 1234 lines [1523.8ms SLOW!]

17:24:30.890 12/03 | ERROR    | middleware.errors    | Error in tools/call: ValueError: Invalid path format
17:24:30.891 12/03 | ERROR    | middleware.logging   | !!! TOOL: scout -> ValueError: Invalid path format [2.1ms]
```

## Middleware Hook Mapping

```
MCP Method              Middleware Hook             Example Context Attributes
─────────────────────  ─────────────────────────  ───────────────────────────────
tools/call             on_call_tool()              message.name, message.arguments
resources/read         on_read_resource()          message.uri
prompts/get            on_get_prompt()             message.name, message.arguments
tools/list             on_list_tools()             (no message attributes)
resources/list         on_list_resources()         (no message attributes)
prompts/list           on_list_prompts()           (no message attributes)
<any other>            on_message()                method, source
<all methods>          on_request()                method, source (generic)
```

## Colorful Console Output

```
EST Timestamp  │ Level    │ Component            │ Message
──────────────────────────────────────────────────────────────────────
[dim gray]     │ [color]  │ [component-color]    │ [with highlighting]
14:23:45.123   │ INFO     │ server               │ >>> Starting Scout MCP...
14:23:45.234   │ INFO     │ server               │ Loaded 3 SSH host(s): tootie, nas, vault
14:23:45.345   │ DEBUG    │ services.pool        │ ConnectionPool initialized (idle_timeout=60s)
14:23:50.123   │ INFO     │ middleware.logging   │ >>> TOOL: scout(target='tootie:/etc')
14:23:50.234   │ INFO     │ services.pool        │ Opening SSH connection to tootie (root@192.168.1.100:22)
14:23:50.456   │ INFO     │ services.pool        │ SSH connection established to tootie (pool_size=1)
14:23:50.567   │ INFO     │ middleware.logging   | <<< TOOL: scout -> 2453 chars [443.5ms]
14:24:00.123   │ WARNING  │ middleware.logging   | <<< TOOL: scout -> 1234 chars [1234.5ms SLOW!]
14:24:10.456   │ ERROR    │ middleware.errors    | Error in tools/call: SSHException: Connection failed
14:24:10.457   │ ERROR    │ middleware.logging   | !!! TOOL: scout -> SSHException: Connection failed [333.2ms]

Legend:
  >>> = Request start
  <<< = Successful completion
  !!! = Error
  +   = Creating/opening
  -   = Closing/removing
  ~   = Reusing
  OK  = Success indicator (from MCPRequestFormatter)
```

## Environment Variable Impact

```
Variable                    Default    Impact on Middleware
──────────────────────────  ─────────  ─────────────────────────────────────
SCOUT_LOG_LEVEL             DEBUG      Filter level for all scout_mcp loggers
SCOUT_LOG_COLORS            true       Enable ANSI color codes in output
SCOUT_LOG_PAYLOADS          false      Include request/response payloads (DEBUG)
SCOUT_SLOW_THRESHOLD_MS     1000       Threshold for WARNING on slow requests
SCOUT_INCLUDE_TRACEBACK     false      Include full tracebacks in error logs

# Legacy (still supported):
MCP_CAT_MAX_FILE_SIZE       1048576    (config, not middleware)
MCP_CAT_COMMAND_TIMEOUT     30         (config, not middleware)
MCP_CAT_IDLE_TIMEOUT        60         (config, not middleware)
```

## Middleware State and Statistics

```python
# Error statistics (ErrorHandlingMiddleware)
error_middleware.get_error_stats()
# → {"ValueError": 3, "SSHException": 1, "TimeoutError": 2}

error_middleware.reset_stats()
# → Clears all counters

# Timing statistics (DetailedTimingMiddleware - not currently used)
timing_middleware.get_timing_stats()
# → {
#     "tool:scout": {"count": 45, "total_ms": 12345.6, "avg_ms": 274.3, "min_ms": 12.1, "max_ms": 1523.8},
#     "resource:tootie://etc": {"count": 12, "total_ms": 3456.7, ...}
#   }

timing_middleware.reset_stats()
# → Clears all timing data
```

## Testing Patterns

```python
# Mock middleware context for testing
context = MagicMock()
context.method = "tools/call"
context.message = MagicMock()
context.message.name = "scout"
context.message.arguments = {"target": "tootie:/etc/hosts"}

# Mock call_next handler
call_next = AsyncMock(return_value="result")

# Test middleware
middleware = LoggingMiddleware(logger=mock_logger)
result = await middleware.on_call_tool(context, call_next)

# Verify logging
assert mock_logger.info.call_count >= 1
all_calls = str(mock_logger.info.call_args_list)
assert ">>> TOOL" in all_calls
```
