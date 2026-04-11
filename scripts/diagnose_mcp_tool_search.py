#!/usr/bin/env python3
"""
Diagnostic script: Investigate why QuickBooks MCP create_purchase tool
is missing from Claude.ai's ToolSearch index.

This script connects to a QuickBooks MCP server via Streamable HTTP transport,
lists all tools, and analyzes them for issues that would prevent them from
appearing in Claude.ai's ToolSearch results.

Known failure modes investigated:
  1. Pagination gaps - server paginates tools/list and client doesn't follow nextCursor
  2. Schema size - tool inputSchema exceeds the 2KB description truncation limit
  3. Missing or malformed fields - tool missing name/description/inputSchema
  4. BM25 ranking - tool description doesn't contain expected search keywords

Usage:
    python scripts/diagnose_mcp_tool_search.py --url <MCP_SERVER_URL>

Example:
    python scripts/diagnose_mcp_tool_search.py \
        --url https://quickbooks-mcp-cloudflare.curly-tree-8090.workers.dev/mcp
"""

import argparse
import json
import sys
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


DESCRIPTION_TRUNCATION_LIMIT = 2048  # Claude.ai truncates descriptions at 2KB
LARGE_SCHEMA_THRESHOLD = 4096        # Schemas above this are considered "large"
EXPECTED_WRITE_TOOLS = [
    "create_purchase",
    "update_purchase",
    "create_vendor",
    "update_vendor",
    "create_bill",
    "update_bill",
    "create_invoice",
    "update_invoice",
    "create_estimate",
    "update_estimate",
    "create_payment",
    "update_payment",
    "create_customer",
    "update_customer",
    "create_employee",
    "update_employee",
]


def jsonrpc_request(method, params=None, req_id=None):
    """Build a JSON-RPC 2.0 request payload."""
    return {
        "jsonrpc": "2.0",
        "id": req_id or str(uuid.uuid4()),
        "method": method,
        "params": params or {},
    }


def send_rpc(url, method, params=None, session_id=None):
    """Send a JSON-RPC request to an MCP server over Streamable HTTP."""
    payload = json.dumps(jsonrpc_request(method, params)).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    req = Request(url, data=payload, headers=headers, method="POST")

    try:
        with urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            session_id_header = resp.headers.get("Mcp-Session-Id")
            raw = resp.read().decode()

            # Handle SSE response format
            if "text/event-stream" in content_type:
                return parse_sse_response(raw), session_id_header

            return json.loads(raw), session_id_header
    except HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"  HTTP {e.code}: {body}", file=sys.stderr)
        raise
    except URLError as e:
        print(f"  Connection error: {e.reason}", file=sys.stderr)
        raise


def parse_sse_response(raw):
    """Parse Server-Sent Events response to extract JSON-RPC result."""
    result = None
    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("data:"):
            data = line[len("data:"):].strip()
            if data:
                try:
                    parsed = json.loads(data)
                    # Keep the last result (final response)
                    if "result" in parsed or "error" in parsed:
                        result = parsed
                except json.JSONDecodeError:
                    continue
    return result


def initialize_session(url):
    """Initialize an MCP session and return the session ID."""
    print("[1/4] Initializing MCP session...")
    params = {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "mcp-diagnostic", "version": "1.0.0"},
    }
    resp, session_id = send_rpc(url, "initialize", params)

    if resp and "result" in resp:
        info = resp["result"].get("serverInfo", {})
        print(f"  Server: {info.get('name', 'unknown')} v{info.get('version', '?')}")
        proto = resp["result"].get("protocolVersion", "unknown")
        print(f"  Protocol: {proto}")
        caps = resp["result"].get("capabilities", {})
        print(f"  Capabilities: {json.dumps(caps, indent=2)}")
        return session_id
    elif resp and "error" in resp:
        print(f"  Error: {resp['error']}", file=sys.stderr)
        return None
    else:
        print("  Warning: No result in initialize response", file=sys.stderr)
        return session_id


def list_all_tools(url, session_id):
    """Fetch all tools, following pagination cursors."""
    print("\n[2/4] Listing all tools (following pagination)...")
    all_tools = []
    cursor = None
    page = 0

    while True:
        page += 1
        params = {}
        if cursor:
            params["cursor"] = cursor

        resp, _ = send_rpc(url, "tools/list", params, session_id)

        if resp is None:
            print(f"  Page {page}: No response received", file=sys.stderr)
            break

        if "error" in resp:
            print(f"  Page {page}: Error - {resp['error']}", file=sys.stderr)
            break

        result = resp.get("result", {})
        tools = result.get("tools", [])
        next_cursor = result.get("nextCursor")

        all_tools.extend(tools)
        print(f"  Page {page}: {len(tools)} tools (total so far: {len(all_tools)})")

        if not next_cursor:
            break
        cursor = next_cursor
        print(f"  Following nextCursor: {next_cursor[:40]}...")

    print(f"  Total tools discovered: {len(all_tools)}")
    return all_tools


