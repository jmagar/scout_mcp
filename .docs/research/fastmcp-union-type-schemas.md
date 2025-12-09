# FastMCP Tool Schema Requirements for Union Return Types

**Research Date:** 2025-12-07
**Focus:** Understanding FastMCP's schema generation for tools returning `list[dict[str, Any]] | str`

## Executive Summary

FastMCP **automatically generates output schemas** from Python type hints using Pydantic. Union types like `list[dict[str, Any]] | str` are supported, but there are important nuances:

1. **Auto-generation works**: FastMCP supports union types, including complex ones
2. **No explicit schema needed**: Type hints alone are sufficient for most cases
3. **Manual override available**: Use `output_schema` parameter when needed
4. **UIResource pattern**: `list[UIResource] | str` requires special handling due to ContentBlock conversion

## Key Findings

### 1. Automatic Schema Generation

FastMCP uses Pydantic to automatically generate JSON schemas from type annotations. According to the [official documentation](https://gofastmcp.com/servers/tools):

> FastMCP's schema generation works for most common types including basic types, collections, **union types**, Pydantic models, TypedDict structures, and dataclasses.

**Supported types include:**
- Primitives: `int`, `str`, `float`, `bool`
- Collections: `list`, `dict`, `set`
- Union types: `str | int`, `Union[str, int]`
- Optional: `str | None`
- Pydantic models and dataclasses

### 2. How Output Schemas Work

When you add return type annotations, FastMCP:
1. Inspects the function signature
2. Generates a JSON schema using Pydantic
3. Validates structured results against this schema
4. Serializes data for the MCP protocol

**Key principle from [FastMCP Tools documentation](https://gofastmcp.com/servers/tools):**
> When you add return type annotations to functions, FastMCP automatically generates JSON schemas that validate structured data.

### 3. Structured Output Rules

According to the [FastMCP documentation](https://gofastmcp.com/servers/tools):

**Object-like results** (dict, Pydantic models, dataclasses):
- **Always** become structured content (even without output schema)
- Automatically validated against generated schema

**Non-object results** (int, str, list):
- Only become structured content **if there's an output schema**
- Otherwise, returned as plain text content

**Primitive wrapping:**
For primitives like `int` or `str`, FastMCP wraps them under a `"result"` key:

```python
@mcp.tool
def calculate_sum(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b
# Returns: {"result": 42}
```

### 4. Manual Schema Override

You can override auto-generated schemas with the `output_schema` parameter:

```python
@mcp.tool(output_schema={
    "type": "object",
    "properties": {
        "data": {"type": "string"},
        "metadata": {"type": "object"}
    }
})
def custom_schema_tool() -> dict:
    """Tool with custom output schema."""
    return {"data": "Hello", "metadata": {"version": "1.0"}}
```

**Important constraint:** Output schemas must be object types (`"type": "object"`).

### 5. Union Type Support

FastMCP supports union types in both input and output schemas. From [MCPcat guide](https://mcpcat.io/guides/building-mcp-server-python-fastmcp/):

> FastMCP supports all Pydantic-compatible types including primitives, collections, dates, UUIDs, and enums.

**Example with union:**
```python
@mcp.tool
def flexible_output(mode: str) -> dict | str:
    """Return dict or string based on mode."""
    if mode == "structured":
        return {"result": "data"}
    return "plain text result"
```

### 6. Known Issue: anyOf Schema Handling

There is a known issue ([#2153](https://github.com/jlowin/fastmcp/issues/2153)) with nested Pydantic models using union types:

**Problem:** When a Pydantic model has a field with a union type (e.g., `metric: NumericType | StringType`), the generated schema may incorrectly handle `$defs` references in `anyOf` constructs.

**Error:** `PointerToNowhere: '/$defs/NumericType' does not exist`

**Workaround:** Simplify output schema structure or avoid deeply nested union types with custom Pydantic models.

### 7. List Return Type Handling

FastMCP has special handling for list return types ([Issue #1969](https://github.com/jlowin/fastmcp/issues/1969)):

**Problem:** Lists of special types (File, Image, Audio, UIResource) may not convert properly if the items aren't recognized as ContentBlocks.

**How it works:**
1. **All items are ContentBlocks** → return as-is
2. **Some items are ContentBlocks** → convert individually
3. **No items are ContentBlocks** → serialize entire list as single text

**Fixed in PR #1970:** Improved handling of FastMCP helper types within list contexts.

## UIResource Pattern

### Type Hierarchy

```python
# From mcp.types
class EmbeddedResource(BaseModel):
    type: Literal["resource"]
    resource: TextResourceContents | BlobResourceContents
    annotations: Annotations | None = None
    meta: dict[str, Any] | None = None

# From mcp_ui_server.core
class UIResource(EmbeddedResource):
    """Represents a UI resource that can be included in tool results."""
    def __init__(self, resource: TextResourceContents | BlobResourceContents, **kwargs):
        super().__init__(type="resource", resource=resource, **kwargs)
```

### Usage Pattern

From [MCP-UI documentation](https://mcpui.dev/guide/server/python/usage-examples):

```python
from mcp.server.fastmcp import FastMCP
from mcp_ui_server import create_ui_resource
from mcp_ui_server.core import UIResource

mcp = FastMCP("my-mcp-server")

@mcp.tool()
def greet() -> list[UIResource]:
    """A simple greeting tool that returns a UI resource."""
    ui_resource = create_ui_resource({
        "uri": "ui://greeting/simple",
        "content": {
            "type": "rawHtml",
            "htmlString": "<h1>Hello from Python MCP Server!</h1>"
        },
        "encoding": "text"
    })
    return [ui_resource]
```

**Key points:**
- Return type is `list[UIResource]`, not `UIResource`
- `create_ui_resource()` returns a single UIResource
- Wrap in list: `return [ui_resource]`

### Union Return Type: `list[UIResource] | str`

For the scout tool pattern returning either UI or plain text:

```python
async def scout(...) -> list[dict[str, Any]] | str:
    """Scout remote files and directories via SSH.

    Returns:
        UIResource list with interactive UI for files/directories, or
        plain string for commands, diffs, searches, and other operations.
    """
    # Return UI for files/directories
    ui_resource = create_ui_resource({...})
    return [ui_resource]

    # OR return plain text for errors/commands
    return "Error: Unknown host"
```

**Schema generation:**
- FastMCP will generate a union schema: `anyOf[array, string]`
- No manual `output_schema` needed
- Pydantic handles validation automatically

## Recommendations

### For scout_mcp Tool

**Current implementation:** `list[dict[str, Any]] | str`

**Works because:**
1. FastMCP auto-generates schema from union type
2. `dict` objects become structured content automatically
3. `str` results become plain text content
4. No manual schema override needed

**Best practice:**
```python
from typing import Any

async def scout(...) -> list[dict[str, Any]] | str:
    """Tool with union return type."""
    # Return structured UI
    ui_resource = create_ui_resource({...})
    return [ui_resource]  # dict becomes structured content

    # OR return plain text
    return "Error message"  # str becomes text content
```

### When to Use output_schema Parameter

**Use manual override when:**
1. You need strict validation beyond Pydantic defaults
2. The auto-generated schema is incorrect
3. You want to suppress structured output: `structured_output=False`
4. Complex nested unions with custom Pydantic models (workaround for #2153)

**Don't use manual override when:**
1. Simple union types work fine with auto-generation
2. Pydantic models already define the schema
3. Return type is straightforward (`dict`, `str`, `list[dict]`)

## Pydantic Union Type Behavior

From [Pydantic documentation](https://docs.pydantic.dev/1.10/usage/schema/):

- Pydantic generates `anyOf` for Union types in JSON Schema
- `anyOf` means "valid against at least one schema"
- `oneOf` means "valid against exactly one schema" (not used by Pydantic)

**Example schema for `list[dict[str, Any]] | str`:**
```json
{
  "anyOf": [
    {
      "type": "array",
      "items": {
        "type": "object"
      }
    },
    {
      "type": "string"
    }
  ]
}
```

## Testing Recommendations

### Verify Schema Generation

```python
import inspect
from fastmcp import FastMCP

mcp = FastMCP("test")

@mcp.tool()
async def my_tool() -> list[dict[str, Any]] | str:
    return [{"key": "value"}]

# Inspect generated schema
print(inspect.signature(my_tool))
```

### Test Both Return Paths

```python
import pytest

@pytest.mark.asyncio
async def test_tool_returns_list():
    result = await my_tool(mode="ui")
    assert isinstance(result, list)
    assert isinstance(result[0], dict)

@pytest.mark.asyncio
async def test_tool_returns_string():
    result = await my_tool(mode="error")
    assert isinstance(result, str)
```

## References

### Documentation
- [FastMCP Tools Documentation](https://gofastmcp.com/servers/tools)
- [FastMCP Python SDK](https://github.com/jlowin/fastmcp)
- [MCP-UI Server Walkthrough](https://mcpui.dev/guide/server/python/walkthrough)
- [MCP-UI Usage Examples](https://mcpui.dev/guide/server/python/usage-examples)
- [Pydantic Schema Generation](https://docs.pydantic.dev/1.10/usage/schema/)

### GitHub Issues
- [#2153: Incorrect conversion of OpenAPI schema into MCP tool schema](https://github.com/jlowin/fastmcp/issues/2153)
- [#1969: Convert FastMCP Types to String if no ContentBlock in List Return Type](https://github.com/jlowin/fastmcp/issues/1969)
- [#323: No way to declare input schema for tools using Fast MCP](https://github.com/modelcontextprotocol/python-sdk/issues/323)

### Related Resources
- [Building MCP Server with FastMCP - Complete Guide](https://mcpcat.io/guides/building-mcp-server-python-fastmcp/)
- [Add Custom Tools to Python MCP Servers](https://mcpcat.io/guides/adding-custom-tools-mcp-server-python/)
- [Building MCP Server and Client with FastMCP 2.0](https://www.datacamp.com/tutorial/building-mcp-server-client-fastmcp)

## Conclusion

**Key Takeaway:** FastMCP automatically handles union return types like `list[dict[str, Any]] | str` through Pydantic's schema generation. No manual `output_schema` parameter is needed for the scout tool.

**Why it works:**
1. ✅ FastMCP supports union types natively
2. ✅ Pydantic generates `anyOf` schemas automatically
3. ✅ `dict` objects become structured content
4. ✅ `str` results become text content
5. ✅ No special decorators or parameters required

**What doesn't work:**
1. ❌ Deeply nested Pydantic models with union types (Issue #2153)
2. ❌ Lists of non-ContentBlock custom types without proper conversion (Issue #1969)

**Recommendation for scout_mcp:**
Continue using `-> list[dict[str, Any]] | str` with no `output_schema` parameter. FastMCP will handle it correctly.
