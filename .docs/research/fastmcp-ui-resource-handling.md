# FastMCP UIResource Handling Research

**Date:** 2025-12-07
**Status:** SOLVED

## Problem

Resource handler returns `dict[str, Any]` from `create_ui_resource().model_dump()`, but FastMCP serializes it to JSON string in the `text` field instead of proper UIResource structure.

**Current Response:**
```json
{
  "uri": "squirts://syslog",
  "mimeType": "text/html",
  "text": "{\"type\":\"resource\",\"resource\":{\"uri\":\"ui://scout-logs/squirts/var/log/syslog\",\"mimeType\":\"text/html\",\"text\":\"...\"}}"
}
```

**Expected Response:**
Either:
1. Just HTML in `text` field, OR
2. UIResource structure properly passed through

---

## FastMCP Resource Handler Flow

### 1. Resource Function Return Types

From `/mcp/server/lowlevel/server.py:314`:
```python
def read_resource(self):
    def decorator(
        func: Callable[[AnyUrl], Awaitable[str | bytes | Iterable[ReadResourceContents]]],
    ):
```

**Accepted return types:**
- `str` - Deprecated, converted to TextResourceContents
- `bytes` - Deprecated, converted to BlobResourceContents
- `Iterable[ReadResourceContents]` - **Preferred**

### 2. Return Processing

From `/mcp/server/lowlevel/server.py:338-363`:
```python
match result:
    case str() | bytes() as data:
        warnings.warn(
            "Returning str or bytes from read_resource is deprecated. "
            "Use Iterable[ReadResourceContents] instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        content = create_content(data, None)
    case Iterable() as contents:
        contents_list = [
            create_content(content_item.content, content_item.mime_type)
            for content_item in contents
        ]
        return types.ServerResult(
            types.ReadResourceResult(contents=contents_list)
        )
```

**Key insight:** If return value is `Iterable`, it extracts `.content` and `.mime_type` from each item!

### 3. FastMCP FunctionResource.read()

From `/fastmcp/resources/resource.py:205-224`:
```python
async def read(self) -> str | bytes:
    """Read the resource by calling the wrapped function."""
    # ... context injection ...

    result = self.fn(**kwargs)
    if inspect.isawaitable(result):
        result = await result

    if isinstance(result, Resource):
        return await result.read()
    elif isinstance(result, bytes | str):
        return result
    else:
        # THIS IS THE PROBLEM!
        return pydantic_core.to_json(result, fallback=str).decode()
```

**The issue:** When resource handler returns a `dict` (from `.model_dump()`), FastMCP's `FunctionResource.read()` calls `pydantic_core.to_json()` and converts it to a JSON string!

---

## Root Cause

1. `create_ui_resource()` returns a UIResource object (likely a Pydantic model)
2. We call `.model_dump()` to convert to dict
3. FastMCP's `FunctionResource.read()` sees a dict (not str/bytes/Resource)
4. It calls `pydantic_core.to_json(result)` → JSON string
5. JSON string becomes the `text` field value

**The dict gets double-serialized!**

---

## Solutions

### Option 1: Return HTML String Directly (RECOMMENDED)

**Rationale:** MCP resources are meant to return text or binary content. UIResource is a tool/prompt concept, not a resource concept.

```python
async def syslog_resource(host: str, lines: int = 100) -> str:
    """Show system logs with log viewer HTML."""
    # ... get logs ...

    # Generate HTML directly
    from scout_mcp.ui.templates import get_log_viewer_html
    html = get_log_viewer_html(host, f"/var/log/syslog", logs)

    return html  # Just return the HTML string!
```

**Resource registration:**
```python
@mcp.resource(
    "squirts://syslog",
    mime_type="text/html"  # This tells client it's HTML
)
```

**Pros:**
- Simple and direct
- Follows MCP resource pattern
- No dependency on mcp-ui-server
- Works with FastMCP's expected types

**Cons:**
- No structured UIResource metadata

