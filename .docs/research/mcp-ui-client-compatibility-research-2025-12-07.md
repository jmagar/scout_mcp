# MCP-UI Client Support and Compatibility Research
**Date:** 2025-12-07
**Research Focus:** MCP-UI format support across different MCP clients

## Executive Summary

MCP-UI is an experimental extension to the Model Context Protocol that enables interactive user interfaces within MCP clients. As of December 2025, support varies significantly across clients, with multiple competing specifications and MIME type variations. The ecosystem is in active development with ongoing standardization efforts through SEP-1865 (MCP Apps Extension).

### Key Findings

1. **Multiple UI Protocols Exist:**
   - MCP-UI (community-driven, most mature)
   - OpenAI Apps SDK (`text/html+skybridge`)
   - MCP Apps Extension SEP-1865 (`text/html;profile=mcp-app`)

2. **Limited Client Support:**
   - Only 7 clients have native MCP-UI support
   - Most major clients (Claude Desktop, Cline, Cursor) do NOT support MCP-UI rendering
   - text/html is NOT universally supported

3. **MCPJam Inspector supports OpenAI Apps SDK** format with iframe rendering (beta)

4. **Recommendation:** For maximum compatibility, provide text-only fallbacks. UI features should be optional enhancements.

---

## MCP-UI Format Specifications

### Three MIME Type Formats

MCP-UI defines three distinct content delivery methods:

#### 1. `text/html` - Inline HTML via iframe srcdoc

**Description:** HTML content rendered in sandboxed iframe using `srcdoc` attribute

**Use Cases:**
- Custom buttons and forms
- Data visualizations
- Interactive widgets

**Example:**
```json
{
  "uri": "ui://my-app/form",
  "mimeType": "text/html",
  "text": "<html><body><button>Click Me</button></body></html>"
}
```

**Security:** Sandboxed iframe with restricted permissions

**Support:** Highest compatibility among MCP-UI clients

---

#### 2. `text/uri-list` - External URL via iframe src

**Description:** Renders external URL content in sandboxed iframe using `src` attribute

**Use Cases:**
- External dashboards
- Third-party widgets
- Mini-applications

**Format:** RFC 2483 URI list format
- Comments start with `#`
- Blank lines ignored
- Only first valid HTTP/HTTPS URL used

**Example:**
```json
{
  "uri": "ui://dashboard/analytics",
  "mimeType": "text/uri-list",
  "text": "https://analytics.example.com/dashboard"
}
```

**Security Requirements:**
- HTTPS/HTTP only (enforced)
- Single URL (multiple URLs trigger warning)
- CSP restrictions may apply

**Limitations:** May require proxy to comply with host's Content Security Policy (CSP)

---

#### 3. `application/vnd.mcp-ui.remote-dom` - Component-based UI

**Description:** JavaScript-defined UI using Shopify's remote-dom library, rendered with host-native components

**Variants:**
- `application/vnd.mcp-ui.remote-dom+javascript;framework=react`
- `application/vnd.mcp-ui.remote-dom+javascript;framework=webcomponents`

**Use Cases:**
- Components matching host's visual design
- Native look-and-feel integration
- Type-safe component libraries

**Architecture:**
1. Server provides JavaScript describing UI and events
2. Script executes in sandboxed iframe
3. UI changes communicated to host as JSON
4. Host renders using its component library

**Advantages:**
- Inherits host's styling
- More flexible than iframes
- Type-safe interactions

**Example:**
```typescript
// Server response
{
  "uri": "ui://product/card",
  "mimeType": "application/vnd.mcp-ui.remote-dom+javascript;framework=react",
  "text": "// JavaScript defining RemoteDOMRoot and components"
}
```

**Supported Components:**
- `ui-button` - Interactive buttons
- Text and typography elements
- Stack layouts
- Custom components via host implementation

**Security:** Sandboxed iframe execution with JSON-RPC communication

**Limitations:** Requires host to implement RemoteDOMResourceRenderer component

---

## Protocol Variants and Specifications

