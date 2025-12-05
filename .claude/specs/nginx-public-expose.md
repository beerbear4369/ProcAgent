# nginx Public Expose Plan

## Overview

Expose ProcAgent to the public internet using nginx as a reverse proxy with a custom styled login page (session-based authentication in FastAPI).

## Architecture

```
Internet
    |
    v
Home Router (Port Forward: 80 -> Windows PC:80)
    |
    v
nginx (Windows, port 80)
    |-- Reverse proxy only (no auth)
    |
    v
FastAPI Backend (127.0.0.1:8000)
    |-- Session-based authentication
    |-- Serves login.html for unauthenticated users
    |-- Serves index.html for authenticated users
    |-- WebSocket chat (/ws)
    |-- API endpoints
    |
    v
websockify (127.0.0.1:6080) -> TightVNC (127.0.0.1:5900)
```

## User Workflow

1. User visits `http://YOUR_PUBLIC_IP/`
2. FastAPI checks session cookie -> not logged in -> serves `login.html`
3. User enters username/password on styled login page
4. POST to `/api/login` -> validates credentials
5. On success: session cookie set, redirect to `/app` (main interface)
6. Main app loads with chat + VNC panel
7. Session persists until logout or browser close

---

## Implementation Steps

### Step 1: Install nginx on Windows

1. Download nginx stable from https://nginx.org/en/download.html
2. Extract to `C:\nginx`
3. Verify: `cd C:\nginx && .\nginx.exe -v`

Commands:
```powershell
# Start
cd C:\nginx && .\nginx.exe

# Stop gracefully
.\nginx.exe -s quit

# Reload config
.\nginx.exe -s reload

# Test config
.\nginx.exe -t
```

### Step 2: Create nginx Configuration

Create `C:\nginx\conf\nginx.conf`:

```nginx
worker_processes 1;

events {
    worker_connections 1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;
    sendfile      on;
    keepalive_timeout 65;

    # WebSocket upgrade handling
    map $http_upgrade $connection_upgrade {
        default upgrade;
        '' close;
    }

    server {
        listen 80;
        server_name _;

        # Main proxy to FastAPI (handles auth internally)
        location / {
            proxy_pass http://127.0.0.1:8000;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # WebSocket for chat
        location /ws {
            proxy_pass http://127.0.0.1:8000/ws;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_read_timeout 86400s;
            proxy_send_timeout 86400s;
        }

        # WebSocket for VNC (websockify)
        location /vnc-ws/ {
            proxy_pass http://127.0.0.1:6080/;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_read_timeout 86400s;
            proxy_send_timeout 86400s;
        }

        # noVNC static files
        location /novnc/ {
            proxy_pass http://127.0.0.1:6080/;
            proxy_http_version 1.1;
        }
    }
}
```

### Step 3: Add Authentication Configuration

**File: `config/settings.yaml`**

Add auth section:
```yaml
# Authentication settings
auth:
  username: "procagent"
  password: "your-secure-password-here"
  session_timeout: 86400  # 24 hours in seconds
```

**File: `procagent/config.py`**

Add AuthConfig model:
```python
@dataclass
class AuthConfig:
    username: str = "procagent"
    password: str = "procagent"
    session_timeout: int = 86400

@dataclass
class Settings:
    # ... existing fields ...
    auth: AuthConfig = field(default_factory=AuthConfig)
```

### Step 4: Add Authentication Endpoints to FastAPI

**File: `procagent/server/app.py`**

Add imports:
```python
from fastapi import Cookie, Response, Form
import secrets
```

Add session storage:
```python
# Authentication session storage (in-memory for MVP)
auth_sessions: Dict[str, float] = {}  # token -> expiry timestamp
```

