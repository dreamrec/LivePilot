# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.9.x   | Yes       |
| < 1.9   | No        |

## Architecture Security Notes

LivePilot operates through three local interfaces:

- **TCP 9878** — MCP server ↔ Ableton Remote Script (localhost only)
- **UDP 9880** — M4L Analyzer → MCP server (localhost only)
- **OSC 9881** — MCP server → M4L Analyzer (localhost only)

All communication is **local only** — no ports are exposed to the network.
The MCP server runs via stdio transport (stdin/stdout) and does not open HTTP endpoints.

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public issue
2. Email **security@pilotstudio.dev** with:
   - A description of the vulnerability
   - Steps to reproduce
   - Potential impact
3. You will receive an acknowledgment within 48 hours
4. We will work with you to understand and address the issue before any public disclosure

If you don't have access to the email, you can use [GitHub's private vulnerability reporting](https://github.com/dreamrec/LivePilot/security/advisories/new).

## Scope

The following are in scope:

- Remote code execution through MCP tool inputs
- Path traversal in file-handling tools (MIDI I/O, sample loading)
- Unauthorized access to Ableton session data
- Denial of service against the MCP server or Remote Script

The following are out of scope:

- Issues requiring physical access to the machine
- Issues in Ableton Live itself (report to Ableton)
- Issues in MCP clients (report to the client maintainer)
