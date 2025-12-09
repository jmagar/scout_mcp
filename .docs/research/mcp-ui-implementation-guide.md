# MCP-UI Implementation Guide: text/html Content Type

**Research Date:** 2025-12-07
**Purpose:** Understand proper implementation of MCP-UI with text/html content type for Python SDK

---

## Executive Summary

MCP-UI supports **two distinct approaches** for delivering interactive UI:

1. **Raw HTML Rendering** (`text/html` mimeType) - Direct HTML in sandboxed iframes
2. **Component-Based Rendering** (`application/vnd.mcp-ui.remote-dom` mimeType) - JavaScript-based dynamic components

For the Python SDK (`mcp-ui-server`), the correct approach is **NOT** returning component objects like `Button`, `Text`, `Stack`, etc. Instead, the SDK uses `create_ui_resource()` which returns a `UIResource` object with the appropriate mimeType.

---

## UIResource Structure

The `UIResource` interface defines the contract for UI delivery:

```typescript
interface UIResource {
  type: 'resource';
  resource: {
    uri: string;              // Must use ui:// scheme (e.g., ui://component/id)
    mimeType: 'text/html' | 'text/uri-list' | 'application/vnd.mcp-ui.remote-dom';
    text?: string;            // Inline content (HTML, URL, or script)
    blob?: string;            // Base64-encoded content
  };
}
```

### MIME Type Options

| MIME Type | Use Case | Rendering Method |
|-----------|----------|------------------|
| `text/html` | Inline HTML content | `<iframe srcdoc="...">` with sandboxing |
| `text/uri-list` | External URLs | `<iframe src="...">` with enhanced permissions |
| `application/vnd.mcp-ui.remote-dom` | Dynamic JavaScript components | Remote DOM via Shopify's framework |

---

## Python SDK: `mcp-ui-server`

### Installation

```bash
pip install mcp-ui-server
# or
uv add mcp-ui-server
```

**Requirements:**
- Python 3.10+
- Full type annotations included
- Works with `mcp` package (FastMCP)

### Core API: `create_ui_resource()`

```python
from mcp_ui_server import create_ui_resource

def create_ui_resource(options_dict: dict[str, Any]) -> UIResource:
    """
    Create a UIResource object for MCP.

    Args:
        options_dict: Dictionary containing:
            - uri (str): Resource identifier (must start with ui://)
            - content (dict): Content specification
            - encoding (str): "text" or "blob" (Base64)

    Returns:
        UIResource: JSON-serializable dict with type, resource fields
    """
```

### Options Dictionary Structure

```python
{
    "uri": "ui://component/instance-id",
    "content": {
        "type": "rawHtml" | "externalUrl" | "remoteDom",
        # type-specific fields below
    },
    "encoding": "text" | "blob"
}
```

---

## Usage Examples

### 1. Raw HTML with Text Encoding

```python
from mcp_ui_server import create_ui_resource

resource = create_ui_resource({
    "uri": "ui://my-component/instance-1",
    "content": {
        "type": "rawHtml",
        "htmlString": """
            <div style="padding: 20px; font-family: Arial, sans-serif;">
                <h1 style="color: #2563eb;">Hello from Python MCP Server!</h1>
                <p>This UI resource was generated server-side using mcp-ui-server.</p>
            </div>
        """
    },
    "encoding": "text"
})
```

**Generated UIResource:**
```python
{
    "type": "resource",
    "resource": {
        "uri": "ui://my-component/instance-1",
        "mimeType": "text/html",
        "text": "<div style=\"padding: 20px...",
        "blob": None
    }
}
```

### 2. Raw HTML with Blob Encoding (Base64)

```python
resource = create_ui_resource({
    "uri": "ui://my-component/instance-2",
    "content": {
        "type": "rawHtml",
        "htmlString": "<h1>Complex HTML Content</h1>"
    },
    "encoding": "blob"  # SDK auto-encodes to Base64
})
```

