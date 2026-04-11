# Investigation: QuickBooks MCP `create_purchase` Missing from ToolSearch

## Issue Summary

The `create_purchase` tool from the QuickBooks MCP server is not returned by
`tool_search` in the Claude.ai chat interface. Searching for "create purchase
expense QuickBooks" or "Quickbooks create_purchase" returns `get_purchase`,
`delete_purchase`, and `search_purchases` — but never `create_purchase`.

The tool works correctly in Claude Code, which loads all MCP tools directly
rather than through the deferred ToolSearch mechanism.

**MCP Server:** `https://quickbooks-mcp-cloudflare.curly-tree-8090.workers.dev/mcp`  
**Expected Tool:** `Quickbooks:create_purchase`  
**Also likely affected:** `create_vendor`, `update_purchase`, and other write/create tools

---

## How ToolSearch Works in Claude.ai

Claude.ai uses **deferred tool loading** for MCP servers:

1. On session start, the MCP connector calls `tools/list` on the server
2. Tool **names only** are stored in a search index (not full schemas)
3. When Claude needs a tool, it calls `ToolSearch` with a query
4. ToolSearch performs **BM25 keyword matching** against tool names + descriptions
5. Top 3-5 matching tools are returned with full schemas loaded inline
6. Tool descriptions are **truncated at 2KB** during indexing

This is fundamentally different from Claude Code, which loads all tool schemas
into context directly.

---

## Root Cause Analysis

### Hypothesis 1: MCP Server Pagination Not Followed (MOST LIKELY)

The MCP `tools/list` method supports **cursor-based pagination**. If the
QuickBooks server paginates its tool list across multiple pages, and Claude.ai's
MCP connector only reads the **first page**, tools on subsequent pages would be
silently dropped from the ToolSearch index.

**Evidence:**
- QuickBooks APIs have many operations — the server likely exposes 50+ tools
- `get_purchase`, `delete_purchase`, `search_purchases` appear (likely page 1)
- `create_purchase`, `update_purchase`, `create_vendor` don't appear (likely page 2+)
- The pattern of missing tools (write/create operations) is consistent with
  alphabetical or registration-order pagination

**Diagnostic:** Run `diagnose_mcp_tool_search.py` and check if page 2+ exists.

### Hypothesis 2: Large Schema Rejection

Create/update tools typically have **much larger input schemas** than read/search
tools because they define all writable fields. A `create_purchase` schema might
include `VendorRef`, `Line` (array of line items with nested `AccountRef`,
`Amount`, `Description`, etc.), `TxnDate`, `PaymentType`, etc.

If Claude.ai's tool indexer silently drops tools whose `inputSchema` exceeds a
size threshold, write tools would be systematically excluded.

**Evidence:**
- `get_purchase` schema: ~200 bytes (just `purchase_id`)
- `create_purchase` schema: likely 3,000-8,000 bytes (all QuickBooks fields)
- Read/search tools consistently appear; write/create tools don't

**Diagnostic:** Compare schema sizes in `diagnose_mcp_tool_search.py` output.

### Hypothesis 3: Server-Side Tool Filtering

The MCP server may conditionally filter which tools are exposed based on:
- OAuth scopes (read-only vs read-write tokens)
- Server configuration (tools might need explicit enablement)
- Cloudflare Workers environment variables

**Evidence:**
- Cloudflare MCP servers use `createMcpHandler` which can filter tools
- QuickBooks API has distinct OAuth scopes for read vs write operations

**Diagnostic:** Compare `tools/list` output with and without write OAuth scopes.

### Hypothesis 4: BM25 Search Ranking (LEAST LIKELY)

The BM25 algorithm matches search queries against tool names and descriptions.
If `create_purchase` has a poor description that doesn't contain "purchase",
"expense", or "create", it would rank below other tools.

**Evidence against:** The tool name itself contains "create" and "purchase",
which should match queries like "create purchase" with high BM25 score. This
hypothesis is unlikely unless the tool has no description at all.

---

## Known Related Bugs

- **anthropics/claude-code#25894**: MCP tools not loaded as deferred tools when
  using mcp-remote proxy
- **anthropics/claude-code#26844**: `defer_loading` in `.claude.json` mcpServers
  has no effect
- **anthropics/claude-code#11175**: MCP tools not available to Claude Assistant
  despite being loaded successfully

---

## Recommended Actions

### Immediate (confirm the issue)

```bash
# Run the diagnostic script against the MCP server
python scripts/diagnose_mcp_tool_search.py \
    --url https://quickbooks-mcp-cloudflare.curly-tree-8090.workers.dev/mcp \
    --json-output tools_dump.json
```

### If tools ARE in the server response (platform bug)

1. File a bug against Claude.ai's MCP connector with the `tools_dump.json`
   evidence showing the tool exists in the server response
2. Focus on pagination handling — verify the connector follows `nextCursor`
3. Check if there's a schema size limit that silently drops large tools
4. Request logging/visibility into which tools the connector successfully indexes

### If tools are NOT in the server response (server bug)

1. Check the Cloudflare Worker's tool registration code
2. Verify QuickBooks OAuth token has write scopes
3. Check if `createMcpHandler` configuration filters write operations
4. Add missing tool registrations to the server

### Long-term fixes

1. **MCP server**: Keep tool schemas compact — only include required fields in
   `inputSchema`, use descriptions for optional field documentation
2. **MCP server**: Test pagination by requesting `tools/list` with explicit
   cursor following
3. **Claude.ai**: Request a diagnostic endpoint or logging for MCP tool indexing
   failures (silent drops make debugging impossible)

---

## Diagnostic Script

See `scripts/diagnose_mcp_tool_search.py` — a standalone Python script that:

1. Connects to any MCP server via Streamable HTTP transport
2. Calls `tools/list` with full pagination support
3. Analyzes each tool for schema size, description quality, and naming
4. Checks for expected write/create tools
5. Generates a diagnosis report with root cause identification

No dependencies beyond Python 3 stdlib.
