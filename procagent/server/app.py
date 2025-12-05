"""
ProcAgent FastAPI Backend Server

Provides WebSocket chat endpoint and VNC proxy for browser-based interface.
"""

import asyncio
import sys
import json
import uuid
from pathlib import Path
from typing import Dict, Optional

# Windows needs ProactorEventLoop for subprocess support (Claude Agent SDK)
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import secrets
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Cookie, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from ..config import get_settings
from ..logging_config import setup_logging, get_logger
from ..agent.core import ProcAgentCore
from ..models import ChatMessage, AgentResponse, ResponseType

# Initialize logging
setup_logging()
logger = get_logger("server.app")

# Create FastAPI app
app = FastAPI(
    title="ProcAgent",
    description="AI copilot for chemical process simulation using ProMax",
    version="0.1.0",
)

# CORS middleware for localhost access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session storage
sessions: Dict[str, ProcAgentCore] = {}

# Authentication session storage (token -> expiry timestamp)
auth_sessions: Dict[str, float] = {}


# ============================================================================
# Static file serving
# ============================================================================

# Mount static files directory
web_dir = Path(__file__).parent.parent / "web"
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root(session: Optional[str] = Cookie(None)):
    """Serve login page or redirect to app if authenticated."""
    # Check if authenticated
    if session and session in auth_sessions and time.time() < auth_sessions[session]:
        return RedirectResponse(url="/app", status_code=302)

    # Serve login page
    login_path = web_dir / "login.html"
    if login_path.exists():
        return FileResponse(login_path)
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head><title>ProcAgent - Login</title></head>
    <body>
        <h1>ProcAgent</h1>
        <p>Login page not found. Please ensure procagent/web/login.html exists.</p>
    </body>
    </html>
    """)


@app.get("/app", response_class=HTMLResponse)
async def app_page(session: Optional[str] = Cookie(None)):
    """Serve the main application (requires auth)."""
    # Check authentication
    if not session or session not in auth_sessions or time.time() >= auth_sessions[session]:
        return RedirectResponse(url="/", status_code=302)

    # Serve main app
    index_path = web_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head><title>ProcAgent</title></head>
    <body>
        <h1>ProcAgent</h1>
        <p>Web interface not found. Please ensure procagent/web/index.html exists.</p>
    </body>
    </html>
    """)


# ============================================================================
# Health check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "sessions": len(sessions)
    }


# ============================================================================
# Authentication endpoints
# ============================================================================

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
        logger.info(f"User logged in: {username}")
        return {"success": True, "redirect": "/app"}

    logger.warning(f"Failed login attempt for user: {username}")
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.post("/api/logout")
async def logout(response: Response, session: Optional[str] = Cookie(None)):
    """Clear user session."""
    if session and session in auth_sessions:
        del auth_sessions[session]
        logger.info("User logged out")
    response.delete_cookie("session")
    return {"success": True, "redirect": "/"}


@app.get("/api/auth/status")
async def auth_status(session: Optional[str] = Cookie(None)):
    """Check if user is authenticated."""
    if session and session in auth_sessions:
        if time.time() < auth_sessions[session]:
            return {"authenticated": True}
        else:
            # Session expired, clean up
            del auth_sessions[session]
    return {"authenticated": False}


# ============================================================================
# VNC connection info
# ============================================================================

@app.get("/vnc/{session_id}")
async def get_vnc_info(session_id: str):
    """Get VNC connection information for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    settings = get_settings()
    return {
        "host": settings.vnc.host,
        "port": settings.vnc.port,
        "websockify_port": settings.vnc.websockify_port,
        "password": settings.vnc.password,
    }


# ============================================================================
# WebSocket chat endpoint
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for chat communication.

    Protocol:
    - Server sends: {"type": "session_created", "session_id": "..."}
    - Client sends: {"message": "...", "pfd_image": "base64...", "stream_data": {...}}
    - Server sends: {"type": "text|tool_use|results|error", ...}
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())
    agent: Optional[ProcAgentCore] = None

    try:
        # Create session
        settings = get_settings()
        working_dir = Path(settings.promax.working_dir) / session_id
        working_dir.mkdir(parents=True, exist_ok=True)

        agent = ProcAgentCore(
            session_id=session_id,
            working_dir=working_dir
        )
        sessions[session_id] = agent

        # Send session created message
        await websocket.send_json({
            "type": "session_created",
            "session_id": session_id,
        })
        logger.info(f"Session created: {session_id}")

        # Message processing loop
        while True:
            # Receive message
            data = await websocket.receive_json()

            # Parse as ChatMessage
            chat_message = ChatMessage(
                message=data.get("message", ""),
                pfd_image=data.get("pfd_image"),
                stream_data=data.get("stream_data"),
            )

            # Process message and stream responses
            async for response in agent.process_message(chat_message):
                await websocket.send_json(response.model_dump(mode="json"))

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "content": str(e)
            })
        except Exception:
            pass

    finally:
        # Cleanup
        if agent:
            await agent.cleanup()
        if session_id in sessions:
            del sessions[session_id]
        logger.info(f"Session cleaned up: {session_id}")


# ============================================================================
# File download endpoint
# ============================================================================

@app.get("/download/{session_id}/{filename}")
async def download_file(session_id: str, filename: str):
    """Download a project file from a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    settings = get_settings()
    file_path = Path(settings.promax.working_dir) / session_id / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )


# ============================================================================
# Main entry point
# ============================================================================

def main():
    """Run the server with proper Windows event loop for subprocess support."""
    import uvicorn

    settings = get_settings()

    # Windows requires ProactorEventLoop for subprocess support (Claude Agent SDK)
    if sys.platform == 'win32':
        # Create ProactorEventLoop and set it as the running loop
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)

        # Run uvicorn with the loop parameter (no reload to keep single process)
        config = uvicorn.Config(
            "procagent.server.app:app",
            host=settings.server.host,
            port=settings.server.port,
            reload=False,  # Disable reload to use our event loop
            log_level="info",
            loop="none",  # Don't let uvicorn manage the loop
        )
        server = uvicorn.Server(config)
        loop.run_until_complete(server.serve())
    else:
        # On non-Windows, use standard uvicorn
        uvicorn.run(
            "procagent.server.app:app",
            host=settings.server.host,
            port=settings.server.port,
            reload=True,
            log_level="info",
        )


if __name__ == "__main__":
    main()