### Option 2: Return UIResource Object (NOT dict)

If `create_ui_resource()` returns a Pydantic model with `.text` attribute:

```python
async def syslog_resource(host: str, lines: int = 100) -> str:
    """Show system logs with log viewer HTML."""
    # ... get logs ...

    ui_resource = create_ui_resource({
        "uri": f"ui://scout-logs/{host}/var/log/syslog",
        "content": {"type": "rawHtml", "htmlString": html},
        "encoding": "text",
    })

    # Return the HTML text from the UIResource
    return ui_resource.text  # Not .model_dump()!
```

**Pros:**
- Still uses mcp-ui-server utilities
- Returns proper text content

**Cons:**
- Loses UIResource structure
- Extra step for same result as Option 1

### Option 3: Use ReadResourceContents (ADVANCED)

Return proper MCP types (requires mcp-ui-server not installed):

```python
from mcp.types import TextResourceContents

async def syslog_resource(host: str, lines: int = 100) -> list[TextResourceContents]:
    """Show system logs with log viewer HTML."""
    # ... get logs ...

    html = get_log_viewer_html(host, f"/var/log/syslog", logs)

    return [
        TextResourceContents(
            uri=f"ui://scout-logs/{host}/var/log/syslog",
            text=html,
            mimeType="text/html"
        )
    ]
```

**Pros:**
- Uses MCP protocol types correctly
- Full control over response structure

**Cons:**
- More verbose
- No benefit over Option 1

---

## Recommendation

**Use Option 1: Return HTML String Directly**

### Implementation

1. **Remove mcp-ui-server dependency:**
```bash
uv remove mcp-ui-server
```

2. **Update resource handlers:**
```python
async def syslog_resource(host: str, lines: int = 100) -> str:
    """Show system logs with interactive log viewer UI."""
    # ... connection code ...
    logs, source = await syslog_read(conn, lines=lines)

    # Return HTML directly
    from scout_mcp.ui.templates import get_log_viewer_html
    return get_log_viewer_html(host, f"/var/log/syslog", logs)
```

3. **Ensure mime_type is set:**
```python
@mcp.resource(
    "squirts://syslog",
    mime_type="text/html"  # Critical!
)
async def syslog_resource(host: str, lines: int = 100) -> str:
    # ...
```

4. **Update ui/generators.py:**
```python
# Before:
async def create_log_viewer_ui(host: str, path: str, content: str) -> dict[str, Any]:
    html = get_log_viewer_html(host, path, content)
    ui_resource = create_ui_resource({...})
    return ui_resource.model_dump()

# After:
async def create_log_viewer_ui(host: str, path: str, content: str) -> str:
    """Create log viewer HTML."""
    return get_log_viewer_html(host, path, content)
```

### Verification

Test with Claude Code MCP inspector:
```bash
# List resources
mcp call resources/list

# Read HTML resource
mcp call resources/read --uri "squirts://syslog"
```

**Expected response:**
```json
{
  "contents": [
    {
      "uri": "squirts://syslog",
      "mimeType": "text/html",
      "text": "<html>...</html>"
    }
  ]
}
```

---

## Key Takeaways

1. **FastMCP resources expect `str | bytes` returns** - not dicts
2. **UIResource is for tool results, not resources** - resources are simpler
3. **mime_type decorator param is critical** - tells client how to render
4. **mcp-ui-server not needed** - we generate HTML directly
5. **Simpler is better** - return HTML string, let FastMCP handle MCP protocol

---

## Related Files

- `/scout_mcp/resources/syslog.py` - Current implementation
- `/scout_mcp/ui/generators.py` - UI generation utilities
- `/scout_mcp/ui/templates.py` - HTML templates
- `/.venv/lib/python3.12/site-packages/mcp/server/lowlevel/server.py` - MCP protocol handler
- `/.venv/lib/python3.12/site-packages/fastmcp/resources/resource.py` - FastMCP resource wrapper
