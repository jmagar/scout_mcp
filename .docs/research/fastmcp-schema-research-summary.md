# FastMCP Schema Research Summary

**Date:** 2025-12-07
**Research Question:** Do tools returning `list[dict[str, Any]] | str` need custom output schemas?

## Answer: NO

FastMCP automatically generates schemas from type hints. No `output_schema` parameter needed.

## Key Findings

### 1. Auto-Generation Works

From [FastMCP documentation](https://gofastmcp.com/servers/tools):

> FastMCP's schema generation works for most common types including basic types, collections, **union types**, Pydantic models, TypedDict structures, and dataclasses.

### 2. Union Type Support

Union types generate `anyOf` schemas automatically:

```python
# Type hint
-> list[dict[str, Any]] | str

# Generated JSON Schema
{
  "anyOf": [
    {"type": "array", "items": {"type": "object"}},
    {"type": "string"}
  ]
}
```

### 3. UIResource is a Pydantic Model (Serializes to dict)

From source inspection:

```python
# mcp_ui_server.core.UIResource inherits from EmbeddedResource
class UIResource(EmbeddedResource):
    """Represents a UI resource that can be included in tool results."""

class EmbeddedResource(BaseModel):
    type: Literal["resource"]
    resource: TextResourceContents | BlobResourceContents
    annotations: Annotations | None = None
    meta: dict[str, Any] | None = None
```

**Important:** `create_ui_resource()` returns a `UIResource` Pydantic model instance, NOT a raw dict.

However, Pydantic models:
- Are recognized by FastMCP as structured content (object-like)
- Auto-serialize to dict via `model_dump()` for the MCP protocol
- Generate schemas automatically from model definition
- Work seamlessly with FastMCP's type system

**Practical implications:**
- You can return `list[UIResource]` (type-accurate)
- Or use `list[dict[str, Any]]` (works because UIResource serializes to dict)
- FastMCP handles both correctly
- The union `list[dict[str, Any]] | str` works perfectly

### 4. When to Use output_schema

**Use manual schema ONLY when:**
- ✅ You need field-level validation (min/max, patterns, required fields)
- ✅ Auto-generated schema is incorrect (rare bug)
- ✅ You want to disable structured output: `structured_output=False`

**Don't use manual schema when:**
- ❌ Type hints are sufficient (most cases)
- ❌ Simple union types (`str | dict`, `list[dict] | str`)
- ❌ Pydantic models already define schema

## Verified Patterns

### Pattern 1: scout_mcp (Current)

```python
async def scout(...) -> list[dict[str, Any]] | str:
    """Returns UI or plain text."""
    # UI path
    ui = create_ui_resource({...})
    return [ui]  # list[dict]

    # Text path
    return "Error message"  # str
```

**Status:** ✅ Works correctly without `output_schema`

### Pattern 2: Pydantic Models (Recommended)

```python
from pydantic import BaseModel

class UIResponse(BaseModel):
    uri: str
    content: dict

async def better_scout(...) -> list[UIResponse] | str:
    """Type-safe with Pydantic."""
    return [UIResponse(uri="...", content={...})]
```

**Status:** ✅ Better type safety, still no manual schema needed

## Known Issues

### Issue #2153: Nested Union Types

**Problem:** Deeply nested Pydantic models with union fields may fail:

```python
# This can break
class Result(BaseModel):
    metric: NumericType | StringType  # Union in nested model

# Error: PointerToNowhere: '/$defs/NumericType' does not exist
```

**Workaround:** Flatten schema or use simpler types

**Does NOT affect:** `list[dict[str, Any]] | str` (no nested models)

### Issue #1969: List ContentBlock Conversion

**Problem:** Lists of non-ContentBlock types may stringify instead of converting individually.

**Status:** Fixed in PR #1970

**Does NOT affect:** UIResource (properly inherits from EmbeddedResource/ContentBlock)

## Recommendations

### For scout_mcp

**Current implementation is optimal:**

```python
async def scout(...) -> list[dict[str, Any]] | str:
    """No changes needed."""
    pass
```

**Why:**
1. ✅ Type hint generates correct schema
2. ✅ Union handled automatically
3. ✅ No nested model issues
4. ✅ UIResource works as dict
5. ✅ Pydantic validates both paths

### Future Improvements (Optional)

**If you want stronger typing:**

```python
from typing import TypeAlias
from mcp.types import EmbeddedResource

# Type alias for clarity
UIResourceList: TypeAlias = list[dict[str, Any]]

async def scout(...) -> UIResourceList | str:
    """Clearer intent, same behavior."""
    pass
```

**Or use Pydantic:**

```python
from pydantic import BaseModel

class ScoutUIResponse(BaseModel):
    """Scout UI response model."""
    uri: str
    content: dict
    encoding: str = "text"

async def scout(...) -> list[ScoutUIResponse] | str:
    """Full type safety."""
    pass
```

## Testing Checklist

- [x] Verified FastMCP supports union types
- [x] Verified UIResource is dict-compatible
- [x] Checked for known issues affecting union types
- [x] Found no issues with `list[dict] | str` pattern
- [x] Confirmed no `output_schema` parameter needed

## Documentation Links

### Official Docs
- [FastMCP Tools](https://gofastmcp.com/servers/tools)
- [MCP-UI Server Walkthrough](https://mcpui.dev/guide/server/python/walkthrough)
- [MCP-UI Usage Examples](https://mcpui.dev/guide/server/python/usage-examples)

### GitHub Issues
- [#2153 - anyOf Schema Conversion](https://github.com/jlowin/fastmcp/issues/2153)
- [#1969 - List ContentBlock Conversion](https://github.com/jlowin/fastmcp/issues/1969)

### Guides
- [Building MCP Servers with FastMCP](https://mcpcat.io/guides/building-mcp-server-python-fastmcp/)
- [FastMCP Tutorial on DataCamp](https://www.datacamp.com/tutorial/building-mcp-server-client-fastmcp)

## Conclusion

**Question:** Do I need `output_schema` for `list[dict[str, Any]] | str`?

**Answer:** **NO**

**Reason:** FastMCP automatically generates correct schemas from type hints, including union types.

**Action:** None required. Current implementation is correct.

---

**Files Created:**
1. `/mnt/cache/code/scout_mcp/.docs/research/fastmcp-union-type-schemas.md` - Detailed research
2. `/mnt/cache/code/scout_mcp/.docs/research/fastmcp-union-types-examples.md` - Code examples
3. `/mnt/cache/code/scout_mcp/.docs/research/fastmcp-schema-research-summary.md` - This summary
