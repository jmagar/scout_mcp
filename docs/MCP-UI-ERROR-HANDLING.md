# MCP-UI Error Handling

Scout MCP implements comprehensive error handling and logging for all MCP-UI functionality.

## Logging

All MCP-UI operations are logged with appropriate detail levels:

### Debug Level
- UIResource creation parameters (URI, content type, content length)
- File/directory paths being processed
- Resource URI construction details

### Info Level
- Successful UIResource creation with metadata
- Content type and size information
- Resource URI after creation

### Error Level
- Invalid URI format errors
- UIResource creation failures
- Unexpected exceptions with full context

## Error Types

### `InvalidURIError`

**Cause:** URI doesn't start with `ui://`

**Example:**
```python
from mcp_ui_server import create_ui_resource
from mcp_ui_server.exceptions import InvalidURIError

try:
    create_ui_resource({
        "uri": "invalid://should-be-ui",
        "content": {"type": "rawHtml", "htmlString": "<h1>Test</h1>"},
        "encoding": "text"
    })
except InvalidURIError as e:
    print(f"Error: {e}")
    # URI must start with 'ui://' but got: invalid://should-be-ui
```

**Common mistakes:**
- Using `http://` or `https://` instead of `ui://`
- Forgetting the `ui://` scheme entirely
- Typos in URI scheme

**Fix:** Ensure all UIResource URIs start with `ui://`

### Generic Exceptions

**Cause:** Unexpected errors during UIResource creation

**Handling:**
- Full exception logged with stack trace
- User-friendly error message returned
- Tool execution continues (returns error string instead of failing)

## Error Handling in Tools

### Test Tools (`ui_tests.py`)

All test tools wrap UIResource creation in try/except blocks:

```python
try:
    logger.debug("Creating rawHtml UIResource with URI: ui://scout/test/raw-html")
    ui_resource = create_ui_resource({...})
    logger.info("Successfully created rawHtml UIResource (URI: %s, content_length: %d bytes)", ...)
    return [ui_resource]
except InvalidURIError as e:
    logger.error("Invalid URI format for rawHtml test: %s", e)
    raise
except Exception as e:
    logger.exception("Unexpected error creating rawHtml UIResource: %s", e)
    raise
```

**Behavior:**
- Specific `InvalidURIError` handling with error logging
- Generic exception catch-all with full traceback logging
- Exceptions are re-raised to MCP server for proper error response

### Scout Tool (`scout.py`)

The main scout tool includes graceful error handling:

```python
try:
    logger.debug("Creating file viewer UIResource (host=%s, path=%s, uri=%s)", ...)
    ui_resource = create_ui_resource({...})
    logger.info("Successfully created file viewer UIResource (URI: %s, content_length: %d bytes)", ...)
    return [ui_resource]
except InvalidURIError as e:
    logger.error("Invalid URI format for file viewer (uri=%s): %s", uri, e)
    return f"Error: Failed to create UI resource - invalid URI format: {e}"
except Exception as e:
    logger.exception("Unexpected error creating file viewer UIResource (path=%s): %s", parsed.path, e)
    return f"Error: Failed to create UI resource: {e}"
```