### MCP-UI (Community Standard)

**Status:** Experimental, community-driven
**URI Scheme:** `ui://`
**MIME Types:** `text/html`, `text/uri-list`, `application/vnd.mcp-ui.remote-dom`
**Website:** https://mcpui.dev
**Documentation:** https://mcpui.dev/guide/introduction

**Packages:**
- `@mcp-ui/client` (React + Web Components)
- `@mcp-ui/server` (TypeScript server SDK)
- `mcp-ui-server` (Ruby gem)
- `mcp-ui` (Python package)

**Supported Hosts:** See Client Compatibility Matrix below

---

### OpenAI Apps SDK

**Status:** Production, ChatGPT-specific
**URI Scheme:** `ui://`
**MIME Type:** `text/html+skybridge`
**Documentation:** https://developers.openai.com/apps-sdk

**Architecture:**
1. MCP server defines tools with UI bundle references
2. Each UI resource uses MIME type `text/html+skybridge`
3. ChatGPT loads HTML in iframe with widget runtime injected
4. Communication via `window.openai.toolOutput` object

**Key Difference from MCP-UI:**
- Proprietary `+skybridge` suffix
- ChatGPT-specific runtime injection
- Different communication protocol

**Example:**
```json
{
  "uri": "ui://weather/widget",
  "mimeType": "text/html+skybridge",
  "text": "<html><!-- Widget HTML with Apps SDK runtime --></html>"
}
```

**Support:** ChatGPT only (via Developer Mode)

---

### MCP Apps Extension (SEP-1865)

**Status:** Draft proposal (November 2025)
**URI Scheme:** `ui://`
**MIME Type:** `text/html;profile=mcp-app`
**Specification:** https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1865
**Official Repo:** https://github.com/modelcontextprotocol/ext-apps

**Design Goals:**
- Unify MCP-UI and OpenAI Apps SDK patterns
- Standardize UI extension as official MCP specification
- Maintain backward compatibility

**Key Features:**
1. **Predeclared UI Resources** - Resources declared separately from tool results
2. **Bidirectional Communication** - JSON-RPC messaging between UI and host
3. **Security Model** - Mandatory iframe sandboxing, auditable messages
4. **Resource Discovery** - Tools reference UI via metadata

**MIME Type Rationale:**
Initial proposal used `text/html+mcp` but switched to `text/html;profile=mcp-app` following RFC 6906 guidelines after IANA media type reviewer feedback. The `profile` parameter allows HTML to be "processed using MCP semantics while maintaining standard HTML processing capabilities."

**Current Scope (MVP):**
- HTML-only (`text/html;profile=mcp-app`)
- Sandboxed iframes
- JSON-RPC communication

**Explicitly Deferred to Future:**
- External URLs (`text/uri-list`)
- Remote DOM rendering
- Native widgets
- State persistence
- Context update mechanisms
- Host-to-UI updates

**Authors:** MCP Core Maintainers (OpenAI + Anthropic) + MCP-UI creators + UI Community Working Group leads

**Status as of Dec 2025:** Draft proposal under discussion, not yet adopted

---

## Client Compatibility Matrix

### Native MCP-UI Support

Based on mcpui.dev documentation as of December 2025:

| Client | Rendering | UI Actions | Notes | URL |
|--------|-----------|------------|-------|-----|
| **Nanobot** | ✅ Full | ✅ Full | Complete MCP-UI support | - |
| **Postman** | ✅ Full | ⚠️ Partial | Rendering works, limited actions | - |
| **Goose** | ✅ Full | ⚠️ Partial | Open source AI agent, CLI-based | https://block.github.io/goose |
| **LibreChat** | ✅ Full | ⚠️ Partial | Enhanced ChatGPT clone, multi-user | https://www.librechat.ai |
| **Smithery** | ✅ Full | ❌ None | Rendering only, no interactions | - |
| **MCPJam Inspector** | ✅ Full | ❌ None | Testing tool, rendering only | https://docs.mcpjam.com |
| **fast-agent** | ✅ Full | ❌ None | Rendering only | https://fast-agent.ai |
| **VSCode** | ❓ TBA | ❓ TBA | Coming soon | - |

