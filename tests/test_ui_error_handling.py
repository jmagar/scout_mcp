"""Test MCP-UI error handling and logging."""

import pytest
from mcp_ui_server.exceptions import InvalidURIError

from scout_mcp.tools.ui_tests import test_external_url, test_raw_html, test_remote_dom


def test_raw_html_success():
    """Test successful rawHtml UIResource creation."""
    result = test_raw_html()
    assert len(result) == 1
    assert result[0].type == "resource"
    assert str(result[0].resource.uri) == "ui://scout/test/raw-html"
    assert result[0].resource.mimeType == "text/html"
    assert len(result[0].resource.text) > 0


def test_remote_dom_success():
    """Test successful remoteDom UIResource creation."""
    result = test_remote_dom()
    assert len(result) == 1
    assert result[0].type == "resource"
    assert str(result[0].resource.uri) == "ui://scout/test/remote-dom"
    assert result[0].resource.mimeType == "text/html"
    assert len(result[0].resource.text) > 0


def test_external_url_success():
    """Test successful externalUrl UIResource creation."""
    result = test_external_url()
    assert len(result) == 1
    assert result[0].type == "resource"
    assert str(result[0].resource.uri) == "ui://scout/test/external-url"
    assert result[0].resource.mimeType == "text/html"
    assert "example.com" in result[0].resource.text


def test_invalid_uri_error():
    """Test that InvalidURIError is raised for non-ui:// URIs."""
    from mcp_ui_server import create_ui_resource

    with pytest.raises(InvalidURIError) as exc_info:
        create_ui_resource({
            "uri": "invalid://should-be-ui",
            "content": {"type": "rawHtml", "htmlString": "<h1>Test</h1>"},
            "encoding": "text"
        })

    assert "URI must start with 'ui://'" in str(exc_info.value)


def test_http_uri_error():
    """Test that HTTP URIs are rejected."""
    from mcp_ui_server import create_ui_resource

    with pytest.raises(InvalidURIError):
        create_ui_resource({
            "uri": "http://example.com",
            "content": {"type": "rawHtml", "htmlString": "<h1>Test</h1>"},
            "encoding": "text"
        })


def test_https_uri_error():
    """Test that HTTPS URIs are rejected."""
    from mcp_ui_server import create_ui_resource

    with pytest.raises(InvalidURIError):
        create_ui_resource({
            "uri": "https://example.com",
            "content": {"type": "rawHtml", "htmlString": "<h1>Test</h1>"},
            "encoding": "text"
        })


def test_empty_uri_error():
    """Test that empty URIs are rejected."""
    from mcp_ui_server import create_ui_resource

    with pytest.raises((InvalidURIError, ValueError)):
        create_ui_resource({
            "uri": "",
            "content": {"type": "rawHtml", "htmlString": "<h1>Test</h1>"},
            "encoding": "text"
        })


def test_ui_resource_structure():
    """Test that UIResource has correct structure for MCP clients."""
    result = test_raw_html()
    ui_resource = result[0]

    # Verify structure matches MCP spec
    assert hasattr(ui_resource, "type")
    assert hasattr(ui_resource, "resource")
    assert hasattr(ui_resource.resource, "uri")
    assert hasattr(ui_resource.resource, "mimeType")
    assert hasattr(ui_resource.resource, "text")

    # Verify URI format
    uri = str(ui_resource.resource.uri)
    assert uri.startswith("ui://")
    assert "//" not in uri.replace("ui://", "", 1)  # No double slashes after scheme


def test_ui_resource_serialization():
    """Test that UIResource can be serialized to dict."""
    result = test_raw_html()
    ui_resource = result[0]

    # Should be able to serialize to dict
    data = ui_resource.model_dump()
    assert isinstance(data, dict)
    assert data["type"] == "resource"
    assert "resource" in data
    assert "uri" in data["resource"]
    assert str(data["resource"]["uri"]).startswith("ui://")
