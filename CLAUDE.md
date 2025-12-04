# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ProcAgent is an AI copilot for chemical process simulation using ProMax. It uses the Claude Agent SDK to orchestrate interactions between a chat interface and ProMax automation via COM API, with Claude Computer Use as a fallback.

**Target Environment:** Single Windows PC running ProMax, TightVNC, and the ProcAgent server.

## Build and Run Commands

```powershell
# Install dependencies
pip install -r requirements.txt

# Set API key
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Start server
python -m procagent.server.app --port 8000

# Run tests
pytest tests/

# Run a single test
pytest tests/test_promax_mcp.py::test_create_stream -v
```

## Architecture

```
Browser (Chat + noVNC)
    ↓ WebSocket
FastAPI Backend (procagent/server/app.py)
    ↓
Claude Agent SDK (procagent/agent/core.py)
    ├── ProMax MCP Server (procagent/mcp/promax_server.py) → pywin32 COM → ProMax
    └── Computer Use MCP (procagent/cua/computer_use.py) → pyautogui → Screen
```

**Key Design Decisions:**
- ProMax COM API is the **primary** execution path (reliable, deterministic)
- Claude Computer Use is **fallback** for edge cases where COM cannot accomplish a task
- TightVNC streams the ProMax window to the browser (user can intervene)
- Claude Skills (SKILL.md files in `procagent/skills/`) provide workflow templates

## ProMax COM API

ProMax runs inside VISIO.EXE. Two connection modes:
- `ProMax.ProMax` - Background mode (data only, no visual shapes)
- `ProMax.ProMaxOutOfProc` - GUI mode (creates both data AND Visio shapes)

**Critical sequence for stream setup:**
1. Add components to environment first
2. Set temperature, pressure, flow rate
3. Set composition (must sum to 1.0)
4. Flash the stream

Reference implementation: `procagent/mcp/promax_server_reference.py`
API reference: `docs/promax_com_api_reference.md`

## Spec Documents

- `.claude/specs/requirements.md` - Product requirements (P0/P1/P2 priority)
- `.claude/specs/design.md` - Full architecture and component design
- `.claude/specs/tasks.md` - Implementation task list

## Demo Scenario

The MVP demonstrates a single Amine Treater (301-E) simulation:
- Block type: Staged Column for H2S/CO2 removal with MDEA
- Performance targets: Offgas H2S ≤100 ppm, Rich Amine Loading ≤0.45 mol/mol
- Example script: `scripts/promax_301e_amine_treater.py`


## Claude Agent SDK Integration

### Windows Event Loop Issue

**Problem:** Claude Agent SDK spawns `claude.exe` as a subprocess. Windows asyncio's default `SelectorEventLoop` does NOT support subprocess creation, causing `NotImplementedError`.

**Solution:** Use `ProactorEventLoop` and configure uvicorn to not override it:

```python
# In app.py main()
if sys.platform == 'win32':
    loop = asyncio.ProactorEventLoop()
    asyncio.set_event_loop(loop)

    config = uvicorn.Config(
        "procagent.server.app:app",
        loop="none",  # Don't let uvicorn manage the loop
        reload=False,  # Disable reload to keep single process
    )
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())
```

**Key points:**
- Setting `asyncio.set_event_loop_policy()` at module level is NOT enough - uvicorn creates its own loop later
- Must create loop BEFORE uvicorn starts and pass `loop="none"`
- `reload=False` required to maintain single process with our event loop

### MCP Server Configuration

**Wrong:** Passing Python objects as a list
```python
# DON'T DO THIS
options = ClaudeAgentOptions(
    mcp_servers=[server1, server2],  # List of objects - WRONG
)
```

**Correct:** Pass as dictionary with server names as keys
```python
# CORRECT
options = ClaudeAgentOptions(
    mcp_servers={
        "promax": server,      # Dict with name as key
        "computer": server2,
    },
    allowed_tools=["mcp__promax__connect_promax", ...],  # Must specify allowed tools
)
```

### SDK Authentication

Claude Agent SDK can authenticate via:
1. **API Key:** Set `ANTHROPIC_API_KEY` environment variable
2. **Max Subscription:** Run `claude.exe` to authenticate with browser OAuth

The bundled CLI is at: `site-packages/claude_agent_sdk/_bundled/claude.exe`

## User instruction
- https://platform.claude.com/docs/en/agent-sdk/python - Claude Agent SDK docs
- Use Max subscription for development (no API costs)