import os
import logging
from mcp.server.fastmcp import FastMCP
from proxmoxer import ProxmoxAPI
import urllib3

# Suppress insecure request warnings for self-signed certs (Home Lab Standard)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("proxmox_mcp")

mcp = FastMCP("Proxmox")

def get_proxmox(host: str) -> ProxmoxAPI:
    token_id = os.environ.get("PROXMOX_TOKEN_ID")
    token_secret = os.environ.get("PROXMOX_TOKEN_SECRET")
    
    if not token_id or not token_secret:
        raise ValueError("Environment variables PROXMOX_TOKEN_ID and PROXMOX_TOKEN_SECRET must be set.")
    
    try:
        user, token_name = token_id.split('!')
    except ValueError:
        raise ValueError("PROXMOX_TOKEN_ID must be in format 'user@realm!token_name'")

    return ProxmoxAPI(
        host, 
        user=user, 
        token_name=token_name, 
        token_value=token_secret, 
        verify_ssl=False
    )

@mcp.tool()
def list_nodes(host: str) -> str:
    """
    List all physical nodes in the Proxmox cluster.
    
    Args:
        host: IP address or hostname of the Proxmox API server.
    """
    try:
        px = get_proxmox(host)
        nodes = px.nodes.get()
        result = []
        for n in nodes:
            result.append(f"Node: {n['node']} | Status: {n['status']} | CPU: {n.get('cpu', 0):.2%} | Max Mem: {n.get('maxmem', 0) // (1024**3)} GB")
        return "\n".join(result)
    except Exception as e:
        return f"Error listing nodes: {str(e)}"

@mcp.tool()
def list_guests(host: str, node: str) -> str:
    """
    List all VMs and Containers (Guests) on a specific Proxmox node.
    
    Args:
        host: IP address or hostname of the Proxmox API server.
        node: Name of the target Proxmox node.
    """
    try:
        px = get_proxmox(host)
        vms = px.nodes(node).qemu.get()
        cts = px.nodes(node).lxc.get()
        
        result = ["--- Virtual Machines (QEMU) ---"]
        for vm in vms:
            result.append(f"[{vm['vmid']}] {vm['name']} - Status: {vm['status']}")
            
        result.append("\n--- LXC Containers ---")
        for ct in cts:
            result.append(f"[{ct['vmid']}] {ct['name']} - Status: {ct['status']}")
            
        return "\n".join(result)
    except Exception as e:
        return f"Error listing guests: {str(e)}"

@mcp.tool()
def manage_guest(host: str, node: str, vmid: int, guest_type: str, action: str) -> str:
    """
    Manage the power state of a specific VM or Container.
    
    Args:
        host: IP address or hostname of the Proxmox API server.
        node: Name of the target Proxmox node.
        vmid: ID of the guest (e.g., 100).
        guest_type: 'qemu' (for VMs) or 'lxc' (for Containers).
        action: Power action to perform ('start', 'stop', 'shutdown', 'status').
    """
    if guest_type not in ['qemu', 'lxc']:
        return "Error: guest_type must be either 'qemu' or 'lxc'."
        
    try:
        px = get_proxmox(host)
        resource = px.nodes(node).qemu(vmid) if guest_type == 'qemu' else px.nodes(node).lxc(vmid)
        
        if action == 'status':
            status = resource.status.current.get()
            return f"Guest {vmid} ({guest_type}) is currently: {status.get('status', 'unknown')}"
            
        elif action in ['start', 'stop', 'shutdown']:
            resource.status.post(action)
            return f"Successfully executed '{action}' on guest {vmid} ({guest_type})."
            
        else:
            return f"Error: Unknown action '{action}'. Use start, stop, shutdown, or status."
            
    except Exception as e:
        return f"Error managing guest: {str(e)}"

def main():
    mcp.run()

if __name__ == "__main__":
    main()
