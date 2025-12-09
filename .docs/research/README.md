# Research Documentation Index

This directory contains research findings, technical investigations, and implementation guides for the scout_mcp project.

## FastMCP Schema Research (2025-12-07)

**Research Question:** Do FastMCP tools returning union types like `list[dict[str, Any]] | str` need custom output schemas?

**Answer:** **NO** - FastMCP automatically generates schemas from type hints.

### Documents

1. **[Quick Reference](./fastmcp-quick-reference.md)** - Start here
   - One-page decision tree
   - Common patterns
   - Quick lookup table

2. **[Code Examples](./fastmcp-union-types-examples.md)** - Concrete implementations
   - 7 working examples
   - Common mistakes
   - Testing patterns

3. **[Detailed Research](./fastmcp-union-type-schemas.md)** - Deep dive
   - How FastMCP generates schemas
   - UIResource type hierarchy
   - Known issues and workarounds
   - Complete documentation links

4. **[Executive Summary](./fastmcp-schema-research-summary.md)** - Management overview
   - Key findings
   - Recommendations
   - Testing checklist

### Key Takeaways

```python
# scout_mcp current implementation - CORRECT ✅
async def scout(...) -> list[dict[str, Any]] | str:
    """No output_schema parameter needed."""
    # FastMCP auto-generates:
    # {
    #   "anyOf": [
    #     {"type": "array", "items": {"type": "object"}},
    #     {"type": "string"}
    #   ]
    # }
    pass
```

**Why it works:**
1. FastMCP supports union types natively
2. Pydantic generates `anyOf` schemas automatically
3. `dict` objects become structured content
4. `str` results become text content
5. UIResource is a dict-compatible type

**No changes needed to scout_mcp implementation.**

## Other Research

### MCP-UI Implementation
- **[mcp-ui-implementation-guide.md](./mcp-ui-implementation-guide.md)** - Integration guide

### Security
- **[security/](./security/)** - Security audits and recommendations

### Performance
- **[performance/](./performance/)** - Performance analysis and benchmarks

### Documentation
- **[documentation/](./documentation/)** - Documentation reviews and standards

## Research Process

When conducting research for this project:

1. **Start with documentation**
   - Official docs (FastMCP, MCP-UI, Pydantic)
   - GitHub issues and discussions
   - Community guides and tutorials

2. **Verify with code inspection**
   - Source code analysis
   - Type hierarchy inspection
   - Runtime behavior testing

3. **Document findings**
   - Create quick reference for daily use
   - Provide code examples for implementation
   - Include detailed research for future reference
   - Write executive summary for stakeholders

4. **Test conclusions**
   - Write tests that validate findings
   - Check edge cases
   - Verify against known issues

## Contributing Research

When adding new research:

1. Create focused documents in appropriate subdirectory
2. Add entry to this index
3. Follow naming convention: `topic-name-YYYY-MM-DD.md`
4. Include:
   - Research question/goal
   - Key findings
   - Code examples
   - References/sources
   - Recommendations

## Tools Used

- **WebSearch** - Documentation and issue tracking
- **WebFetch** - Official docs and GitHub
- **Code inspection** - Source analysis and type checking
- **pytest** - Validation and testing

## Reference Links

### FastMCP
- [FastMCP Documentation](https://gofastmcp.com/servers/tools)
- [FastMCP GitHub](https://github.com/jlowin/fastmcp)
- [FastMCP PyPI](https://pypi.org/project/fastmcp/)

### MCP-UI
- [MCP-UI Documentation](https://mcpui.dev/guide/introduction)
- [MCP-UI GitHub](https://github.com/MCP-UI-Org/mcp-ui)
- [Python Server Guide](https://mcpui.dev/guide/server/python/walkthrough)

### Pydantic
- [Pydantic Docs](https://docs.pydantic.dev/)
- [Schema Generation](https://docs.pydantic.dev/1.10/usage/schema/)

### MCP Protocol
- [MCP Specification](https://modelcontextprotocol.io/)
- [Python SDK](https://github.com/modelcontextprotocol/python-sdk)

## Questions?

For questions about this research:
1. Check [Quick Reference](./fastmcp-quick-reference.md) first
2. Review [Code Examples](./fastmcp-union-types-examples.md)
3. Consult [Detailed Research](./fastmcp-union-type-schemas.md)
4. Open issue if still unclear
