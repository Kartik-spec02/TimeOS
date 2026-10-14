# Friction Log — TimeOS

This log records every point of friction, confusion, or broken documentation encountered while building TimeOS for the Amazon Developer Hackathon 2026.

## 1. MCP SDK v2 vs v1 — FastMCP renamed to MCPServer

**What happened:** Running `pip install mcp` installed version 2.3.0. The code `from mcp.server.fastmcp import FastMCP` failed with:

ModuleNotFoundError: No module named 'mcp.server.fastmcp'

The error message in v2.3.0 includes a link to the migration guide, but the link is buried in a raised exception rather than a warning at install time.

**Fix:** Pinned to `mcp<2` in `requirements.txt` and downgraded.

**Suggestion:** The migration guide is thorough but the error only appeared at runtime, not at install time. A deprecation warning during `pip install` would have saved time.

## 2. "Invalid Host header" after Cloudflare tunnel

**What happened:** After exposing the server via `cloudflared tunnel`, every request returned `Invalid Host header`.

**Cause:** MCP's `TransportSecuritySettings` enables DNS rebinding protection by default, which only allows `localhost` and `127.0.0.1`.

**Fix:** Set `enable_dns_rebinding_protection=False` in the `FastMCP` constructor.

**Suggestion:** The error message "Invalid Host header" doesn't mention DNS rebinding protection or how to disable it. A hint in the error would help.

## 3. `@alexa-ai/cli` does not exist on npm

**What happened:** Tried to install `@alexa/alexa-ai` and `@alexa-ai/cli`. Both returned 404.

**Cause:** Amazon's Alexa+ MCP Toolkit is **partner-only**. The CLI is not publicly available.

**Fix:** Built a web-based simulator (`alexa_sim.html`) instead. This is explicitly allowed by the hackathon rules: "New to MCP? Build a simulated Alexa+ experience in a web app."

**Suggestion:** The hackathon rules page should state this limitation more prominently. Many participants likely hit the same wall.

## 4. CORS preflight returned 405

**What happened:** The browser sent an `OPTIONS /mcp` preflight request. The MCP server returned `405 Method Not Allowed` because the MCP router doesn't handle OPTIONS.

**Cause:** Adding `CORSMiddleware` via Starlette's `add_middleware()` after `streamable_http_app()` was too late — the routes were already built.

**Fix:** Wrote a custom ASGI wrapper (`CORSWrapper`) that intercepts OPTIONS before it reaches the MCP router and adds CORS headers to all responses.

**Suggestion:** MCP's streamable HTTP transport should ship with a CORS option for browser-based clients.

## 5. `Mount()` broke the tools/call path

**What happened:** Wrapping the MCP app in `Mount("/mcp", app=mcp_app)` made `initialize` work but `tools/call` returned 404.

**Cause:** The MCP internal routing expects the app at the root, not behind a mount point.

**Fix:** Reverted to the root-mounted app and used the custom CORS wrapper instead of Starlette's middleware.

**Suggestion:** If the recommended way to add middleware is `Mount`, it should not break the internal routing.

## 6. SSE vs plain JSON responses

**What happened:** The server sometimes responds with SSE (`data: {...}`) and sometimes with plain JSON, depending on the request. The initial client code only parsed SSE.

**Fix:** `parseSSE()` falls back to `JSON.parse()` when no `data: ` line is found.

**Suggestion:** Document when each response format is used.

## 7. Database table missing after deletion while server running

**What happened:** Deleted `data/timeos.db` while the server was running. The server had an open connection to the deleted file, so `init_db()` did not recreate the table.

**Fix:** Always stop the server, delete the DB, then restart.

**Suggestion:** `init_db()` could be called at the start of every tool invocation, or the server could detect a missing file.

## Summary

The most impactful friction points were (1) the v1/v2 SDK rename, (2) the partner-only CLI, and (3) the CORS/DNS-rebinding issues. All three had error messages that did not point to the actual fix.