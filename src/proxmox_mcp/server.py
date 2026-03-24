import os
import logging
import time
from mcp.server.fastmcp import FastMCP
from proxmoxer import ProxmoxAPI
import urllib3

# Suppress insecure request warnings for self-signed certs (Home Lab Standard)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("proxmox_mcp")

mcp = FastMCP("Proxmox")

def get_proxmox() -> ProxmoxAPI:
    host = os.environ.get("PROXMOX_HOST")
    token_id = os.environ.get("PROXMOX_TOKEN_ID")
    token_secret = os.environ.get("PROXMOX_TOKEN_SECRET")
    
    if not host:
        raise ValueError("Environment variable PROXMOX_HOST must be set (e.g., 192.168.1.100).")
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
def list_nodes() -> str:
    """
    List all physical nodes in the configured Proxmox cluster.
    """
    try:
        px = get_proxmox()
        nodes = px.nodes.get()
        result = []
        for n in nodes:
            result.append(f"Node: {n['node']} | Status: {n['status']} | CPU: {n.get('cpu', 0):.2%} | Max Mem: {n.get('maxmem', 0) // (1024**3)} GB")
        return "\n".join(result)
    except Exception as e:
        return f"Error listing nodes: {str(e)}"

@mcp.tool()
def list_guests(node: str) -> str:
    """
    List all VMs and Containers (Guests) on a specific Proxmox node.
    
    Args:
        node: Name of the target Proxmox node.
    """
    try:
        px = get_proxmox()
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
def manage_guest(node: str, vmid: int, guest_type: str, action: str) -> str:
    """
    Manage the power state of a specific VM or Container.
    
    Args:
        node: Name of the target Proxmox node.
        vmid: ID of the guest (e.g., 100).
        guest_type: 'qemu' (for VMs) or 'lxc' (for Containers).
        action: Power action to perform ('start', 'stop', 'shutdown', 'status').
    """
    if guest_type not in ['qemu', 'lxc']:
        return "Error: guest_type must be either 'qemu' or 'lxc'."
        
    try:
        px = get_proxmox()
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

@mcp.tool()
def clone_guest(
    node: str, 
    vmid: int, 
    source_vmid: int, 
    name: str, 
    full_clone: bool = True,
    ipconfig0: str = None,
    ciuser: str = None,
    cipassword: str = None,
    sshkeys: str = None,
    start_vm: bool = True
) -> str:
    """
    Clone a VM from a template, configure Cloud-Init, and optionally start it.
    
    Args:
        node: Name of the target Proxmox node.
        vmid: ID for the new VM (e.g., 201).
        source_vmid: ID of the template VM to clone from (e.g., 9000).
        name: Name of the new VM.
        full_clone: Whether to perform a full clone (True) or linked clone (False).
        ipconfig0: Cloud-Init IP config (e.g., 'ip=192.168.1.50/24,gw=192.168.1.1').
        ciuser: Cloud-Init default username.
        cipassword: Cloud-Init user password.
        sshkeys: Cloud-Init SSH public keys (newline separated).
        start_vm: Whether to start the VM automatically after configuration.
    """
    try:
        px = get_proxmox()
        
        # 1. Clone the VM
        logger.info(f"Cloning VM {source_vmid} to {vmid} ({name})...")
        task_upid = px.nodes(node).qemu(source_vmid).clone.post(
            newid=vmid, 
            name=name, 
            full=1 if full_clone else 0
        )
        
        # 2. Wait for clone to complete (Proxmox tasks)
        while True:
            task_status = px.nodes(node).tasks(task_upid).status.get()
            if task_status['status'] == 'stopped':
                if task_status['exitstatus'] == 'OK':
                    break
                else:
                    return f"Error: Clone task failed with status {task_status['exitstatus']}"
            time.sleep(3)
            
        # 3. Configure Cloud-Init
        logger.info(f"Clone finished. Configuring Cloud-Init for VM {vmid}...")
        config_params = {}
        if ipconfig0: config_params['ipconfig0'] = ipconfig0
        if ciuser: config_params['ciuser'] = ciuser
        if cipassword: config_params['cipassword'] = cipassword
        if sshkeys:
            import urllib.parse
            # Proxmox API expects sshkeys to be URL encoded
            config_params['sshkeys'] = urllib.parse.quote(sshkeys, safe='')
            
        if config_params:
            px.nodes(node).qemu(vmid).config.post(**config_params)
            
        # 4. Start the VM if requested
        if start_vm:
            logger.info(f"Starting VM {vmid}...")
            px.nodes(node).qemu(vmid).status.start.post()
            return f"Successfully cloned VM {vmid} ('{name}') from template {source_vmid}, configured Cloud-Init, and started the VM."
            
        return f"Successfully cloned VM {vmid} ('{name}') from template {source_vmid} and configured Cloud-Init. VM is currently stopped."
        
    except Exception as e:
        return f"Error cloning guest: {str(e)}"

def main():
    mcp.run()

if __name__ == "__main__":
    main()