**Generated UIResource:**
```python
{
    "type": "resource",
    "resource": {
        "uri": "ui://my-component/instance-2",
        "mimeType": "text/html",
        "text": None,
        "blob": "PGgxPkNvbXBsZXggSFRNTCBDb250ZW50PC9oMT4="
    }
}
```

### 3. External URL (iframe src)

```python
resource = create_ui_resource({
    "uri": "ui://dashboard/analytics",
    "content": {
        "type": "externalUrl",
        "iframeUrl": "https://my.analytics.com/dashboard"
    },
    "encoding": "text"
})
```

**Generated UIResource:**
```python
{
    "type": "resource",
    "resource": {
        "uri": "ui://dashboard/analytics",
        "mimeType": "text/uri-list",
        "text": "https://my.analytics.com/dashboard",
        "blob": None
    }
}
```

### 4. Remote DOM (JavaScript Components)

```python
remote_dom_script = """
const button = document.createElement('ui-button');
button.setAttribute('label', 'Click me for a tool call!');
button.addEventListener('press', () => {
    window.parent.postMessage({
        type: 'tool',
        payload: {
            toolName: 'uiInteraction',
            params: { action: 'button-click' }
        }
    }, '*');
});
root.appendChild(button);
"""

resource = create_ui_resource({
    "uri": "ui://remote-component/action-button",
    "content": {
        "type": "remoteDom",
        "script": remote_dom_script.strip(),
        "framework": "react"  # or "webcomponents"
    },
    "encoding": "text"
})
```

**Generated UIResource:**
```python
{
    "type": "resource",
    "resource": {
        "uri": "ui://remote-component/action-button",
        "mimeType": "application/vnd.mcp-ui.remote-dom",
        "text": "const button = document.createElement...",
        "blob": None
    }
}
```

---

## FastMCP Integration

### Complete Server Example

```python
import argparse
from mcp.server.fastmcp import FastMCP
from mcp_ui_server import create_ui_resource
from mcp_ui_server.core import UIResource

# Create FastMCP instance
mcp = FastMCP("my-mcp-server")

@mcp.tool()
def show_greeting() -> list[UIResource]:
    """Display a greeting UI resource."""
    ui_resource = create_ui_resource({
        "uri": "ui://greeting/simple",
        "content": {
            "type": "rawHtml",
            "htmlString": """
                <div style="padding: 20px; text-align: center; font-family: Arial, sans-serif;">
                    <h1 style="color: #2563eb;">Hello from Python MCP Server!</h1>
                    <p>This UI resource was generated server-side using mcp-ui-server.</p>
                </div>
            """
        },
        "encoding": "text"
    })
    return [ui_resource]

@mcp.tool()
def show_dashboard() -> list[UIResource]:
    """Display analytics dashboard via external URL."""
    ui_resource = create_ui_resource({
        "uri": "ui://dashboard/analytics",
        "content": {
            "type": "externalUrl",
            "iframeUrl": "https://my.analytics.com/dashboard"
        },
        "encoding": "text"
    })
    return [ui_resource]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MCP UI Server Demo")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    args = parser.parse_args()

    mcp.run(transport=args.transport)
```

---

## Client-Side Rendering

### HTMLResourceRenderer Component

The MCP-UI client uses `HTMLResourceRenderer` (internal component) to render `text/html` resources:

**Rendering Process:**
1. Check `resource.mimeType === 'text/html'`
2. Extract HTML from `resource.text` or decode `resource.blob` (Base64)
3. Create `<iframe>` with `srcdoc` attribute
4. Apply sandbox permissions: `"allow-scripts"` (default)
5. Enable auto-resizing if iframe posts `ui-size-change` messages

**Security:**
- All HTML rendered in sandboxed iframes
- Default permissions: `allow-scripts`
- Additional permissions via `sandboxPermissions` prop
- Users should sanitize untrusted HTML or rely on iframe isolation

**Auto-Resizing:**
- Iframe content can post `ui-size-change` messages
- Client listens via `postMessage` API
- Adjusts iframe height dynamically

---

