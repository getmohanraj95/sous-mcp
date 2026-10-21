# Sous: friction log

Real incidents from building Sous, an MCP server for Alexa+, for the
*Build, Ship, Shape: Amazon Developer Hackathon*. Each entry records the task,
the steps taken, the expected and actual results, a severity rating, the
workaround used, and an actionable suggestion.

| # | Area | Severity |
| --- | --- | --- |
| 1 | MCP Python SDK installation | Medium |
| 2 | Alexa+ add-on tooling access | High |
| 3 | MCP session identity inside tools | Medium (security dimension) |

---

## Entry 1: `pip install mcp` installs an incompatible major version

- **Task attempted:** Install the MCP Python SDK and follow the published
  quickstart for a Streamable HTTP server.
- **Steps taken:** `pip install mcp`, then copied the `FastMCP` quickstart.
- **Expected:** The installed package matches the API in the current
  documentation and examples.
- **Actual:** PyPI resolved to the v2 line, which reworked the API, so the
  quickstart code did not run against the installed package.
- **Severity:** Medium. Not a blocker, but it costs every new developer time at
  the worst possible moment, the first five minutes.
- **Workaround:** Pinned `mcp>=1.28,<2` in `requirements.txt` with an
  explanatory comment.
- **Suggestion:** State the required version range in the first code block of
  the getting-started page, or have the v2 package emit a clear message pointing
  to the v1 docs when v1-style imports are used.

## Entry 2: Alexa+ add-on tooling is unavailable to hackathon participants

- **Task attempted:** Test the MCP server against a real Alexa+ client using the
  MCP Toolkit, Alexa CLI and Web Simulator referenced in Alexa+ materials.
- **Steps taken:** Followed the Alexa+ add-on documentation to request access.
- **Expected:** Some participant-tier access, or a sandbox, for a hackathon whose
  primary track is Alexa+.
- **Actual:** The tooling is in preview for selected partners and could not be
  obtained. The add-on manifest in `addon-package/` could be prepared but never
  validated against a real client, and `structuredContent` rendering could not
  be verified against the real data-only flow.
- **Severity:** High for this track. Entrants cannot confirm their integration
  works on the target platform, only that it is protocol-correct.
- **Workaround:** Built `simulator/`, a web client that performs real
  `initialize`, `tools/list` and `tools/call` requests over Streamable HTTP and
  renders `structuredContent` the way the data-only flow is documented to.
- **Suggestion:** Offer a read-only validation endpoint or a hosted test client
  that accepts a public MCP URL and reports whether the manifest, tool schemas
  and structured output would render, without granting full add-on publishing
  rights.

## Entry 3: No supported way to read the MCP session ID inside a tool

- **Task attempted:** Scope per-conversation state to the MCP session.
- **Steps taken:** Looked for a session identifier on `Context`; found only
  `ctx.session`, the transport object.
- **Expected:** A documented accessor such as `ctx.session_id`.
- **Actual:** The only route is `ctx.request_context.request.headers`, which
  couples tool code to Starlette and returns nothing on transports without an
  HTTP request. Using `id(ctx.session)` instead appears to work and even passes
  a naive isolation test, but it is unsafe: CPython reuses an object's id after
  it is collected, so a new session can inherit a finished one's state.
- **Severity:** Medium, with a security dimension. The obvious implementation is
  quietly wrong, and the failure mode is one user's data appearing in another
  user's session.
- **Workaround:** Read the `mcp-session-id` header defensively and fall back to
  object identity only for transports that have no request (see
  `sous/tools.py`, `session_key`).
- **Suggestion:** Expose the negotiated session ID as a first-class property on
  `Context`, and warn against `id()`-based keying in the state-management docs.
