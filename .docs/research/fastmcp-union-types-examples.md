# FastMCP Union Type Return Examples

**Quick Reference:** Concrete examples of FastMCP tools returning union types

## TL;DR

**Question:** Do I need `output_schema` for `list[dict[str, Any]] | str`?

**Answer:** **NO**. FastMCP auto-generates schemas from type hints. Union types are fully supported.

## Example 1: Basic Union Type (str | dict)

```python
from fastmcp import FastMCP

mcp = FastMCP("example")

@mcp.tool()
def flexible_response(mode: str) -> str | dict:
    """Return string or dict based on mode."""
    if mode == "error":
        return "An error occurred"
    return {"status": "success", "data": [1, 2, 3]}
```

**Generated schema:**
```json
{
  "anyOf": [
    {"type": "string"},
    {"type": "object"}
  ]
}
```

**No `output_schema` parameter needed.**

## Example 2: List Union Type (list[dict] | str)

```python
from typing import Any
from fastmcp import FastMCP

mcp = FastMCP("search-tool")

@mcp.tool()
def search_items(query: str) -> list[dict[str, Any]] | str:
    """Search items, return results or error message."""
    if not query:
        return "Error: Query cannot be empty"

    results = [
        {"id": 1, "title": "Item 1", "score": 0.95},
        {"id": 2, "title": "Item 2", "score": 0.87},
    ]
    return results
```

**Generated schema:**
```json
{
  "anyOf": [
    {
      "type": "array",
      "items": {"type": "object"}
    },
    {"type": "string"}
  ]
}
```

**No `output_schema` parameter needed.**

## Example 3: UIResource Union (list[UIResource] | str)

```python
from typing import Any
from fastmcp import FastMCP
from mcp_ui_server import create_ui_resource

mcp = FastMCP("ui-tool")

@mcp.tool()
async def display_content(path: str) -> list[dict[str, Any]] | str:
    """Display file with UI or return error message.

    Note: UIResource is a dict[str, Any], so we use that type hint.
    """
    if not path.exists():
        return f"Error: File not found: {path}"

    # Create UI resource
    ui_resource = create_ui_resource({
        "uri": f"ui://viewer/{path}",
        "content": {
            "type": "rawHtml",
            "htmlString": "<h1>File Content</h1><pre>...</pre>"
        },
        "encoding": "text"
    })

    return [ui_resource]  # Returns list of dict
```

**Generated schema:**
```json
{
  "anyOf": [
    {
      "type": "array",
      "items": {"type": "object"}
    },
    {"type": "string"}
  ]
}
```

**No `output_schema` parameter needed.**

## Example 4: scout_mcp Pattern (Current Implementation)

```python
from typing import Any
from fastmcp import FastMCP
from mcp_ui_server import create_ui_resource
from scout_mcp.ui import create_file_viewer_ui

mcp = FastMCP("scout_mcp")

@mcp.tool()
async def scout(
    target: str = "",
    query: str | None = None,
    # ... other parameters
) -> list[dict[str, Any]] | str:
    """Scout remote files and directories via SSH.

    Returns:
        UIResource list with interactive UI for files/directories, or
        plain string for commands, diffs, searches, and other operations.
    """
    # Error case - return string
    if not target:
        return "Error: Target required"

    # UI case - return list of UIResource (which are dicts)
    if is_file(target):
        content = await read_file(target)
        html = await create_file_viewer_ui(host, path, content)
        ui_resource = create_ui_resource({
            "uri": f"ui://scout/{host}/{path}",
            "content": {"type": "rawHtml", "htmlString": html},
            "encoding": "text"
        })
        return [ui_resource]

    # Command case - return string
    if query:
        output = await run_command(target, query)
        return output
```

**Why this works:**
1. ✅ Type hint `list[dict[str, Any]] | str` is sufficient
2. ✅ FastMCP auto-generates union schema
3. ✅ `create_ui_resource()` returns `dict[str, Any]`
4. ✅ Pydantic validates both branches
5. ✅ No manual schema needed

## Example 5: When to Use output_schema (Advanced)

**Only use `output_schema` when you need strict validation:**

```python
from fastmcp import FastMCP

mcp = FastMCP("strict-tool")

@mcp.tool(output_schema={
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "score": {"type": "number", "minimum": 0, "maximum": 1}
                },
                "required": ["id", "name", "score"]
            }
        },
        "total": {"type": "integer"}
    },
    "required": ["results", "total"]
})
def search_strict(query: str) -> dict[str, Any]:
    """Search with strict schema validation."""
    return {
        "results": [
            {"id": 1, "name": "Item 1", "score": 0.95},
            {"id": 2, "name": "Item 2", "score": 0.87}
        ],
        "total": 2
    }
```