**Legend:**
- ✅ Full Support
- ⚠️ Partial Support
- ❌ No Support / Rendering Only
- ❓ Status Unknown / Coming Soon

---

### Protocol Adapter Support

Two clients use protocol adapters to translate between protocols:

| Client | Protocol | MIME Type | Adapter | Notes |
|--------|----------|-----------|---------|-------|
| **ChatGPT** | Apps SDK | `text/html+skybridge` | Yes | MCP-UI → Apps SDK translation |
| **MCP Apps SEP Hosts** | MCP Apps | `text/html;profile=mcp-app` | Yes | Future adoption |

**Adapter Functionality:**
- Automatically translates MCP-UI `postMessage` protocol to host-specific APIs
- Switches MIME types (`text/html` → `text/html+skybridge`)
- Injects host-specific runtime (e.g., Apps SDK bridge script)
- Over time, as hosts adopt open spec, adapters become unnecessary

---

### Major Clients WITHOUT MCP-UI Support

**Important:** The following popular MCP clients do NOT support MCP-UI rendering:

| Client | MCP Support | UI Support | Type | Notes |
|--------|-------------|------------|------|-------|
| **Claude Desktop** | ✅ Full | ❌ No UI | Desktop App | Resources listed but not rendered |
| **Claude Code** | ✅ Full | ❌ No UI | CLI/Agent | Text-only interactions |
| **Cline** | ⚠️ Partial | ❌ No UI | VSCode Extension | Resources + Tools only |
| **Cursor** | ✅ Full | ❌ No UI | IDE | Native MCP, no UI rendering |
| **Continue** | ✅ Full | ❌ No UI | IDE Extension | MCP support, no UI |

**Known Issues:**
- **Claude Desktop:** Resources are discovered and listed in Settings → Integrations → [Server] → PROVIDED RESOURCES, but not actually rendered or used in responses
- **Cline:** Supports MCP Resources and Tools (3/7 MCP concepts), but no UI rendering
- **MCP Apps Extension:** Still in proposal stage, not yet adopted by major clients

---

### Client Feature Support (MCP Protocol)

Source: https://mcp-availability.com

MCP defines 7 core concepts. UI rendering is NOT part of the core protocol.

| Client | Resources | Prompts | Tools | Sampling | Roots | Discovery | Elicitation | UI |
|--------|-----------|---------|-------|----------|-------|-----------|-------------|-----|
| **Claude Desktop** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Claude Code** | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| **Cline** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **MCPOmni-Connect** | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **systemprompt** | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Amp** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

---

## MCPJam Inspector Implementation Details

**Website:** https://www.mcpjam.com
**Documentation:** https://docs.mcpjam.com
**GitHub:** https://github.com/MCPJam/inspector
**Status:** Beta (as of December 2025)

### OpenAI Apps SDK Support

MCPJam Inspector is positioned as "the only local-first OpenAI app emulator" for testing Apps SDK servers without requiring:
- ChatGPT Developer Mode access
- ngrok tunneling
- Production deployment

**Architecture:**
1. MCP server defines tools with UI resources
2. Resources contain raw HTML (MIME type: `text/html+skybridge`)
3. MCPJam loads resource into iframe
4. React components compiled to JS and loaded into iframe
5. UI rendered as interactive widget

**Workflow:**
1. Connect to MCP server via SSE (Server-Sent Events)
2. Navigate to Tools tab
3. Invoke a tool (e.g., Pizza tool)
4. View rendered UI in bottom panel

**Supported Format:**
- `text/html+skybridge` (OpenAI Apps SDK format)
- iframe-based rendering
- Widget data model

**Current Limitations (Beta):**
- LLM playground features still buggy
- Apps SDK support incomplete
- Ongoing polishing needed

**Key Features:**
- Local development without ngrok
- Visual tool testing (Postman for MCP)
- SSE transport support
- Widget preview

