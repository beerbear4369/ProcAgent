# ProcAgent MVP Implementation Plan

This implementation plan provides a phased, test-driven approach to building the ProcAgent MVP. Tasks are organized to deliver incremental value, with P0 (Must Demo) requirements prioritized first.

---

## Phase 1: Project Foundation and Core Infrastructure

- [x] 1. Set up project structure and development environment
  - Create the procagent directory structure as defined in design (agent/, mcp/, cua/, server/, web/, skills/)
  - Initialize Python virtual environment and install core dependencies (fastapi, uvicorn, pywin32, websockets)
  - Create requirements.txt with all dependencies
  - Set up configuration module with settings.yaml for API keys and ports
  - Create basic logging infrastructure
  - _Requirements: Req 9.1 (single PC deployment), Req 9.2 (startup prerequisites)_

- [x] 2. Create core data models and type definitions
  - Implement Pydantic models for ProcAgentSession, BlockIdentification, StreamSpec
  - Implement StreamProperties, PerformanceTarget, SimulationResult models
  - Implement ResultsComparison, TargetAssessment, AdjustmentSuggestion models
  - Implement WebSocket message models (ChatMessage, AgentResponse)
  - Write unit tests for model validation (composition sum validation, temperature range, pressure validation)
  - _Requirements: Req 2.9 (composition validation), Req 2.10 (property ordering)_

---

## Phase 2: ProMax MCP Server (COM API Integration)

- [x] 3. Implement ProMax MCP Server foundation
  - Create promax_server.py with MCP server factory function
  - Implement COM connection state management (_state dictionary)
  - Implement _get_promax() helper for COM connection
  - Write mock-based unit tests for server initialization
  - _Requirements: Req 1.5 (COM API block creation), Req 2.6 (COM API for blocks/streams)_

- [x] 4. Implement project and flowsheet management tools
  - [x] 4.1 Implement create_project tool
    - Create new ProMax project via pmx.New()
    - Return structured MCP response with project name
    - Write unit tests with mocked COM objects
    - _Requirements: Req 2.1 (flowsheet creation)_

  - [x] 4.2 Implement add_flowsheet tool
    - Add flowsheet to project via Flowsheets.Add()
    - Handle error case when no project exists
    - Write unit tests for success and error cases
    - _Requirements: Req 2.1 (flowsheet creation)_

  - [x] 4.3 Implement add_components tool
    - Add chemical components to environment via env.Components.Add()
    - Track added and failed components
    - Return summary with success/failure counts
    - Write unit tests for component addition
    - _Requirements: Req 2.2 (component extraction), Req 2.3 (component addition), Req 2.4 (ProMax nomenclature)_

- [x] 5. Implement block creation tool
  - Implement create_block tool with block type mapping (AmineTreater, Separator, HeatExchanger, etc.)
  - Map block types to Visio stencils and master shapes (Column.vss/Distill, Separators.vss, etc.)
  - Implement Visio shape drop at specified coordinates
  - Handle unknown block type error case
  - Write unit tests for block creation with mock Visio objects
  - _Requirements: Req 1.4 (block type mapping), Req 1.5 (COM API block creation)_

- [x] 6. Implement stream creation and connection tools
  - [x] 6.1 Implement create_stream tool
    - Drop Process Stream shape from Streams.vss stencil
    - Position stream at specified x,y coordinates
    - Set stream name
    - Write unit tests for stream creation
    - _Requirements: Req 1.6 (stream creation and connection)_

  - [x] 6.2 Implement connect_stream tool
    - Connect stream to block port using Visio GlueTo
    - Handle inlet vs outlet connections (EndX vs BeginX)
    - Map port_index to Connections.X cell
    - Write unit tests for stream connection
    - _Requirements: Req 1.6 (stream creation and connection)_

- [x] 7. Implement stream property and composition tools
  - [x] 7.1 Implement set_stream_properties tool
    - Set temperature (C to K conversion)
    - Set pressure (kPa to Pa conversion)
    - Set molar flow (kmol/h to mol/s conversion)
    - Set mass flow (kg/h to kg/s conversion)
    - Write unit tests for unit conversions
    - _Requirements: Req 2.7 (prompt for inlet stream data), Req 2.8 (populate stream properties), Req 2.9 (property ordering)_

  - [x] 7.2 Implement set_stream_composition tool
    - Validate composition sums to 1.0 (within 0.001 tolerance)
    - Build composition array matching environment component order
    - Set composition via SIValues tuple
    - Write unit tests for composition validation and setting
    - _Requirements: Req 2.10 (composition setting via SIValues)_

  - [x] 7.3 Implement flash_stream tool
    - Call stream.Flash() to establish thermodynamic equilibrium
    - Write unit test for flash operation
    - _Requirements: Req 2.11 (flash streams)_