**Behavior:**
- Errors are caught and logged
- User-friendly error message is returned as string
- Tool execution continues (doesn't crash the server)
- Full context preserved in logs for debugging

## Debugging MCP-UI Issues

### Enable DEBUG Logging

Set environment variable:
```bash
export SCOUT_LOG_LEVEL=DEBUG
```

Or in code:
```python
import logging
logging.getLogger("scout_mcp").setLevel(logging.DEBUG)
```

### Check Logs for MCP-UI Operations

Look for these log patterns:

**Successful creation:**
```
DEBUG | scout_mcp.tools.ui_tests | Creating rawHtml UIResource with URI: ui://scout/test/raw-html
INFO  | scout_mcp.tools.ui_tests | Successfully created rawHtml UIResource (URI: ui://scout/test/raw-html, content_length: 3221 bytes)
```

**URI format error:**
```
ERROR | scout_mcp.tools.ui_tests | Invalid URI format for rawHtml test: URI must start with 'ui://' but got: invalid://...
```

**Unexpected error:**
```
ERROR | scout_mcp.tools.scout | Unexpected error creating file viewer UIResource (path=/var/log/app.log): ...
Traceback (most recent call last):
  ...
```

### Common Issues

#### 1. Double Slashes in URI

**Symptom:**
```
uri://scout/host//path/to/file
                  ^^
```

**Cause:** Path starts with `/`, creating double slash when concatenated

**Fix:** Strip leading slash before URI construction
```python
path_clean = parsed.path.lstrip('/')
uri = f"ui://scout/{parsed.host}/{path_clean}"
```

**Status:** ✅ Fixed in scout.py (lines 281-287, 319-321)

#### 2. Invalid Content Type

**Symptom:** Client doesn't render UIResource

**Cause:** Unsupported content type or malformed content structure

**Debug:**
1. Check logs for successful UIResource creation
2. Verify content type is supported by client
3. Check content structure matches MCP-UI spec

#### 3. HTML Generation Errors

**Symptom:** UIResource created but empty/malformed HTML

**Cause:** Error in template generation

**Debug:**
1. Check HTML generator functions in `ui/templates.py`
2. Verify template has valid HTML structure
3. Check for exceptions in HTML generation

## Testing Error Handling

### Manual Testing

```python
from mcp_ui_server import create_ui_resource
from mcp_ui_server.exceptions import InvalidURIError

# Test 1: Invalid URI scheme
try:
    create_ui_resource({
        "uri": "http://example.com",
        "content": {"type": "rawHtml", "htmlString": "<h1>Test</h1>"},
        "encoding": "text"
    })
except InvalidURIError as e:
    print(f"✓ Caught expected error: {e}")

# Test 2: Empty URI
try:
    create_ui_resource({
        "uri": "",
        "content": {"type": "rawHtml", "htmlString": "<h1>Test</h1>"},
        "encoding": "text"
    })
except (InvalidURIError, ValueError) as e:
    print(f"✓ Caught expected error: {e}")

# Test 3: Successful creation
try:
    ui_resource = create_ui_resource({
        "uri": "ui://test/valid",
        "content": {"type": "rawHtml", "htmlString": "<h1>Test</h1>"},
        "encoding": "text"
    })
    print(f"✓ Successfully created: {ui_resource.resource.uri}")
except Exception as e:
    print(f"✗ Unexpected error: {e}")
```

### Automated Testing

See [tests/test_ui_error_handling.py](../tests/test_ui_error_handling.py) for comprehensive test suite.

## Best Practices

1. **Always use try/except** around `create_ui_resource()` calls
2. **Log at appropriate levels:**
   - DEBUG: Input parameters
   - INFO: Successful operations
   - ERROR: Failures with context
3. **Catch specific exceptions first:**
   - `InvalidURIError` for URI format issues
   - Generic `Exception` as fallback
4. **Provide context in error messages:**
   - Include URI, path, host when logging errors
   - Help users understand what went wrong
5. **Don't crash the server:**
   - Return error strings instead of raising in tools
   - Let MCP server handle the error response
6. **Test error paths:**
   - Verify invalid URIs are caught
   - Test with malformed content
   - Ensure graceful degradation

## Files with Error Handling

- [scout_mcp/tools/ui_tests.py](../scout_mcp/tools/ui_tests.py) - Test tools with error handling
- [scout_mcp/tools/scout.py](../scout_mcp/tools/scout.py) - Main scout tool error handling
- [tests/test_ui_error_handling.py](../tests/test_ui_error_handling.py) - Automated tests

## Related Documentation

- [MCP-UI Testing Guide](MCP-UI-TESTING.md)
- [MCP-UI Implementation](../README.md#interactive-ui)
- [mcp-ui-server Documentation](https://github.com/MCP-UI-Org/mcp-ui)