**Testing Process:**
```bash
# Clone Apps SDK examples
git clone https://github.com/openai/openai-apps-sdk-examples

# Run local MCP server
# ...

# Connect to MCPJam Inspector via SSE
# Invoke tools and view rendered UI
```

---

## Relationship Between MCP-UI and OpenAI Apps SDK

### Convergence Through SEP-1865

The MCP Apps Extension (SEP-1865) represents a **synthesis** of architectural patterns from both:

**From MCP-UI:**
- Bidirectional communication model
- HTML/external URL support
- Remote DOM patterns
- Component-based architecture
- Security model (sandboxed iframes)

**From OpenAI Apps SDK:**
- Validation of demand for rich UI in conversational interfaces
- Production usage patterns
- Platform adoption proof (Postman, HuggingFace, Shopify)
- `text/html+skybridge` MIME type precedent

**Goal:** "Unifying them into a single, open standard" while maintaining backward compatibility

### Current State (Dec 2025)

**MCP-UI:**
- Community-driven
- 7 native clients
- Multiple MIME types
- Active development
- Experimental status

**OpenAI Apps SDK:**
- ChatGPT-specific
- Production-ready
- Proprietary extensions
- `text/html+skybridge` format
- Limited to ChatGPT ecosystem

**MCP Apps Extension (SEP-1865):**
- Draft proposal
- Not yet adopted
- HTML-only (MVP)
- Future: URL, RemoteDOM, widgets
- Backed by OpenAI + Anthropic + community

### Migration Path

**For Server Developers:**
1. Implement MCP-UI for maximum client support today
2. Use adapters for ChatGPT compatibility (`text/html+skybridge`)
3. Monitor SEP-1865 adoption
4. Plan migration to `text/html;profile=mcp-app` when standardized

**For Client Developers:**
1. Implement MCP-UI protocol for immediate compatibility
2. Add adapter support for Apps SDK if ChatGPT integration needed
3. Track SEP-1865 standardization progress
4. Plan migration to official MCP Apps Extension

---

## Technical Architecture Details

### Security Model

All UI implementations share common security principles:

**1. Iframe Sandboxing**
```html
<iframe
  sandbox="allow-scripts allow-same-origin"
  srcdoc="<!-- UI content -->"
></iframe>
```

**Restricted Permissions:**
- No top-level navigation
- No popup windows
- No form submission to external URLs
- Limited plugin access

**2. Content Security Policy (CSP)**
- External URLs may be blocked
- Proxy servers often required for `text/uri-list`
- Host controls CSP rules

**3. Predeclared Resources**
- UI templates declared separately from tool results
- Hosts can review HTML before rendering
- Prevents dynamic code injection

**4. Auditable Communication**
- All UI-to-host messages via JSON-RPC
- Loggable protocol
- Explicit approval for tool calls from UI

### Communication Protocols

**MCP-UI (postMessage):**
```typescript
// UI → Host
window.parent.postMessage({
  type: 'mcp-ui/action',
  payload: { action: 'submit', data: {...} }
}, '*');

// Host → UI
window.addEventListener('message', (event) => {
  if (event.data.type === 'mcp-ui/response') {
    // Handle response
  }
});
```

**OpenAI Apps SDK (window.openai):**
```typescript
// Access tool output
const output = window.openai.toolOutput;

// Call tools
window.openai.callTool('toolName', { params });

// Update UI
window.openai.updateWidget({ status: 'loading' });
```

**MCP Apps Extension (JSON-RPC):**
```json
// UI → Host
{
  "jsonrpc": "2.0",
  "method": "mcp/call_tool",
  "params": {
    "name": "submit_form",
    "arguments": { "field": "value" }
  },
  "id": 1
}

// Host → UI
{
  "jsonrpc": "2.0",
  "result": { "success": true },
  "id": 1
}
```

### Resource Declaration Examples

**MCP-UI:**
```typescript
import { createUIResource } from '@mcp-ui/server';

const resource = createUIResource({
  uri: 'ui://myapp/widget',
  name: 'My Widget',
  description: 'Interactive form',
  mimeType: 'text/html',
  text: '<html>...</html>'
});
```

