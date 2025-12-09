# FastMCP Output Schema Quick Reference

## Do I Need output_schema?

| Your Return Type | Need output_schema? | Why |
|-----------------|---------------------|-----|
| `str` | ❌ No | Auto-generated |
| `int`, `float`, `bool` | ❌ No | Auto-wrapped as `{"result": value}` |
| `dict` | ❌ No | Auto-generated object schema |
| `list[dict]` | ❌ No | Auto-generated array schema |
| `list[dict[str, Any]]` | ❌ No | Auto-generated array schema |
| **`list[dict] \| str`** | **❌ No** | **Auto-generated anyOf union** |
| **`list[dict[str, Any]] \| str`** | **❌ No** | **Auto-generated anyOf union** |
| `Pydantic Model` | ❌ No | Schema from model definition |
| `Model1 \| Model2` | ❌ No | Auto-generated anyOf union |
| Need field validation | ✅ Yes | Manual constraints (min/max/pattern) |

## FastMCP Auto-Generation Rules

### 1. Object-like Types → Always Structured
- `dict`, Pydantic models, dataclasses
- **Always** become structured content
- **Always** validated against schema

### 2. Primitive Types → Conditional
- `int`, `str`, `bool`, `list`
- Only structured if output schema exists
- Otherwise, plain text content

### 3. Union Types → anyOf Schema
```python
# Type hint
-> list[dict] | str

# Generated schema
{
  "anyOf": [
    {"type": "array", "items": {"type": "object"}},
    {"type": "string"}
  ]
}
```

## Common Patterns

### ✅ Pattern: Union Return (scout_mcp)

```python
async def scout(...) -> list[dict[str, Any]] | str:
    # UI path
    return [create_ui_resource({...})]

    # Error path
    return "Error message"
```

**No `output_schema` needed.**

### ✅ Pattern: Pydantic Model

```python
from pydantic import BaseModel

class Response(BaseModel):
    id: int
    data: list[dict]

@mcp.tool()
def my_tool() -> Response:
    return Response(id=1, data=[...])
```

**No `output_schema` needed.**

### ✅ Pattern: Pydantic Union

```python
class Success(BaseModel):
    status: str = "ok"
    data: list

class Error(BaseModel):
    status: str = "error"
    message: str

@mcp.tool()
def my_tool() -> Success | Error:
    return Success(data=[...])
```

**No `output_schema` needed.**

### ⚠️ Pattern: Manual Schema (Advanced)

```python
@mcp.tool(output_schema={
    "type": "object",
    "properties": {
        "score": {
            "type": "number",
            "minimum": 0,
            "maximum": 1
        }
    },
    "required": ["score"]
})
def my_tool() -> dict:
    return {"score": 0.95}
```

**Only for strict field validation.**

## UIResource Pattern

### create_ui_resource() Returns Pydantic Model

```python
from mcp_ui_server import create_ui_resource

# Returns UIResource (Pydantic model)
ui = create_ui_resource({
    "uri": "ui://path",
    "content": {"type": "rawHtml", "htmlString": "<h1>Hi</h1>"},
    "encoding": "text"
})

# Type is UIResource (Pydantic model), NOT dict
type(ui)  # <class 'mcp_ui_server.core.UIResource'>

# But it serializes to dict for MCP protocol
ui.model_dump()  # Returns dict[str, Any]
```

**Key insight:** UIResource is a Pydantic model, which means:
- FastMCP recognizes it as structured content (object-like)
- Automatically serializes to dict via `model_dump()`
- Works with both `list[UIResource]` and `list[dict[str, Any]]` type hints

### Return as list[dict]

```python
@mcp.tool()
async def show_ui() -> list[dict[str, Any]]:
    ui = create_ui_resource({...})
    return [ui]  # Wrap in list
```

### Union with String

```python
@mcp.tool()
async def show_ui_or_error() -> list[dict[str, Any]] | str:
    if error:
        return "Error message"
    return [create_ui_resource({...})]
```

## When to Use output_schema

### ✅ Use When:
1. Need field constraints (min/max, regex patterns)
2. Need required fields beyond type
3. Auto-generated schema is wrong (rare bug)
4. Want to suppress structured output

### ❌ Don't Use When:
1. Type hints are sufficient
2. Simple types (`str`, `dict`, `list`)
3. Union types (`A | B`)
4. Pydantic models (already have schema)

## Known Issues

### Issue #2153: Nested Union Models
**Problem:** Deep nesting with unions breaks

```python
# ❌ This can fail
class MyModel(BaseModel):
    field: TypeA | TypeB  # Nested union

# Error: PointerToNowhere: '/$defs/TypeA' does not exist
```

**Workaround:** Flatten schema or use simpler types

**Doesn't affect:** `list[dict[str, Any]] | str`

### Issue #1969: List Type Conversion
**Status:** Fixed in FastMCP 2.12.4+

**Problem was:** Lists of special types stringified incorrectly

**Now fixed:** Proper ContentBlock handling

## Testing Union Returns

```python
@pytest.mark.asyncio
async def test_union_list_path():
    result = await my_tool(mode="ui")
    assert isinstance(result, list)
    assert isinstance(result[0], dict)

@pytest.mark.asyncio
async def test_union_string_path():
    result = await my_tool(mode="error")
    assert isinstance(result, str)
```

## Quick Decision Tree

```
Need output schema?
│
├─ Return type is str, int, dict, list?
│  └─ ❌ No → Auto-generated
│
├─ Return type is Pydantic model?
│  └─ ❌ No → Schema from model
│
├─ Return type is Union (A | B)?
│  └─ ❌ No → Auto-generates anyOf
│
├─ Need field validation (min/max/pattern)?
│  └─ ✅ Yes → Use output_schema
│
└─ Otherwise?
   └─ ❌ No → Trust FastMCP
```

## Resources

- [FastMCP Tools Docs](https://gofastmcp.com/servers/tools)
- [MCP-UI Python Guide](https://mcpui.dev/guide/server/python/walkthrough)
- [Detailed Research](./fastmcp-union-type-schemas.md)
- [Code Examples](./fastmcp-union-types-examples.md)

## TL;DR

**For `list[dict[str, Any]] | str`:**

```python
# ✅ This is correct - no changes needed
async def scout(...) -> list[dict[str, Any]] | str:
    pass
```

**FastMCP handles everything automatically.**
