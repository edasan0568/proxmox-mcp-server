# Proxmox MCP Server

A simple Model Context Protocol (MCP) server for managing Proxmox VE environments via the Proxmox API.

## Features
- Connects to any Proxmox host dynamically via arguments
- Disables SSL verification warnings for self-signed certificates (ideal for home labs)
- Provides tools to:
  - List physical nodes
  - List virtual machines (QEMU) and containers (LXC)
  - Manage guest power states (start, stop, shutdown, status)

## Setup & Authentication
The server requires a Proxmox API Token.
Create a token in the Proxmox GUI (Datacenter > Permissions > API Tokens) for a user with appropriate permissions (e.g., `root@pam`).

Set the following environment variables before running:
- `PROXMOX_TOKEN_ID`: The full token ID (e.g., `root@pam!mytoken`)
- `PROXMOX_TOKEN_SECRET`: The UUID secret of the token

## Usage (via `uvx`)

You can run this server dynamically using `uvx` without installing it permanently:

```bash
PROXMOX_TOKEN_ID="root@pam!mytoken" \
PROXMOX_TOKEN_SECRET="your-uuid-secret" \
uvx --from git+https://github.com/edasan0568/proxmox-mcp-server proxmox-mcp-server
```

## MCP Configuration Example (mcp_settings.json for MCPHub)

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
        "PROXMOX_TOKEN_ID": "root@pam!mytoken",
        "PROXMOX_TOKEN_SECRET": "your-uuid-secret"
      }
    }
  }
}
```

## Tools Available
1. `list_nodes`: List all physical nodes in the cluster.
2. `list_guests`: List all VMs and Containers on a specific node.
3. `manage_guest`: Start, stop, shutdown, or check status of a specific VM/CT.