**OpenAI Apps SDK:**
```typescript
// Resource metadata in tool definition
{
  name: 'create_pizza',
  description: 'Order a pizza',
  // ...
  openai: {
    outputTemplate: 'ui://pizza/widget'
  }
}

// Resource definition
{
  uri: 'ui://pizza/widget',
  mimeType: 'text/html+skybridge',
  text: '<html><!-- Widget with Apps SDK runtime --></html>'
}
```

**MCP Apps Extension:**
```typescript
// Resource declaration
{
  uri: 'ui://weather/widget',
  name: 'Weather Widget',
  description: 'Interactive weather display',
  mimeType: 'text/html;profile=mcp-app',
  text: '<html>...</html>'
}

// Tool metadata
{
  name: 'get_weather',
  description: 'Get weather info',
  // ...
  ui: {
    template: 'ui://weather/widget'
  }
}
```

---

## Recommendations for Maximum Compatibility

### For Server Developers

**1. Always Provide Text Fallbacks**
```typescript
function handleToolCall(params) {
  const result = {
    // Text response for all clients
    content: [
      {
        type: 'text',
        text: 'Order created: Pizza Margherita, $12.99'
      }
    ]
  };

  // Optional UI resource for compatible clients
  if (clientSupportsUI) {
    result.ui = {
      uri: 'ui://pizza/confirmation',
      mimeType: 'text/html',
      text: '<html><!-- Rich UI --></html>'
    };
  }

  return result;
}
```

**2. Use MCP-UI for Broadest Support**
- 7 native clients vs 1 for Apps SDK
- Clear migration path to SEP-1865
- Active community development
- Multiple language SDKs

**3. Implement Adapters for ChatGPT**
```typescript
import { createAppsSDKAdapter } from '@mcp-ui/server';

// Automatic translation to text/html+skybridge
const adapter = createAppsSDKAdapter(mcpUIResource);
```

**4. Feature Detection**
```typescript
// Check client capabilities
const capabilities = client.getCapabilities();

if (capabilities.ui?.supported) {
  // Provide UI resources
  return enhancedResponse;
} else {
  // Text-only response
  return textResponse;
}
```

**5. Progressive Enhancement**
- Core functionality works without UI
- UI adds better UX, not required features
- Graceful degradation for unsupported clients

### For Client Developers

**1. Implement MCP-UI Protocol First**
- Largest server ecosystem
- Well-documented SDKs
- Active community support
- React + Web Component libraries available

**2. Add Apps SDK Adapter (Optional)**
- Only if ChatGPT compatibility needed
- Use existing adapter libraries
- Automatic MIME type translation

**3. Support All Three MIME Types**
```typescript
switch (resource.mimeType) {
  case 'text/html':
    return renderInlineHTML(resource.text);

  case 'text/uri-list':
    return renderExternalURL(resource.text);

  case 'application/vnd.mcp-ui.remote-dom':
    return renderRemoteDOM(resource.text);

  default:
    return renderTextFallback(resource);
}
```

**4. Security Best Practices**
- Always use sandboxed iframes
- Implement CSP restrictions
- Audit all UI-to-host messages
- Require user approval for sensitive actions

**5. Track SEP-1865 Standardization**
- Monitor https://github.com/modelcontextprotocol/ext-apps
- Plan migration to `text/html;profile=mcp-app`
- Participate in UI Community Working Group discussions

---

## Version History and Specifications

### MCP Protocol Versions

**Latest Stable:** 2025-11-25 (First Anniversary Release)
**Documentation:** https://modelcontextprotocol.io/specification/2025-11-25

**Notable Versions:**
- **2025-11-25** - First anniversary, SEP-1865 introduced
- **2025-06-18** - Structured Tool Output, Elicitation Support, OAuth updates
- **2025-03-26** - Earlier stable release

### MCP-UI Versions

**Status:** No formal version numbers
**Release Model:** Rolling releases via npm packages