Add endpoints:
```python
@app.post("/api/login")
async def login(
    response: Response,
    username: str = Form(...),
    password: str = Form(...)
):
    """Authenticate user and create session."""
    settings = get_settings()

    if username == settings.auth.username and password == settings.auth.password:
        # Create session token
        session_token = secrets.token_urlsafe(32)
        expiry = time.time() + settings.auth.session_timeout
        auth_sessions[session_token] = expiry

        # Set cookie
        response.set_cookie(
            key="session",
            value=session_token,
            httponly=True,
            max_age=settings.auth.session_timeout
        )
        return {"success": True, "redirect": "/app"}

    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.post("/api/logout")
async def logout(response: Response, session: str = Cookie(None)):
    """Clear user session."""
    if session and session in auth_sessions:
        del auth_sessions[session]
    response.delete_cookie("session")
    return {"success": True, "redirect": "/"}


@app.get("/api/auth/status")
async def auth_status(session: str = Cookie(None)):
    """Check if user is authenticated."""
    if session and session in auth_sessions:
        if time.time() < auth_sessions[session]:
            return {"authenticated": True}
        else:
            # Session expired
            del auth_sessions[session]
    return {"authenticated": False}


def require_auth(session: str = Cookie(None)):
    """Dependency to require authentication."""
    if not session or session not in auth_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if time.time() >= auth_sessions[session]:
        del auth_sessions[session]
        raise HTTPException(status_code=401, detail="Session expired")
    return session
```

Update root route:
```python
@app.get("/", response_class=HTMLResponse)
async def root(session: str = Cookie(None)):
    """Serve login page or redirect to app."""
    # Check if authenticated
    if session and session in auth_sessions and time.time() < auth_sessions[session]:
        # Redirect to app
        return RedirectResponse(url="/app", status_code=302)

    # Serve login page
    login_path = web_dir / "login.html"
    if login_path.exists():
        return FileResponse(login_path)
    return HTMLResponse("<h1>Login page not found</h1>")


@app.get("/app", response_class=HTMLResponse)
async def app_page(session: str = Cookie(None)):
    """Serve the main application (requires auth)."""
    # Check authentication
    if not session or session not in auth_sessions or time.time() >= auth_sessions[session]:
        return RedirectResponse(url="/", status_code=302)

    # Serve main app
    index_path = web_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>App not found</h1>")
```

### Step 5: Create Login Page

**File: `procagent/web/login.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ProcAgent - Login</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .login-container {
            background: #fff;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            width: 100%;
            max-width: 400px;
        }

        .logo {
            text-align: center;
            margin-bottom: 30px;
        }

        .logo h1 {
            color: #1a1a2e;
            font-size: 28px;
            font-weight: 700;
        }

        .logo p {
            color: #666;
            font-size: 14px;
            margin-top: 8px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            color: #333;
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 8px;
        }

        .form-group input {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.2s;
        }

        .form-group input:focus {
            outline: none;
            border-color: #4a90d9;
        }

        .error-message {
            background: #ffe6e6;
            color: #d32f2f;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
            font-size: 14px;
        }

        .error-message.show {
            display: block;
        }

        .login-btn {
            width: 100%;
            padding: 14px;
            background: #4a90d9;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }

        .login-btn:hover {
            background: #3a7bc8;
        }

        .login-btn:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>ProcAgent</h1>
            <p>AI Copilot for Process Simulation</p>
        </div>

        <div id="error-message" class="error-message"></div>

        <form id="login-form">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required autocomplete="username">
            </div>

            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required autocomplete="current-password">
            </div>

            <button type="submit" class="login-btn" id="login-btn">Sign In</button>
        </form>
    </div>

    <script>
        const form = document.getElementById('login-form');
        const errorDiv = document.getElementById('error-message');
        const loginBtn = document.getElementById('login-btn');

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            // Disable button during request
            loginBtn.disabled = true;
            loginBtn.textContent = 'Signing in...';
            errorDiv.classList.remove('show');

            const formData = new FormData(form);

            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const data = await response.json();
                    window.location.href = data.redirect || '/app';
                } else {
                    const error = await response.json();
                    errorDiv.textContent = error.detail || 'Invalid credentials';
                    errorDiv.classList.add('show');
                }
            } catch (err) {
                errorDiv.textContent = 'Connection error. Please try again.';
                errorDiv.classList.add('show');
            } finally {
                loginBtn.disabled = false;
                loginBtn.textContent = 'Sign In';
            }
        });
    </script>
</body>
</html>
```

