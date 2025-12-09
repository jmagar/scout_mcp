"""MCP-UI test tools demonstrating different content types."""

import logging

from mcp_ui_server import create_ui_resource
from mcp_ui_server.core import UIResource
from mcp_ui_server.exceptions import InvalidURIError

logger = logging.getLogger(__name__)


def test_raw_html() -> list[UIResource]:
    """Test tool that renders raw HTML content.

    Returns a simple HTML page with styled content to verify
    rawHtml rendering in MCP-UI clients.

    Returns:
        List containing a single UIResource with rawHtml content
    """
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Raw HTML Test</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                padding: 24px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .card {
                background: white;
                border-radius: 12px;
                padding: 32px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 600px;
                width: 100%;
            }
            h1 {
                font-size: 32px;
                font-weight: 700;
                color: #1a202c;
                margin-bottom: 16px;
            }
            p {
                font-size: 16px;
                line-height: 1.6;
                color: #4a5568;
                margin-bottom: 12px;
            }
            .badge {
                display: inline-block;
                background: #667eea;
                color: white;
                padding: 6px 12px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
                margin-top: 16px;
            }
            .grid {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 16px;
                margin-top: 24px;
            }
            .box {
                background: #f7fafc;
                padding: 20px;
                border-radius: 8px;
                text-align: center;
                border: 2px solid #e2e8f0;
            }
            .box-title {
                font-weight: 600;
                color: #2d3748;
                margin-bottom: 8px;
            }
            .box-value {
                font-size: 24px;
                font-weight: 700;
                color: #667eea;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🎨 Raw HTML Test</h1>
            <p>This is a <strong>rawHtml</strong> content type demonstration.</p>
            <p>If you can see this styled content with gradient background,
               the MCP-UI rendering is working correctly!</p>
            <span class="badge">✓ Rendering Active</span>

            <div class="grid">
                <div class="box">
                    <div class="box-title">Content Type</div>
                    <div class="box-value">rawHtml</div>
                </div>
                <div class="box">
                    <div class="box-title">Framework</div>
                    <div class="box-value">MCP-UI</div>
                </div>
                <div class="box">
                    <div class="box-title">Status</div>
                    <div class="box-value">✓</div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        logger.debug("Creating rawHtml UIResource with URI: ui://scout/test/raw-html")
        ui_resource = create_ui_resource({
            "uri": "ui://scout/test/raw-html",
            "content": {"type": "rawHtml", "htmlString": html},
            "encoding": "text"
        })
        logger.info(
            "Successfully created rawHtml UIResource (URI: %s, content_length: %d bytes)",
            ui_resource.resource.uri,
            len(html)
        )
        return [ui_resource]
    except InvalidURIError as e:
        logger.error("Invalid URI format for rawHtml test: %s", e)
        raise
    except Exception as e:
        logger.exception("Unexpected error creating rawHtml UIResource: %s", e)
        raise


def test_remote_dom() -> list[UIResource]:
    """Test tool that renders using remoteDom (JavaScript).

    Returns a UIResource that executes JavaScript to dynamically
    build DOM elements using the MCP-UI remoteDom API.

    Returns:
        List containing a single UIResource with remoteDom content
    """
    # JavaScript that creates DOM elements using MCP-UI's remoteDom API
    js_code = """
    // Create card container
    const card = createElement('Card', {
        style: {
            padding: '32px',
            maxWidth: '600px',
            margin: '24px auto',
            background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
            borderRadius: '12px',
            boxShadow: '0 20px 60px rgba(0,0,0,0.3)'
        }
    });

    // Create stack for vertical layout
    const stack = createElement('Stack', {
        direction: 'vertical',
        spacing: 16,
        style: { background: 'white', padding: '24px', borderRadius: '8px' }
    });

    // Title
    const title = createElement('Text', {
        content: '🔮 Remote DOM Test',
        variant: 'title',
        style: { fontSize: '32px', fontWeight: '700', color: '#1a202c' }
    });

    // Description
    const desc = createElement('Text', {
        content: 'This content is dynamically created using JavaScript and the remoteDom API.',
        style: { fontSize: '16px', color: '#4a5568', lineHeight: '1.6' }
    });

    // Badge
    const badge = createElement('Text', {
        content: '✓ JavaScript Executed',
        style: {
            display: 'inline-block',
            background: '#f5576c',
            color: 'white',
            padding: '8px 16px',
            borderRadius: '6px',
            fontSize: '14px',
            fontWeight: '600'
        }
    });

    // Info boxes
    const infoStack = createElement('Stack', {
        direction: 'horizontal',
        spacing: 12,
        style: { marginTop: '16px' }
    });

    ['remoteDom', 'React', 'Dynamic'].forEach(label => {
        const box = createElement('Card', {
            style: {
                flex: 1,
                padding: '16px',
                textAlign: 'center',
                background: '#f7fafc',
                border: '2px solid #e2e8f0'
            }
        });

        const text = createElement('Text', {
            content: label,
            style: { fontWeight: '600', color: '#667eea' }
        });

        appendChild(box, text);
        appendChild(infoStack, box);
    });

    // Build DOM tree
    appendChild(stack, title);
    appendChild(stack, desc);
    appendChild(stack, badge);
    appendChild(stack, infoStack);
    appendChild(card, stack);

    return card;
    """

    try:
        logger.debug("Creating remoteDom UIResource with URI: ui://scout/test/remote-dom")
        ui_resource = create_ui_resource({
            "uri": "ui://scout/test/remote-dom",
            "content": {
                "type": "remoteDom",
                "script": js_code,
                "framework": "react"
            },
            "encoding": "text"
        })
        logger.info(
            "Successfully created remoteDom UIResource (URI: %s, script_length: %d bytes)",
            ui_resource.resource.uri,
            len(js_code)
        )
        return [ui_resource]
    except InvalidURIError as e:
        logger.error("Invalid URI format for remoteDom test: %s", e)
        raise
    except Exception as e:
        logger.exception("Unexpected error creating remoteDom UIResource: %s", e)
        raise


def test_external_url() -> list[UIResource]:
    """Test tool that renders an external URL in iframe.

    Returns a UIResource that loads an external website
    in a sandboxed iframe.

    Returns:
        List containing a single UIResource with externalUrl content
    """
    try:
        logger.debug("Creating externalUrl UIResource with URI: ui://scout/test/external-url")
        ui_resource = create_ui_resource({
            "uri": "ui://scout/test/external-url",
            "content": {
                "type": "externalUrl",
                "iframeUrl": "https://example.com",
                "cssProps": {
                    "width": "100%",
                    "height": "600px",
                    "border": "2px solid #e2e8f0",
                    "borderRadius": "8px"
                }
            },
            "encoding": "text"
        })
        logger.info(
            "Successfully created externalUrl UIResource (URI: %s, target: %s)",
            ui_resource.resource.uri,
            "https://example.com"
        )
        return [ui_resource]
    except InvalidURIError as e:
        logger.error("Invalid URI format for externalUrl test: %s", e)
        raise
    except Exception as e:
        logger.exception("Unexpected error creating externalUrl UIResource: %s", e)
        raise