**Current Packages (Dec 2025):**
- `@mcp-ui/client` - TypeScript client SDK
- `@mcp-ui/server` - TypeScript server SDK
- `mcp-ui-server` - Ruby gem
- `mcp-ui` - Python package

**Specification Status:** Experimental, not part of official MCP spec (yet)

### OpenAI Apps SDK

**Status:** Production (ChatGPT only)
**Documentation:** https://developers.openai.com/apps-sdk
**Version:** No public version numbers

### MCP Apps Extension (SEP-1865)

**Status:** Draft Proposal (November 2025)
**Pull Request:** https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1865
**Repository:** https://github.com/modelcontextprotocol/ext-apps

**Proposal Timeline:**
- Introduced: November 21, 2025
- Authors: OpenAI + Anthropic Core Maintainers + MCP-UI creators
- Status: Under discussion, not yet adopted
- Target: Future MCP specification update

---

## Unresolved Issues and Future Development

### Known Gaps in SEP-1865

As identified in PR discussions:

**1. Context Update Mechanisms**
- Problem: How does UI state flow to agent without triggering inference?
- Example: User updates form, agent needs context but shouldn't respond yet
- Status: Deferred to future iterations

**2. State Persistence**
- Problem: How to maintain UI state across conversation sessions?
- Example: User closes chat, reopens - widget state lost
- Status: Not addressed in MVP

**3. Widget State Management**
- Problem: How to rehydrate widget state after page reload?
- Example: Multi-step form progress lost on refresh
- Status: Host-specific implementations vary

**4. Host-to-UI Updates**
- Problem: How does host update UI when subsequent tool calls modify data?
- Example: Agent calls tool to update order, confirmation widget needs refresh
- Status: No standardized pattern

**5. Bidirectional Data Flow**
- Problem: Complex workflows requiring multiple UI ↔ Agent interactions
- Example: Wizard with agent-assisted steps
- Status: Under discussion

### Future Extensions

**Planned for post-MVP:**
- External URL support (`text/uri-list`)
- Remote DOM rendering (`application/vnd.mcp-ui.remote-dom`)
- Native widgets (platform-specific components)
- State synchronization protocol
- Multi-widget coordination
- Rich media types (video, audio, canvas)

**Community Requests:**
- WebSocket support for real-time updates
- File upload/download from widgets
- Clipboard integration
- Accessibility improvements
- Mobile-optimized components

---

## Quick Reference

### Which Format to Use?

| Goal | Format | MIME Type | Notes |
|------|--------|-----------|-------|
| **Maximum compatibility** | MCP-UI HTML | `text/html` | 7 clients support |
| **ChatGPT integration** | Apps SDK | `text/html+skybridge` | ChatGPT only |
| **Future-proof** | MCP Apps | `text/html;profile=mcp-app` | When SEP-1865 adopted |
| **Native styling** | Remote DOM | `application/vnd.mcp-ui.remote-dom` | Limited support |
| **External services** | URI List | `text/uri-list` | CSP issues |

### Which Clients Support UI?

| Client | Support | Format | Notes |
|--------|---------|--------|-------|
| **ChatGPT** | ✅ Via Apps SDK | `text/html+skybridge` | Production |
| **Goose** | ✅ MCP-UI | `text/html`, etc. | Partial actions |
| **LibreChat** | ✅ MCP-UI | `text/html`, etc. | Partial actions |
| **MCPJam Inspector** | ✅ Apps SDK | `text/html+skybridge` | Testing only |
| **Claude Desktop** | ❌ | - | Resources listed, not rendered |
| **Cline** | ❌ | - | No UI rendering |
| **Cursor** | ❌ | - | No UI rendering |

### Testing Your MCP-UI Implementation

**1. Test with MCPJam Inspector (Apps SDK format):**
```bash
# Clone inspector or use hosted version
# Configure SSE connection
# Invoke tools and verify iframe rendering
```

**2. Test with Goose (MCP-UI format):**
```bash
# Install Goose
# Add MCP server to extensions
# Invoke tool and verify UI rendering
```