### Step 6: Update Frontend for VNC Proxy

**File: `procagent/web/index.html`**

Update the `connectVNC` function (around line 515-531):

```javascript
// Connect to VNC
function connectVNC() {
    if (!sessionId) return;

    // Fetch VNC info
    fetch(`/vnc/${sessionId}`)
        .then(response => response.json())
        .then(info => {
            // Connect via noVNC through nginx proxy
            // Use relative path instead of direct port access
            const vncUrl = `/novnc/vnc.html?autoconnect=true&password=${encodeURIComponent(info.password)}&path=vnc-ws/`;
            vncFrame.src = vncUrl;
            vncFrame.style.display = 'block';
            vncPlaceholder.style.display = 'none';
        })
        .catch(error => {
            console.error('Failed to get VNC info:', error);
        });
}
```

Add auth check at the beginning of the script section:
```javascript
// Check authentication on load
fetch('/api/auth/status')
    .then(response => response.json())
    .then(data => {
        if (!data.authenticated) {
            window.location.href = '/';
        }
    });
```

### Step 7: Windows Firewall Configuration

Run as Administrator:
```powershell
New-NetFirewallRule -DisplayName "nginx HTTP" -Direction Inbound -LocalPort 80 -Protocol TCP -Action Allow
```

### Step 8: Router Port Forwarding

1. Find your local IP: `ipconfig` (look for IPv4 address like 192.168.1.xxx)
2. Access router admin (usually 192.168.1.1 or 192.168.0.1)
3. Navigate to Port Forwarding / NAT / Virtual Server
4. Create rule:
   - External Port: 80
   - Internal IP: Your PC's IP (e.g., 192.168.1.100)
   - Internal Port: 80
   - Protocol: TCP
5. Save and apply

### Step 9: Find Your Public IP

```powershell
curl ifconfig.me
```

Or visit https://whatismyip.com

---

## Files Summary

### Files to Modify

| File | Changes |
|------|---------|
| `procagent/server/app.py` | Add login/logout/auth endpoints, update root route |
| `procagent/web/index.html` | Update VNC URL to use proxy path, add auth check |
| `procagent/config.py` | Add AuthConfig dataclass |
| `config/settings.yaml` | Add auth section with credentials |

### Files to Create

| File | Purpose |
|------|---------|
| `C:\nginx\conf\nginx.conf` | nginx reverse proxy configuration |
| `procagent/web/login.html` | Custom styled login page |

---

## Startup Sequence

1. Start TightVNC Server (if not already running as service)
2. Start websockify: `python -m websockify 6080 localhost:5900`
3. Start ProcAgent: `python -m procagent.server.app`
4. Start nginx: `cd C:\nginx && nginx.exe`

Optional startup script (`scripts/start_all.bat`):
```batch
@echo off
echo Starting ProcAgent services...

start "websockify" cmd /c "python -m websockify 6080 localhost:5900"
timeout /t 2

start "ProcAgent" cmd /c "python -m procagent.server.app"
timeout /t 3

cd C:\nginx
start nginx.exe

echo All services started!
echo Access at http://YOUR_PUBLIC_IP/
```

---

## Testing Checklist

- [ ] nginx starts without errors (`nginx -t`)
- [ ] Login page appears at `http://localhost/`
- [ ] Login with correct credentials redirects to app
- [ ] Login with wrong credentials shows error
- [ ] Chat WebSocket works after login
- [ ] VNC panel loads and displays ProMax
- [ ] Test from external network (phone on cellular)

---

## Security Notes

**MVP (Current):**
- Basic session-based auth with in-memory storage
- HTTP only (no encryption)
- Single user credentials in config file

**Future Improvements:**
- Add SSL/TLS with Let's Encrypt
- Rate limiting on login attempts
- Persistent session storage (Redis/database)
- Multiple user accounts
- IP allowlisting