**Use case:** When you need field-level validation (types, ranges, required fields) beyond what Pydantic infers.

## Example 6: Pydantic Model (Best for Complex Types)

**Instead of manual `output_schema`, use Pydantic models:**

```python
from fastmcp import FastMCP
from pydantic import BaseModel, Field

mcp = FastMCP("model-tool")

class SearchResult(BaseModel):
    """Search result model."""
    id: int
    name: str
    score: float = Field(ge=0, le=1, description="Relevance score")

class SearchResponse(BaseModel):
    """Search response model."""
    results: list[SearchResult]
    total: int

@mcp.tool()
def search_typed(query: str) -> SearchResponse:
    """Search with Pydantic model validation."""
    return SearchResponse(
        results=[
            SearchResult(id=1, name="Item 1", score=0.95),
            SearchResult(id=2, name="Item 2", score=0.87)
        ],
        total=2
    )
```

**Advantages:**
1. ✅ Type safety in code
2. ✅ Auto-generated schema from model
3. ✅ Field validation (ranges, patterns)
4. ✅ Better IDE support
5. ✅ Reusable models

## Example 7: Union with Pydantic Models

```python
from fastmcp import FastMCP
from pydantic import BaseModel

mcp = FastMCP("union-model-tool")

class SuccessResponse(BaseModel):
    status: str = "success"
    data: list[dict]

class ErrorResponse(BaseModel):
    status: str = "error"
    message: str

@mcp.tool()
def fetch_data(query: str) -> SuccessResponse | ErrorResponse:
    """Fetch data or return error."""
    if not query:
        return ErrorResponse(message="Query cannot be empty")

    return SuccessResponse(data=[{"id": 1, "value": "test"}])
```

**Generated schema uses `anyOf` with two object schemas.**

## Summary Table

| Return Type | Need output_schema? | FastMCP Behavior |
|------------|---------------------|------------------|
| `str` | ❌ No | Auto-generates string schema |
| `dict` | ❌ No | Auto-generates object schema |
| `list[dict]` | ❌ No | Auto-generates array schema |
| `str \| dict` | ❌ No | Auto-generates anyOf union |
| `list[dict] \| str` | ❌ No | Auto-generates anyOf union |
| `list[dict[str, Any]] \| str` | ❌ No | Auto-generates anyOf union |
| Pydantic model | ❌ No | Generates from model schema |
| Model1 \| Model2 | ❌ No | Auto-generates anyOf union |
| Custom validation | ✅ Yes | Manual schema with constraints |

## Testing Union Types

```python
import pytest
from fastmcp import FastMCP

mcp = FastMCP("test")

@mcp.tool()
async def my_tool(mode: str) -> list[dict] | str:
    if mode == "error":
        return "Error occurred"
    return [{"id": 1, "value": "data"}]

@pytest.mark.asyncio
async def test_returns_list():
    """Test list return path."""
    result = await my_tool(mode="success")
    assert isinstance(result, list)
    assert len(result) > 0
    assert isinstance(result[0], dict)

@pytest.mark.asyncio
async def test_returns_string():
    """Test string return path."""
    result = await my_tool(mode="error")
    assert isinstance(result, str)
    assert "Error" in result
```

## Common Mistakes

### ❌ Don't: Add unnecessary output_schema
```python
# UNNECESSARY - FastMCP does this automatically
@mcp.tool(output_schema={
    "anyOf": [
        {"type": "array", "items": {"type": "object"}},
        {"type": "string"}
    ]
})
async def my_tool() -> list[dict] | str:
    pass
```

### ✅ Do: Trust the type hint
```python
# CORRECT - Let FastMCP generate schema
@mcp.tool()
async def my_tool() -> list[dict] | str:
    pass
```

### ❌ Don't: Mix type systems
```python
# CONFUSING - Type hint says str, schema says object
@mcp.tool(output_schema={"type": "object"})
async def my_tool() -> str:
    return "string"  # Will fail validation
```

### ✅ Do: Keep type hint and schema aligned
```python
# CORRECT - Type hint and Pydantic model match
class Response(BaseModel):
    message: str

@mcp.tool()
async def my_tool() -> Response:
    return Response(message="success")
```

## Conclusion

**For scout_mcp's `list[dict[str, Any]] | str` return type:**

```python
# Current implementation - CORRECT ✅
async def scout(...) -> list[dict[str, Any]] | str:
    """No output_schema parameter needed."""
    pass
```

**FastMCP handles it automatically through:**
1. Type hint inspection
2. Pydantic schema generation
3. Union type support (anyOf)
4. Automatic validation

**No changes needed.**
