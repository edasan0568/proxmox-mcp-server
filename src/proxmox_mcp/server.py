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
        raise ValueError("Environment variable PROXMOX_HOST must be set.")
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
    """List all physical nodes in the configured Proxmox cluster."""
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
    """List all VMs and Containers (Guests) on a specific Proxmox node."""
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
    """Manage the power state of a specific VM or Container (start, stop, shutdown, status)."""
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
            return f"Error: Unknown action '{action}'."
    except Exception as e:
        return f"Error managing guest: {str(e)}"

@mcp.tool()
def clone_vm(
    node: str, vmid: int, source_vmid: int, name: str, full_clone: bool = True,
    ipconfig0: str = None, ciuser: str = None, cipassword: str = None,
    sshkeys: str = None, start_vm: bool = True
) -> str:
    """Clone a VM (QEMU) from a template and apply Cloud-Init config."""
    try:
        px = get_proxmox()
        logger.info(f"Cloning VM {source_vmid} to {vmid} ({name})...")
        task_upid = px.nodes(node).qemu(source_vmid).clone.post(newid=vmid, name=name, full=1 if full_clone else 0)
        
        while True:
            task_status = px.nodes(node).tasks(task_upid).status.get()
            if task_status['status'] == 'stopped':
                if task_status['exitstatus'] == 'OK': break
                else: return f"Error: Clone task failed with status {task_status['exitstatus']}"
            time.sleep(3)
            
        logger.info(f"Configuring VM {vmid}...")
        config_params = {}
        if ipconfig0: config_params['ipconfig0'] = ipconfig0
        if ciuser: config_params['ciuser'] = ciuser
        if cipassword: config_params['cipassword'] = cipassword
        if sshkeys:
            import urllib.parse
            config_params['sshkeys'] = sshkeys
            
        if config_params:
            px.nodes(node).qemu(vmid).config.post(**config_params)
            
        if start_vm:
            px.nodes(node).qemu(vmid).status.start.post()
            return f"Successfully cloned VM {vmid} ('{name}'), applied Cloud-Init, and started it."
            
        return f"Successfully cloned VM {vmid} ('{name}') and applied Cloud-Init. VM is stopped."
    except Exception as e:
        return f"Error cloning VM: {str(e)}"

@mcp.tool()
def create_lxc(
    node: str, vmid: int, ostemplate: str, name: str,
    password: str = None, sshkeys: str = None, net0: str = None,
    rootfs: str = "local-lvm:8", memory: int = 512, cores: int = 1,
    nesting: bool = True, unprivileged: bool = True,
    start_ct: bool = True
) -> str:
    """Create an LXC Container directly from an OS template tarball."""
    try:
        px = get_proxmox()
        logger.info(f"Creating LXC {vmid} ({name}) from {ostemplate}...")
        
        create_params = {
            'vmid': vmid,
            'ostemplate': ostemplate,
            'hostname': name,
            'rootfs': rootfs,
            'memory': memory,
            'cores': cores,
            'unprivileged': 1 if unprivileged else 0
        }
        if nesting:
            create_params['features'] = 'nesting=1'
            
        if password: create_params['password'] = password
        if sshkeys:
            import urllib.parse
            create_params['ssh-public-keys'] = sshkeys
        if net0: create_params['net0'] = net0
        
        task_upid = px.nodes(node).lxc.post(**create_params)
        
        while True:
            task_status = px.nodes(node).tasks(task_upid).status.get()
            if task_status['status'] == 'stopped':
                if task_status['exitstatus'] == 'OK': break
                else: return f"Error: Create task failed with status {task_status['exitstatus']}"
            time.sleep(3)
            
        if start_ct:
            px.nodes(node).lxc(vmid).status.start.post()
            return f"Successfully created LXC {vmid} ('{name}') from {ostemplate} and started it."
            
        return f"Successfully created LXC {vmid} ('{name}'). Container is stopped."
    except Exception as e:
        return f"Error creating LXC: {str(e)}"

def main():
    mcp.run()

if __name__ == "__main__":
    main()
