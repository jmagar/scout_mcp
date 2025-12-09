# MCP-UI Testing Tools

Scout MCP includes three test tools to verify MCP-UI rendering in different clients.

## Test Tools

### 1. `test_raw_html()`

Tests raw HTML rendering with styled content.

**Content Type:** `rawHtml`

**Usage:**
```python
test_raw_html()
```

**What it does:**
- Returns a styled HTML page with gradient background
- Includes cards, badges, and grid layout
- Tests CSS rendering and HTML structure
- Shows "✓ Rendering Active" if working correctly

**Expected Result:**
You should see a purple gradient background with a white card containing:
- Title: "🎨 Raw HTML Test"
- Description text
- Green badge with checkmark
- Three info boxes showing "rawHtml", "MCP-UI", "✓"

---

### 2. `test_remote_dom()`

Tests dynamic DOM creation using JavaScript.

**Content Type:** `remoteDom`

**Usage:**
```python
test_remote_dom()
```

**What it does:**
- Executes JavaScript to build DOM elements
- Uses React framework with MCP-UI components
- Creates Card, Stack, and Text elements dynamically
- Tests JavaScript execution in sandbox

**Expected Result:**
You should see a pink gradient background with a white card containing:
- Title: "🔮 Remote DOM Test"
- Description about JavaScript execution
- Red badge: "✓ JavaScript Executed"
- Three info boxes: "remoteDom", "React", "Dynamic"

**Note:** This requires the client to support the `remoteDom` content type with React framework.

---

### 3. `test_external_url()`

Tests iframe rendering of external websites.

**Content Type:** `externalUrl`

**Usage:**
```python
test_external_url()
```

**What it does:**
- Loads example.com in a sandboxed iframe
- Tests external URL embedding
- Includes CSS styling for iframe dimensions

**Expected Result:**
You should see example.com loaded in an iframe with:
- 600px height
- Rounded corners (8px border-radius)
- Light gray border
- Full width

**Note:** Some websites block iframe embedding via X-Frame-Options headers.

---

## Testing in MCPJam

1. **Connect to Scout MCP server** in MCPJam Inspector
2. **Open the LLM Playground/Chat interface** (not just Inspector)
3. **Call a test tool:**
   ```
   Call test_raw_html
   ```
4. **Check the chat message** for rendered UI (not just JSON)

## Troubleshooting

### "I only see JSON, not rendered UI"

**Possible causes:**
1. Using Inspector/Tools tab instead of Chat/Playground
2. MCPJam chat doesn't support MCP-UI (check client documentation)
3. JavaScript errors in browser console (press F12)
4. Client configured for different UI framework

**Solution:**
- Make sure you're in the **Chat/Playground** interface
- Check browser console (F12) for errors
- Verify MCPJam supports MCP-UI in chat

### "remoteDom doesn't render"

**Possible causes:**
1. Client doesn't support remoteDom content type
2. React framework not available in client
3. JavaScript execution blocked

**Solution:**
- Try `test_raw_html()` first (simpler)
- Check client documentation for remoteDom support
- Use browser console to debug JavaScript errors

### "externalUrl shows blank iframe"

**Possible causes:**
1. Website blocks iframe embedding (X-Frame-Options)
2. CORS policies blocking content
3. Network connectivity issues

**Solution:**
- This is expected for many modern websites
- Successful iframe appearance confirms the feature works
- Try with a URL you control for testing

## Expected MCP Response Structure

All three tools return the same MCP structure:

```json
{
  "content": [
    {
      "type": "resource",
      "resource": {
        "uri": "ui://scout/test/...",
        "mimeType": "text/html",
        "text": "..."
      }
    }
  ]
}
```

The `resource.uri` starts with `ui://` which signals MCP-UI clients to render the content.

## Implementation Details

**Files:**
- [scout_mcp/tools/ui_tests.py](../scout_mcp/tools/ui_tests.py) - Test tool implementations
- [scout_mcp/server.py:444-447](../scout_mcp/server.py#L444-L447) - Tool registration

**Key Points:**
- All tools return `list[UIResource]`
- Registered with `output_schema=None` (no validation)
- Use `create_ui_resource()` from mcp-ui-server SDK
- URIs follow pattern: `ui://scout/test/<test-name>`

## Client Compatibility

These tools test MCP-UI compatibility with different clients:

| Client | rawHtml | remoteDom | externalUrl |
|--------|---------|-----------|-------------|
| MCPJam Inspector | ✓ | ? | ✓ |
| Claude Desktop | ? | ? | ? |
| Custom MCP-UI Client | ✓ | ✓ | ✓ |

**Legend:**
- ✓ = Known to work
- ? = Untested
- ✗ = Known not to work

## Resources

- [MCP-UI Documentation](https://mcpui.dev/)
- [MCP-UI GitHub](https://github.com/MCP-UI-Org/mcp-ui)
- [mcp-ui-server SDK](https://pypi.org/project/mcp-ui-server/)
- [MCPJam Inspector](https://www.mcpjam.com/)