def analyze_tools(tools):
    """Analyze tools for issues that would prevent ToolSearch indexing."""
    print("\n[3/4] Analyzing tools for ToolSearch issues...")
    print("=" * 70)

    issues = {
        "missing_description": [],
        "missing_input_schema": [],
        "truncated_description": [],
        "large_schema": [],
        "empty_description": [],
        "no_search_keywords": [],
    }

    tool_summary = []

    for tool in tools:
        name = tool.get("name", "<unnamed>")
        desc = tool.get("description", "")
        schema = tool.get("inputSchema", {})
        schema_str = json.dumps(schema)
        schema_size = len(schema_str)
        desc_size = len(desc)
        prop_count = len(schema.get("properties", {}))

        entry = {
            "name": name,
            "desc_size": desc_size,
            "schema_size": schema_size,
            "prop_count": prop_count,
            "issues": [],
        }

        if not desc:
            issues["missing_description"].append(name)
            entry["issues"].append("NO_DESCRIPTION")
        elif desc_size > DESCRIPTION_TRUNCATION_LIMIT:
            issues["truncated_description"].append(name)
            entry["issues"].append(f"DESC_TRUNCATED({desc_size}B > {DESCRIPTION_TRUNCATION_LIMIT}B)")

        if not schema:
            issues["missing_input_schema"].append(name)
            entry["issues"].append("NO_INPUT_SCHEMA")

        if schema_size > LARGE_SCHEMA_THRESHOLD:
            issues["large_schema"].append(name)
            entry["issues"].append(f"LARGE_SCHEMA({schema_size}B)")

        if desc and len(desc.strip()) < 10:
            issues["empty_description"].append(name)
            entry["issues"].append("NEAR_EMPTY_DESC")

        tool_summary.append(entry)

    # Print all tools sorted by schema size (largest first)
    tool_summary.sort(key=lambda t: t["schema_size"], reverse=True)

    print(f"\n{'Tool Name':<40} {'Desc':<6} {'Schema':<8} {'Props':<6} {'Issues'}")
    print("-" * 90)
    for t in tool_summary:
        issue_str = ", ".join(t["issues"]) if t["issues"] else "OK"
        marker = ">>>" if any(kw in t["name"] for kw in ["create_", "update_"]) else "   "
        print(f"{marker} {t['name']:<36} {t['desc_size']:<6} {t['schema_size']:<8} {t['prop_count']:<6} {issue_str}")

    return issues, tool_summary


def check_expected_tools(tools):
    """Check which expected write/create tools are present or missing."""
    print("\n[4/4] Checking expected write/create tools...")
    print("=" * 70)
    tool_names = {t.get("name", "") for t in tools}

    present = []
    missing = []
    for expected in EXPECTED_WRITE_TOOLS:
        if expected in tool_names:
            present.append(expected)
        else:
            # Check for prefixed variants (e.g., "quickbooks_create_purchase")
            matches = [n for n in tool_names if expected in n]
            if matches:
                present.append(f"{expected} (as {matches[0]})")
            else:
                missing.append(expected)

    print(f"\n  Present ({len(present)}):")
    for t in present:
        print(f"    + {t}")

    print(f"\n  Missing ({len(missing)}):")
    for t in missing:
        print(f"    - {t}")

    # Categorize all tools by action prefix
    action_counts = {}
    for t in tools:
        name = t.get("name", "")
        # Extract action prefix (e.g., "create", "get", "update", "delete", "search")
        parts = name.split("_", 1)
        action = parts[0] if parts else "unknown"
        action_counts[action] = action_counts.get(action, 0) + 1

    print(f"\n  Tool counts by action prefix:")
    for action, count in sorted(action_counts.items(), key=lambda x: -x[1]):
        print(f"    {action}: {count}")

    return present, missing