## Key Differences: Component-Based vs Raw HTML

### Component-Based (Remote DOM)

```python
# WRONG for Python SDK - This is TypeScript/JavaScript approach
from mcp_ui import Button, Text, Stack  # These don't exist in Python!

return Stack(
    children=[
        Text(content="Hello"),
        Button(label="Click me")
    ]
)
```

### Raw HTML (Correct for Python)

```python
# CORRECT for Python SDK
from mcp_ui_server import create_ui_resource

return [create_ui_resource({
    "uri": "ui://greeting/1",
    "content": {
        "type": "rawHtml",
        "htmlString": """
            <div>
                <p>Hello</p>
                <button>Click me</button>
            </div>
        """
    },
    "encoding": "text"
})]
```

---

## SDK Features

### Automatic Validation

The SDK performs:
- **URI prefix checking**: Enforces `ui://` scheme
- **MIME type mapping**: Automatically sets based on content type
- **Base64 encoding**: Auto-encodes when `encoding: "blob"`
- **Type safety**: Uses dataclasses internally, returns dicts for MCP

### Error Handling

```python
from mcp_ui_server.exceptions import InvalidURIError

try:
    create_ui_resource({
        "uri": "invalid://should-be-ui",  # Wrong scheme!
        "content": {
            "type": "externalUrl",
            "iframeUrl": "https://example.com"
        },
        "encoding": "text"
    })
except InvalidURIError as e:
    print(f"Error: {e}")
```

---

## Official Documentation

### Primary Sources

- **Official Documentation**: [mcpui.dev](https://mcpui.dev)
- **GitHub Repository**: [MCP-UI-Org/mcp-ui](https://github.com/MCP-UI-Org/mcp-ui)
- **Python Overview**: [mcpui.dev/guide/server/python/overview](https://mcpui.dev/guide/server/python/overview)
- **Python Walkthrough**: [mcpui.dev/guide/server/python/walkthrough](https://mcpui.dev/guide/server/python/walkthrough)
- **Usage Examples**: [mcpui.dev/guide/server/python/usage-examples](https://mcpui.dev/guide/server/python/usage-examples)
- **HTML Resource Renderer**: [mcpui.dev/guide/client/html-resource](https://mcpui.dev/guide/client/html-resource)

### Additional Resources

- **PyPI Package**: [pypi.org/project/mcp-ui/](https://pypi.org/project/mcp-ui/)
- **Technical Deep Dive**: [WorkOS Blog - MCP-UI Technical Overview](https://workos.com/blog/mcp-ui-a-technical-deep-dive-into-interactive-agent-interfaces)

---

## Conclusion

### What We Learned

1. **MCP-UI supports raw HTML via `text/html` mimeType** - This is NOT component-based
2. **Python SDK uses `create_ui_resource()` function** - Returns `UIResource` dict
3. **Three content types available**:
   - `rawHtml` → `text/html` mimeType (iframe srcdoc)
   - `externalUrl` → `text/uri-list` mimeType (iframe src)
   - `remoteDom` → `application/vnd.mcp-ui.remote-dom` mimeType (JavaScript)
4. **Encoding options**: `"text"` (inline) or `"blob"` (Base64)
5. **Security**: All HTML rendered in sandboxed iframes with configurable permissions

### Correct Implementation Pattern

```python
from mcp.server.fastmcp import FastMCP
from mcp_ui_server import create_ui_resource

mcp = FastMCP("scout-mcp")

@mcp.tool()
def my_ui_tool() -> list:
    """Return UI resource."""
    return [create_ui_resource({
        "uri": "ui://my-tool/instance",
        "content": {
            "type": "rawHtml",
            "htmlString": "<div>Your HTML here</div>"
        },
        "encoding": "text"
    })]
```

---

## References

All information sourced from official MCP-UI documentation at mcpui.dev and the MCP-UI-Org/mcp-ui GitHub repository.

**License:** Apache 2.0
**Python SDK:** mcp-ui-server (Python 3.10+)
**Last Updated:** 2025-12-07
