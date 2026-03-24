# Proxmox MCP Server

A simple Model Context Protocol (MCP) server for managing Proxmox VE environments via the Proxmox API.

## Features
- Connects to any Proxmox host dynamically via environment variable
- Disables SSL verification warnings for self-signed certificates (ideal for home labs)
- Provides tools to:
  - List physical nodes
  - List virtual machines (QEMU) and containers (LXC)
  - Manage guest power states (start, stop, shutdown, status)

## Setup & Authentication
The server requires a Proxmox API Token.
Create a token in the Proxmox GUI (Datacenter > Permissions > API Tokens) for a user with appropriate permissions (e.g., `root@pam`).

Set the following environment variables before running:
- `PROXMOX_HOST`: The IP address or hostname of your Proxmox server (e.g., `192.168.1.100`)
- `PROXMOX_TOKEN_ID`: The full token ID (e.g., `root@pam!mytoken`)
- `PROXMOX_TOKEN_SECRET`: The UUID secret of the token

## Usage (via `uvx`)

You can run this server dynamically using `uvx` without installing it permanently:

```bash
PROXMOX_HOST="192.168.1.100" \
PROXMOX_TOKEN_ID="root@pam!mytoken" \
PROXMOX_TOKEN_SECRET="your-uuid-secret" \
uvx --from git+https://github.com/edasan0568/proxmox-mcp-server proxmox-mcp-server
```

## MCP Configuration Example (MCPHub)

```json
{
  "mcpServers": {
    "proxmox": {
      "command": "/root/.local/bin/uvx",
      "args": [
        "--from",
        "git+https://github.com/edasan0568/proxmox-mcp-server",
        "proxmox-mcp-server"
      ],
      "env": {
        "PROXMOX_HOST": "192.168.1.100",
        "PROXMOX_TOKEN_ID": "root@pam!mytoken",
        "PROXMOX_TOKEN_SECRET": "your-uuid-secret"
      }
    }
  }
}
```
