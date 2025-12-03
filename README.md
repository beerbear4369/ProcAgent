# ProcAgent

AI copilot for chemical process simulation using ProMax. Built on the **Claude Agent SDK**.

## Overview

ProcAgent enables users to create and run ProMax simulations through a chat interface, with AI-powered automation using:
- **ProMax COM API** - Primary execution via pywin32
- **Claude Computer Use** - Fallback GUI automation
- **Claude Skills** - Reusable workflow templates
- **TightVNC** - Interactive visual monitoring

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Single Physical Windows PC                        │
│                                                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │  ProMax App     │  │  TightVNC       │  │  ProcAgent Server       │  │
│  │  (VISIO.EXE)    │  │  Server         │  │  (FastAPI + Agent)      │  │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────────────┘  │
│           └────────────────────┴────────────────────┘                    │
└─────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

```powershell
# Install dependencies
pip install -r requirements.txt

# Set API key
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Start server
python -m procagent.server.app --port 8000

# Open browser to http://localhost:8000
```

## Project Structure

```
procagent/
├── procagent/
│   ├── agent/core.py           # ClaudeSDKClient orchestrator
│   ├── mcp/promax_server.py    # In-process MCP with COM API tools
│   ├── cua/computer_use.py     # Computer Use tool executor
│   ├── server/app.py           # FastAPI backend
│   ├── web/index.html          # Chat + noVNC frontend
│   └── skills/                 # Claude Skills for ProMax
│       ├── promax-amine-treater/
│       ├── promax-stream-setup/
│       └── promax-simulation-runner/
├── docs/
│   ├── design.md               # Full design document
│   ├── requirements.md         # Product requirements
│   └── promax_com_api_reference.md
├── config/
├── tests/
├── scripts/
└── requirements.txt
```

## Documentation

- [Design Document](docs/design.md) - Full architecture and implementation details
- [Requirements](docs/requirements.md) - Product requirements and acceptance criteria
- [ProMax COM API Reference](docs/promax_com_api_reference.md) - COM API documentation

## Key Features (MVP)

1. **Single Block Creation** - Create ProMax blocks via PFD upload or chat
2. **Parameter Population** - Fill block parameters from stream data
3. **Simulation Execution** - Run solver, display results, suggest adjustments
4. **Interactive VNC** - User can view and intervene in ProMax
5. **Intelligent Fallback** - COM API primary, Computer Use backup

## Requirements

- Windows 10/11
- ProMax installed and licensed
- Python 3.10+
- Node.js (required by Claude Agent SDK)
- TightVNC Server
- Anthropic API key with computer use beta access

## License

[To be determined]

## References

- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python)
- [Claude Skills](https://www.anthropic.com/news/skills)
- [Claude Computer Use](https://platform.claude.com/docs/en/build-with-claude/computer-use)