- [x] 8. Implement simulation execution and results tools
  - [x] 8.1 Implement run_simulation tool
    - Execute solver via flowsheet.Solver.Solve()
    - Interpret status code (>=1 converged, 0 not converged, <0 error)
    - Return convergence status message
    - _Requirements: Req 3.1 (execute simulation), Req 3.2 (retrieve results)_

  - [x] 8.2 Implement get_stream_results tool
    - Retrieve temperature, pressure, molar flow for specified streams
    - Retrieve composition for specified streams
    - _Requirements: Req 3.2 (retrieve results), Req 3.3 (display results)_

  - [x] 8.3 Implement list_streams and list_blocks tools
    - List all streams in flowsheet
    - List all blocks in flowsheet
    - _Requirements: Req 3.3 (display results)_

  - [ ] 8.4 Implement save_project tool
    - Save project to specified file path via SaveAs()
    - _Requirements: Req 6.1 (save project), Req 6.2 (download link)_

---

## Phase 3: Computer Use MCP Server (Fallback Mechanism) - DEFERRED

> **Status:** Deferred - COM API is working well for MVP. Computer Use fallback is P2.

- [ ] 9. Implement Computer Use MCP Server (P2 - Deferred)
  - _Deferred until COM API limitations are encountered_
  - _Requirements: Req 1.9 (Computer Use fallback), Req 8.3 (fallback for COM failures)_

---

## Phase 4: Claude Agent Core (Orchestrator)

- [x] 10. Implement ProcAgentCore class foundation
  - Create core.py with ProcAgentCore class
  - Implement constructor accepting session_id, MCP servers, working_dir
  - Implement initialize() method to create ClaudeSDKClient with options
  - Configure MCP servers, allowed tools, system prompt
  - _Requirements: Req 4.1 (browser chat interface), Req 7.1 (3-second acknowledgment)_

- [x] 11. Implement system prompt for ProMax operations
  - Build comprehensive system prompt with tool descriptions
  - Include workflow guidance for block and stream creation
  - _Requirements: Req 1.1-1.4 (block identification), Req 2.15 (setup sequence)_

- [x] 12. Implement user message processing
  - [x] 12.1 Implement process_user_message async generator
    - Build prompt parts with optional image and stream data
    - Send query to Claude Agent SDK
    - Yield streaming responses (text, tool_use, result)
    - _Requirements: Req 1.2 (PFD image upload), Req 4.2 (message acknowledgment)_

  - [ ] 12.2 Implement multimodal input handling (P1)
    - Accept PFD image as bytes and convert to base64
    - Include image in prompt for multimodal analysis
    - _Requirements: Req 1.2 (PFD image interpretation), Req 1.3 (image + text combination)_

- [ ] 13. Implement tool validation hooks (P1 - Optional)
  - Composition validation, property range validation
  - _Requirements: Req 2.10 (composition must sum to 1.0)_

- [x] 14. Implement cleanup and resource management
  - Implement cleanup() method to close ClaudeSDKClient
  - Handle graceful shutdown of agent resources
  - _Requirements: Req 9.4 (single user session handling)_

---

## Phase 5: Backend Server (FastAPI + WebSocket)

- [x] 15. Implement FastAPI application foundation
  - Create app.py with FastAPI application
  - Configure CORS for localhost access
  - Mount static files directory for web assets
  - Implement root endpoint to serve index.html
  - _Requirements: Req 4.1 (browser-based interface), Req 9.1 (single PC deployment)_

- [x] 16. Implement WebSocket chat endpoint
  - [x] 16.1 Create WebSocket connection handler
    - Accept WebSocket connection, generate session_id
    - Create session and send session_created message
    - _Requirements: Req 4.1 (chat interface), Req 4.2 (message acknowledgment)_

  - [x] 16.2 Implement chat message processing loop
    - Initialize ProcAgentCore with MCP servers
    - Parse incoming chat messages, stream responses back
    - _Requirements: Req 4.2 (status updates), Req 4.3 (real-time status indicators)_

  - [x] 16.3 Implement error handling and cleanup
    - Handle WebSocketDisconnect gracefully
    - Clean up agent and session on disconnect
    - _Requirements: Req 8.1 (error notification)_

- [x] 17. Implement VNC connection endpoint
  - Create endpoint to return VNC connection info
  - _Requirements: Req 4.4 (VNC streaming), Req 4.6 (websockify proxy)_

---

## Phase 6: Session Management

- [x] 18. Implement SessionManager class
  - [x] 18.1 Session creation with unique session_id
    - _Requirements: Req 9.4 (single user session), Req 4.4 (fixed VNC port)_

  - [x] 18.2 VNC port allocation (fixed port 5900 for MVP)
    - _Requirements: Req 4.5 (pre-running TightVNC), Req 9.2 (TightVNC running)_

  - [ ] 18.3 Session timeout monitoring (P1)
    - Destroy session after timeout period
    - _Requirements: Req 9.4 (session lifecycle)_

---

## Phase 7: Web Frontend

- [x] 19. Implement HTML/CSS structure for chat interface
  - Create index.html with header, chat panel, VNC panel layout
  - Style message bubbles (user, assistant, tool)
  - Style input area with text input, send button, upload button
  - _Requirements: Req 4.1 (browser-based chat), Req 4.8 (1280x720 minimum)_