**3. Test with LibreChat (MCP-UI format):**
```bash
# Deploy LibreChat instance
# Configure MCP server in YAML
# Test multi-user UI isolation
```

**4. Verify Fallback Behavior (Claude Desktop):**
```bash
# Add MCP server to claude_desktop_config.json
# Verify text-only responses work
# Check Settings → Integrations for resource listing
```

---

## Additional Resources

### Official Documentation

- **MCP Specification:** https://modelcontextprotocol.io/specification
- **MCP Clients:** https://modelcontextprotocol.io/clients
- **MCP-UI Website:** https://mcpui.dev
- **MCP-UI Getting Started:** https://mcpui.dev/guide/getting-started
- **MCP-UI Protocol Details:** https://mcpui.dev/guide/protocol-details
- **MCP-UI Supported Hosts:** https://mcpui.dev/guide/supported-hosts
- **OpenAI Apps SDK:** https://developers.openai.com/apps-sdk
- **MCPJam Inspector:** https://docs.mcpjam.com

### GitHub Repositories

- **MCP Core:** https://github.com/modelcontextprotocol/modelcontextprotocol
- **SEP-1865 (MCP Apps):** https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1865
- **MCP Apps Extension:** https://github.com/modelcontextprotocol/ext-apps
- **MCP-UI:** https://github.com/MCP-UI-Org/mcp-ui
- **MCPJam Inspector:** https://github.com/MCPJam/inspector
- **OpenAI Apps SDK Examples:** https://github.com/openai/openai-apps-sdk-examples

### NPM Packages

- **@mcp-ui/client:** https://www.npmjs.com/package/@mcp-ui/client
- **@mcp-ui/server:** https://www.npmjs.com/package/@mcp-ui/server
- **@postman/mcp-ui-client:** https://www.npmjs.com/package/@postman/mcp-ui-client

### Community Resources

- **MCP Availability (Compatibility Matrix):** https://mcp-availability.com
- **MCP Index:** https://mcpindex.net
- **MCP Market:** https://mcpmarket.com
- **PulseMCP Clients:** https://www.pulsemcp.com/clients
- **Awesome MCP Clients:** https://github.com/punkpeye/awesome-mcp-clients
- **MCP Client Capabilities:** https://github.com/apify/mcp-client-capabilities

### Blog Posts and Guides

- **MCP Apps Announcement:** http://blog.modelcontextprotocol.io/posts/2025-11-21-mcp-apps/
- **MCP UI (Shopify Engineering):** https://shopify.engineering/mcp-ui-breaking-the-text-wall
- **Building with Apps SDK (MCPJam):** https://www.mcpjam.com/blog/apps-sdk
- **MCP-UI Technical Overview (WorkOS):** https://workos.com/blog/mcp-ui-a-technical-deep-dive-into-interactive-agent-interfaces
- **MCP UI with Goose:** https://block.github.io/goose/blog/2025/08/11/mcp-ui-post-browser-world/

---

## Conclusion

### Current State (December 2025)

**MCP-UI is NOT universally supported.** Only 7 clients have native support, and major clients like Claude Desktop, Cline, and Cursor do NOT render UI resources.

**Key Takeaways:**

1. **Multiple competing standards exist:**
   - MCP-UI (community, 7 clients)
   - OpenAI Apps SDK (ChatGPT only)
   - MCP Apps Extension (draft proposal)

2. **text/html is NOT universal:**
   - Works in MCP-UI clients
   - Requires `+skybridge` suffix for ChatGPT
   - Will use `;profile=mcp-app` in SEP-1865
   - Not supported in Claude Desktop, Cline, Cursor

3. **MCPJam Inspector supports Apps SDK format:**
   - Beta support for `text/html+skybridge`
   - iframe-based rendering
   - Testing tool, not production client

4. **Standardization in progress:**
   - SEP-1865 aims to unify approaches
   - HTML-only MVP, other formats deferred
   - Adoption timeline unclear

### Recommendations