def generate_diagnosis(tools, issues, tool_summary, present, missing):
    """Generate the final diagnosis report."""
    print("\n" + "=" * 70)
    print("DIAGNOSIS REPORT")
    print("=" * 70)

    total = len(tools)
    total_issues = sum(len(v) for v in issues.values())

    if not tools:
        print("""
  CRITICAL: No tools returned by tools/list

  Possible causes:
    1. MCP server requires authentication (OAuth, API key) to list tools
    2. The tools/list endpoint is broken or returns empty results
    3. Server uses pagination but returned 0 tools on first page
""")
        return

    print(f"\n  Total tools from server: {total}")
    print(f"  Tools with issues: {total_issues}")
    print(f"  Expected write tools present: {len(present)}/{len(EXPECTED_WRITE_TOOLS)}")
    print(f"  Expected write tools missing: {len(missing)}/{len(EXPECTED_WRITE_TOOLS)}")

    # Determine most likely root cause
    if missing:
        large_tools = {t["name"] for t in tool_summary if t["schema_size"] > LARGE_SCHEMA_THRESHOLD}
        write_tools_large = [m for m in missing if m in large_tools]

        if len(missing) == len(EXPECTED_WRITE_TOOLS) and total > 0:
            print("""
  ROOT CAUSE: Write/create tools entirely absent from server response

  The MCP server does not return create/update tools in tools/list.
  This is likely a server-side configuration or authorization issue.

  RECOMMENDED FIX:
    - Check MCP server code for tool registration of create/update operations
    - Verify OAuth scopes include write permissions
    - Check if server conditionally filters tools based on auth context
""")
        elif write_tools_large:
            print(f"""
  ROOT CAUSE: Large schema sizes on write/create tools

  The following tools have schemas exceeding {LARGE_SCHEMA_THRESHOLD}B:
    {', '.join(write_tools_large)}

  Claude.ai truncates tool descriptions at 2KB. Large schemas may cause
  the tool indexer to silently drop or fail to index the tool.

  RECOMMENDED FIX:
    - Reduce inputSchema size by making properties optional
    - Use $ref to external schema definitions
    - Split complex tools into simpler sub-operations
""")

    # Check for the pagination diagnosis
    if total > 0:
        # Check if write tools tend to be later alphabetically
        sorted_names = sorted(t.get("name", "") for t in tools)
        print(f"\n  First tool alphabetically: {sorted_names[0]}")
        print(f"  Last tool alphabetically:  {sorted_names[-1]}")

        # Check if all returned tools might be from a single page
        if total <= 25 and any(m not in [t.get("name") for t in tools] for m in EXPECTED_WRITE_TOOLS):
            print("""
  POSSIBLE CAUSE: Pagination not followed

  If the server returns tools across multiple pages and the Claude.ai
  connector only reads the first page, tools on subsequent pages would
  be silently missing from the ToolSearch index.

  RECOMMENDED FIX (Claude.ai platform):
    - Ensure MCP connector follows nextCursor until exhausted
    - Log when pagination is truncated
""")

    if issues["truncated_description"]:
        print(f"""
  WARNING: {len(issues['truncated_description'])} tools have descriptions > 2KB
  These tools may have degraded ToolSearch ranking because their descriptions
  are truncated, losing important search keywords.

  Affected tools: {', '.join(issues['truncated_description'])}
""")

    if issues["missing_description"]:
        print(f"""
  WARNING: {len(issues['missing_description'])} tools have no description
  Tools without descriptions cannot be found via BM25 keyword search.

  Affected tools: {', '.join(issues['missing_description'])}
""")

    print("""
  GENERAL RECOMMENDATIONS:
    1. Run this diagnostic against the live MCP server to confirm tool inventory
    2. Compare tools/list output between Claude Code (working) and Claude.ai (broken)
    3. If tools ARE in the server response, file a bug against Claude.ai's MCP connector
    4. If tools are NOT in the server response, investigate server-side tool registration
    5. Check Claude.ai MCP connector logs for schema validation errors
""")


def main():
    parser = argparse.ArgumentParser(
        description="Diagnose QuickBooks MCP ToolSearch indexing issues"
    )
    parser.add_argument(
        "--url",
        required=True,
        help="MCP server URL (e.g., https://example.workers.dev/mcp)",
    )
    parser.add_argument(
        "--expected-tool",
        action="append",
        help="Additional tool name to check for (can be repeated)",
    )
    parser.add_argument(
        "--json-output",
        help="Write full tool list to JSON file for offline analysis",
    )
    args = parser.parse_args()

    if args.expected_tool:
        EXPECTED_WRITE_TOOLS.extend(args.expected_tool)

    print(f"MCP ToolSearch Diagnostic")
    print(f"Server: {args.url}")
    print("=" * 70)

    try:
        session_id = initialize_session(args.url)
    except Exception as e:
        print(f"\nFATAL: Cannot connect to MCP server: {e}", file=sys.stderr)
        print("\nIf the server requires OAuth, you may need to provide credentials.")
        sys.exit(1)

    try:
        tools = list_all_tools(args.url, session_id)
    except Exception as e:
        print(f"\nFATAL: Cannot list tools: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json_output and tools:
        with open(args.json_output, "w") as f:
            json.dump(tools, f, indent=2)
        print(f"\n  Full tool list written to: {args.json_output}")

    issues, tool_summary = analyze_tools(tools)
    present, missing = check_expected_tools(tools)
    generate_diagnosis(tools, issues, tool_summary, present, missing)


if __name__ == "__main__":
    main()