- [x] 20. Implement WebSocket communication
  - [x] 20.1 WebSocket connect with auto-reconnect
    - _Requirements: Req 4.1 (chat interface), Req 7.1 (3-second acknowledgment)_

  - [x] 20.2 Message handling (text, tool_use, error)
    - _Requirements: Req 4.2 (status updates), Req 4.3 (real-time status indicators)_

- [x] 21. Implement user input handling
  - [x] 21.1 Send message function
    - _Requirements: Req 4.1 (chat input)_

  - [ ] 21.2 File upload handling (P1)
    - Handle PFD image upload
    - _Requirements: Req 1.2 (PFD image upload)_

- [x] 22. Implement results display
  - Display tool results in chat
  - _Requirements: Req 3.3 (display results)_

- [x] 23. Integrate noVNC viewer
  - Add iframe for noVNC viewer
  - _Requirements: Req 4.4 (VNC streaming), Req 4.6 (noVNC via websockify)_

---

## Phase 8: Claude Skills (Workflow Templates)

- [x] 24. Create Amine Treater skill
  - Create skills/promax-amine-treater/SKILL.md
  - Document required components (MDEA, H2S, CO2, Water, hydrocarbons)
  - Document block creation steps (Distill from Column.vss)
  - Document stream configuration (4 ports: Sour Gas, Lean Amine, Treated Gas, Rich Amine)
  - Document typical operating conditions and performance targets
  - _Requirements: Req 1.4 (block type mapping), Req 3.4 (performance targets)_

- [x] 25. Create Stream Setup skill
  - Create skills/promax-stream-setup/SKILL.md
  - Document property setting order (T, P, flow, composition, flash)
  - Document composition rules (sum to 1.0, normalize if needed)
  - Document common errors and solutions
  - _Requirements: Req 2.15 (setup sequence), Req 2.10 (composition rules)_

- [x] 26. Create Simulation Runner skill
  - Create skills/promax-simulation-runner/SKILL.md
  - Document pre-simulation checklist
  - Document status code interpretation
  - Document result comparison methodology
  - Document common convergence issues
  - _Requirements: Req 3.1-3.5 (simulation execution and results)_

---

## Phase 9: Integration Testing

- [x] 27. Create E2E test playbooks for ProMax MCP Server
  - Created tests/e2e/test_mcp_tools.py with playbooks
  - separator_basic: Test full separator workflow
  - staged_column_amine: Test amine treater column
  - stream_properties: Test stream properties/composition/flash
  - list_operations: Test list_streams/list_blocks
  - _Requirements: Req 1.5, Req 2.6 (COM API operations)_

- [x] 28. Create Playwright regression test runner
  - Run tests via Playwright MCP through the chat UI
  - Verify success indicators from playbook responses
  - _Requirements: Req 4.1-4.3 (UI communication)_

---

## Phase 10: End-to-End Demo Testing

- [x] 30. E2E separator_basic test passing
  - Verified via Playwright regression test
  - All MCP tools working: connect, create_project, add_components, create_stream, create_block, connect_stream, set_stream_properties, set_stream_composition, flash_stream, run_simulation, list_streams, list_blocks, get_stream_results
  - _Requirements: All P0 requirements (Req 1, 2, 3, 4)_

- [x] 31. Server startup and manual testing documented
  - python -m procagent.server.app --port 8000
  - Navigate to http://127.0.0.1:8000
  - _Requirements: Req 9.2 (startup procedure)_

---

## Phase 11: P1 Features (Backlog)

- [ ] 32. PFD image upload and multimodal analysis
  - _Requirements: Req 1.2 (PFD image interpretation)_

- [ ] 33. Save project and file download
  - _Requirements: Req 6.1-6.3 (file export and download)_

- [ ] 34. Session timeout monitoring
  - _Requirements: Req 9.4 (session lifecycle)_

- [ ] 35. Tool validation hooks (composition sum, property ranges)
  - _Requirements: Req 2.10 (composition validation)_

---

## Progress Summary

**MVP Status: FUNCTIONAL ✅**

| Phase | Status | Notes |
|-------|--------|-------|
| 1. Foundation | ✅ Complete | Project structure, data models |
| 2. ProMax MCP | ✅ Complete | All 13 tools working |
| 3. Computer Use | ⏸️ Deferred | COM API sufficient for MVP |
| 4. Agent Core | ✅ Complete | Claude Agent SDK integration |
| 5. Backend Server | ✅ Complete | FastAPI + WebSocket |
| 6. Session Manager | ✅ Complete | Basic session handling |
| 7. Web Frontend | ✅ Complete | Chat UI + noVNC |
| 8. Skills | ✅ Complete | Workflow templates |
| 9. Integration Tests | ✅ Complete | Playwright E2E playbooks |
| 10. E2E Demo | ✅ Complete | separator_basic passing |
| 11. P1 Features | 📋 Backlog | Image upload, save project |

**Working MCP Tools:**
- connect_promax, create_project, add_components
- create_stream, create_block, connect_stream
- set_stream_properties, set_stream_composition, flash_stream
- run_simulation, list_streams, list_blocks, get_stream_results
