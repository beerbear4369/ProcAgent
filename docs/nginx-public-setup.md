# nginx Public Exposure Setup Guide

This guide documents how to expose ProcAgent to the public internet using nginx.

## Architecture

```
Internet (Public IP: 156.246.78.218)
    ↓
ZTE F620 Router (192.168.10.254)
    ↓ Port Forward: 80 → 192.168.10.2
    ↓
PC (192.168.10.2) via Ethernet
    ↓
nginx (port 80) → FastAPI (port 8000)
```

## Prerequisites

- Windows PC connected to F620 router via ethernet
- nginx installed at `C:\nginx`
- Python environment with ProcAgent dependencies

## Quick Start

### 1. Start Services

```powershell
# Terminal 1: Start FastAPI backend
python -m procagent.server.app

# Terminal 2: Start nginx
cd C:\nginx
.\nginx.exe
```

### 2. Access

- **Public URL:** `http://YOUR_PUBLIC_IP/`
- **Local URL:** `http://localhost/`
- **Login:** Username and password configured in `config/settings.yaml`

## Installation Steps

### Step 1: Install nginx

1. Download nginx from https://nginx.org/en/download.html
2. Extract to `C:\nginx`
3. Copy `config/nginx.conf` to `C:\nginx\conf\nginx.conf`

### Step 2: Configure Authentication

Edit `config/settings.yaml`:

```yaml
auth:
  username: "procagent"
  password: "your-secure-password"
  session_timeout: 86400  # 24 hours
```

### Step 3: Windows Firewall

Run as Administrator:

```powershell
New-NetFirewallRule -DisplayName "nginx HTTP" -Direction Inbound -LocalPort 80 -Protocol TCP -Action Allow
```

### Step 4: Router Port Forwarding

On your router (e.g., ZTE F620 at 192.168.10.254):

1. Navigate to **Security** → **Port Forwarding**
2. Add rule:
   - **Name:** ProcAgent
   - **Protocol:** TCP
   - **LAN Host:** Your PC's IP (e.g., 192.168.10.2)
   - **WAN Port:** 80
   - **LAN Host Port:** 80
3. Apply

### Step 5: Get Public IP

```powershell
curl ifconfig.me
```

## nginx Configuration

The nginx config (`config/nginx.conf`) handles:

- Reverse proxy to FastAPI (port 8000)
- WebSocket proxy for chat (`/ws`)
- WebSocket proxy for VNC (`/vnc-ws/`)
- noVNC static files (`/novnc/`)

## File Locations

| File | Purpose |
|------|---------|
| `C:\nginx\conf\nginx.conf` | nginx configuration |
| `config/settings.yaml` | App settings including auth |
| `procagent/web/login.html` | Login page |
| `procagent/web/index.html` | Main app |
| `procagent/server/app.py` | FastAPI backend with auth |

## Troubleshooting

### Check if services are running

```powershell
# Check ports
netstat -ano | findstr ":80 :8000"

# Test locally
curl http://localhost/health
```

### Restart nginx

```powershell
cd C:\nginx
.\nginx.exe -s quit
.\nginx.exe
```

### Check nginx logs

```powershell
type C:\nginx\logs\error.log
type C:\nginx\logs\access.log
```

### Test nginx config

```powershell
cd C:\nginx
.\nginx.exe -t
```

## Security Notes

- Change the default password in `config/settings.yaml`
- Sessions are stored in-memory (lost on server restart)
- HTTP only (no SSL) - for production, add HTTPS with Let's Encrypt
- Consider IP allowlisting for additional security