**For Server Developers:**
- ✅ **Always provide text fallbacks**
- ✅ Use MCP-UI for maximum compatibility (7 clients)
- ✅ Add Apps SDK adapter if ChatGPT needed
- ✅ Monitor SEP-1865 for standardization
- ❌ Don't rely on UI features for core functionality

**For Client Developers:**
- ✅ Implement MCP-UI protocol for broad compatibility
- ✅ Support all three MIME types (HTML, URI, RemoteDOM)
- ✅ Use sandboxed iframes for security
- ✅ Track SEP-1865 adoption progress
- ⚠️ Consider Apps SDK adapter for ChatGPT compatibility

**For Testing:**
- Use MCPJam Inspector for Apps SDK format
- Use Goose or LibreChat for MCP-UI format
- Test fallback behavior with Claude Desktop
- Verify security with sandboxed rendering

### Future Outlook

The MCP-UI ecosystem is actively evolving. SEP-1865 represents a significant step toward standardization, backed by both OpenAI and Anthropic. However, widespread adoption will take time, and servers must continue supporting text-only fallbacks for the foreseeable future.

**Timeline Expectations:**
- **Short term (Q1 2025):** MCP-UI remains dominant for UI-enabled clients
- **Medium term (Q2-Q3 2025):** SEP-1865 adoption begins if approved
- **Long term (Q4 2025+):** Unified standard emerges, broader client support

**Watch for:**
- SEP-1865 approval and merge into MCP spec
- Major client adoption announcements
- Migration guides from MCP-UI to MCP Apps
- Extended format support (URLs, RemoteDOM, widgets)

---

## Sources and Citations

This research compiled information from the following sources:

### Official Documentation
- [Model Context Protocol - Example Clients](https://modelcontextprotocol.io/clients)
- [MCP-UI Introduction](https://mcpui.dev/guide/introduction)
- [MCP-UI Protocol Details](https://mcpui.dev/guide/protocol-details)
- [MCP-UI Supported Hosts](https://mcpui.dev/guide/supported-hosts)
- [OpenAI Apps SDK - Build MCP Server](https://developers.openai.com/apps-sdk/build/mcp-server/)
- [MCP Apps Blog Post](http://blog.modelcontextprotocol.io/posts/2025-11-21-mcp-apps/)
- [MCPJam Inspector Documentation](https://docs.mcpjam.com)
- [MCPJam Apps SDK Guide](https://www.mcpjam.com/blog/apps-sdk)

### GitHub Resources
- [MCP-UI Repository](https://github.com/MCP-UI-Org/mcp-ui)
- [SEP-1865 Pull Request](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1865)
- [MCP Apps Extension Repository](https://github.com/modelcontextprotocol/ext-apps)
- [MCPJam Inspector Repository](https://github.com/MCPJam/inspector)
- [MCP Client Capabilities](https://github.com/apify/mcp-client-capabilities)
- [Awesome MCP Clients](https://github.com/punkpeye/awesome-mcp-clients)

### Community Resources
- [MCP Availability - Compatibility Matrix](https://mcp-availability.com/)
- [LibreChat MCP Documentation](https://www.librechat.ai/docs/features/mcp)
- [Shopify Engineering - MCP UI](https://shopify.engineering/mcp-ui-breaking-the-text-wall)
- [WorkOS - MCP-UI Technical Overview](https://workos.com/blog/mcp-ui-a-technical-deep-dive-into-interactive-agent-interfaces)
- [Goose - MCP UI Blog](https://block.github.io/goose/blog/2025/08/11/mcp-ui-post-browser-world/)

### Package Registries
- [@mcp-ui/client on npm](https://www.npmjs.com/package/@mcp-ui/client)
- [@mcp-ui/server on npm](https://www.npmjs.com/package/@mcp-ui/server)
- [@postman/mcp-ui-client on npm](https://www.npmjs.com/package/@postman/mcp-ui-client)

---

**Research Date:** December 7, 2025
**Document Version:** 1.0
**Last Updated:** 2025-12-07
