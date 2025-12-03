# ProcAgent Requirements Document (MVP Demo)

## Introduction

ProcAgent is an AI copilot designed to assist junior chemical/process engineers in using ProMax, a Windows-based process simulation software. Built primarily on the **ProMax COM API** for reliable programmatic control, ProcAgent aims to lower the barrier to entry for engineers new to the industry by automating workflow creation from Process Flow Diagrams (PFDs), intelligently populating block parameters, and providing simulation execution with target comparison.

**MVP Architecture:** ProcAgent is a **single-PC local demo** application. The user runs a web browser on the same Windows PC where ProMax, the backend server, TightVNC, and all components run. This is NOT a multi-user SaaS deployment - it is a demonstration environment for investor/user presentations.

**Technical Approach:**
- **Claude Agent SDK:** Central orchestrator (`pip install claude-agent-sdk`) managing all AI interactions
- **ProMax COM API (Primary):** The system uses the ProMax COM API as the primary mechanism for all ProMax interactions - creating blocks, setting parameters, running simulations, and reading results
- **TightVNC (Visibility):** A single TightVNC service with a fixed port and password streams the ProMax window to the browser via noVNC, allowing the user to see what is happening
- **Claude Computer Use (Fallback):** For edge cases where the COM API cannot accomplish a specific task, Claude's native computer use capabilities (CUA with coordinate-based interactions) can be used as a fallback mechanism

This MVP focuses on ProMax integration only and targets investor/user demonstrations on a single Windows PC.

---

## Demo Use Case: Amine Treater (301-E) Simulation

For the 1-month MVP demo timeline, ProcAgent will demonstrate capabilities using a single-block Amine Treater simulation scenario.

### Process Description

- **Unit:** Amine Treater Column (301-E)
- **Purpose:** Remove H2S from sour offgas stream using amine absorption
- **Scope:** Single block focus for MVP demonstration

### Input Specifications

| Stream | Description |
|--------|-------------|
| Sour Offgas | Feed gas containing H2S, CO2, and hydrocarbons |
| Lean Amine | MDEA (Methyldiethanolamine) solution |

### Performance Targets

| Parameter | Target Value | Unit |
|-----------|--------------|------|
| Offgas H2S | <= 100 | ppm(mol) |
| Rich Amine Loading | <= 0.45 | mol H2S/mol amine |

### Test Scenarios

| Scenario | Lean Amine Loading | Expected Outcome |
|----------|-------------------|------------------|
| Base Case | 0.01 mol/mol | Should meet H2S target |
| High Loading | 0.02 mol/mol | May struggle to meet target |

### Demo Flow

1. User opens the web app in their browser (same PC as backend)
2. User describes a process block via chat OR uploads a PFD image and describes which block to focus on
3. System uses multimodal AI to understand the block type (e.g., Amine Treater column)
4. System creates single Amine Treater column in ProMax via COM API
5. User provides stream data for parameter population
6. System runs simulation and displays results
7. System compares results to performance targets
8. If targets not met, system suggests parameter adjustments
9. User can manually request another run with adjusted parameters

---

## Priority Classification

### P0 - Must Demo (Core MVP)

These features are essential for the 1-month demo timeline:

| Requirement | Scope for Demo |
|-------------|----------------|
| Req 1: Single Block Creation from Chat or PFD | User describes block via chat OR uploads PFD image with description. AI identifies block type. Creates ONE block (e.g., Amine Treater) in ProMax via COM API. |
| Req 2: Parameter Population | Fill parameters based on user-provided inlet stream data via COM API. |
| Req 3: Single Simulation Run | Run simulation once, display results, compare to targets. |
| Req 4: Chat + VNC Streaming UI | Basic chat interface with live ProMax view via TightVNC/noVNC. |

### P1 - If Time Permits

These features are nice-to-have if time remains after P0 completion:

| Requirement | Scope for Demo |
|-------------|----------------|
| Req 5: Basic Explanations | Simple explanations of why targets were/were not met. |
| Req 3 (partial): Manual Iterations | 1-2 manual iterations with AI suggestions for parameter adjustments. |
| Req 6: File Download | ProMax file download only, skip report generation. |

### P2 - Post-Demo (Out of MVP Scope)

These features are deferred to future releases:

- Full PFD interpretation with automatic detection of ALL blocks and connections
- Multi-block workflow creation
- Human-in-the-loop pause/resume with state re-assessment
- Report generation (PDF/Excel/Word)
- Multi-iteration automatic optimization loop
- Multi-user/multi-session architecture
- Cloud/SaaS deployment

---

## Requirements

### Requirement 1: Single Block Creation from Chat or PFD

**Priority:** P0 - Must Demo

**User Story:** As a junior process engineer, I want to describe a process block via chat or upload a PFD image and describe which block to focus on, so that ProcAgent can identify and create the corresponding block in ProMax without requiring me to manually navigate the software.

#### Acceptance Criteria

1. WHEN the user provides a text description of a block type (e.g., "Amine Treater column") via chat, THEN the system SHALL accept the input and identify the appropriate ProMax block type.

2. WHEN the user uploads a PFD image (PNG, JPG, PDF) along with a text description of which block to focus on, THEN the system SHALL use multimodal AI to interpret the image context.

3. WHEN the user provides both an image and text description, THEN the system SHALL use the text to identify which specific equipment/block they want to simulate.

4. WHEN the system receives a block specification (via text or image+text), THEN the system SHALL map it to the appropriate ProMax block type (e.g., "Amine Treater" maps to Staged Column).

5. WHEN creating the block, THEN the system SHALL create a single block in ProMax using the ProMax COM API.

6. WHEN the user specifies inlet and outlet stream names, THEN the system SHALL create corresponding streams and connect them to the block via COM API.

7. IF the block specification is ambiguous or incomplete, THEN the system SHALL prompt the user for clarification before proceeding.

8. WHEN the block creation is complete, THEN the system SHALL display a summary of the created block and its stream connections to the user.

9. IF the COM API cannot accomplish the block creation, THEN the system SHALL attempt to use Claude Computer Use as a fallback mechanism.

---

### Requirement 2: Parameter Population

**Priority:** P0 - Must Demo

**User Story:** As a junior process engineer, I want to provide inlet stream data and have the system populate block parameters via COM API, so that I have a working simulation configuration without manually entering every value.

#### Acceptance Criteria

**Environment and Component Initialization**

1. WHEN creating a new flowsheet in ProMax, THEN the system SHALL configure the thermodynamic environment with all required chemical components BEFORE creating any blocks or streams.

2. WHEN determining required components, THEN the system SHALL analyze all user-provided stream compositions and extract a complete list of chemical species needed for the simulation.

3. WHEN adding components to the environment, THEN the system SHALL use the ProMax COM API's component addition capability (e.g., `env.Components.Add("ComponentName")`) for each required species.

4. WHEN adding components, THEN the system SHALL use component names that exactly match the ProMax species database nomenclature (e.g., "Methane", "Ethane", "MDEA", "Hydrogen Sulfide").

5. IF a component name provided by the user does not match ProMax nomenclature, THEN the system SHALL attempt to map common names/aliases to the correct ProMax species name and notify the user of any unresolved components.

**Block and Stream Creation**

6. WHEN the thermodynamic environment is configured with all components, THEN the system SHALL proceed to create blocks and streams in the flowsheet using the COM API.

7. WHEN a block is created in ProMax, THEN the system SHALL prompt the user to provide inlet stream data (composition, flow rate, temperature, pressure).

8. WHEN the user provides inlet stream data, THEN the system SHALL populate the corresponding stream properties in ProMax using the COM API.

**Stream Property and Composition Setting**

9. WHEN populating stream properties, THEN the system SHALL set temperature, pressure, and flow rate values BEFORE setting stream composition.

10. WHEN setting stream composition, THEN the system SHALL set all component values simultaneously using the phase composition SIValues property (tuple of mole fractions summing to 1.0).

11. WHEN stream properties and composition are set, THEN the system SHALL flash the stream to establish thermodynamic equilibrium.

**General Parameter Population**

12. WHEN populating block parameters, THEN the system SHALL use the provided stream data and basic engineering defaults for the block type.

13. WHEN parameters are populated, THEN the system SHALL display the populated values to the user for review.

14. IF any required parameter cannot be determined from user input or defaults, THEN the system SHALL notify the user that manual input is required.

**Order of Operations**

15. WHEN setting up a complete simulation, THEN the system SHALL follow this mandatory sequence:
    - Step 1: Create flowsheet
    - Step 2: Add all required components to the thermodynamic environment
    - Step 3: Create blocks and streams
    - Step 4: Set stream properties (temperature, pressure, flow rate)
    - Step 5: Set stream compositions
    - Step 6: Flash streams to establish equilibrium

---

### Requirement 3: Simulation Execution and Results

**Priority:** P0 (single run) / P1 (manual iterations)

**User Story:** As a junior process engineer, I want to run a simulation and see results compared to my targets, so that I can understand if the configuration meets requirements and what adjustments might help.

#### Acceptance Criteria (P0 - Single Run)

1. WHEN the user requests to run a simulation, THEN the system SHALL execute the simulation in ProMax using the COM API (Solver.Solve).

2. WHEN the simulation completes, THEN the system SHALL retrieve results from ProMax using the COM API.

3. WHEN results are retrieved, THEN the system SHALL display key output values to the user in a clear format in the chat interface.

4. WHEN the user has specified performance targets, THEN the system SHALL compare results against those targets and indicate pass/fail status.

5. IF simulation results do not meet targets, THEN the system SHALL suggest which parameters might be adjusted to improve results.

#### Acceptance Criteria (P1 - Manual Iterations)

6. WHEN the user requests to run another simulation with adjusted parameters, THEN the system SHALL apply the parameter changes via COM API and re-run the simulation.

7. WHEN running follow-up iterations, THEN the system SHALL display current parameters, results, and comparison to previous runs.

---

### Requirement 4: User Interface - Browser-Based Chat with VNC Streaming

**Priority:** P0 - Must Demo

**User Story:** As a demo user, I want a browser-based chat interface with live visibility into what the AI is doing in ProMax, so that I can follow along and understand the process.

#### Acceptance Criteria

**Chat Interface**

1. WHEN the user navigates to the ProcAgent web application (localhost URL), THEN the system SHALL present a browser-based chat interface as the primary input method.

2. WHEN the user submits a message in the chat, THEN the system SHALL acknowledge receipt and provide status updates on processing.

3. WHILE the agent is performing actions via the COM API, THEN the system SHALL show real-time status indicators (e.g., "Creating Amine Treater block", "Populating stream data").

**VNC Streaming (Single Fixed Instance)**

4. WHEN displaying the ProMax view, THEN the system SHALL stream video from a single TightVNC server instance running on a fixed port (e.g., 5900) with a fixed password configured at deployment time.

5. WHEN the backend starts, THEN the system SHALL expect TightVNC to already be running - it does NOT spawn per-session VNC instances.

6. WHEN displaying the VNC stream, THEN the system SHALL use websockify to proxy the VNC connection to a noVNC viewer embedded in the browser.

7. WHEN rendering the VNC stream, THEN the system SHALL ensure minimal latency so users can follow agent actions in near real-time (minimum 5 fps).

**Browser Compatibility**

8. WHEN rendering the interface, THEN the system SHALL provide a responsive layout suitable for desktop screen sizes (minimum 1280x720).

9. WHEN accessing the web application, THEN the system SHALL support modern web browsers (Chrome, Firefox, Edge) without requiring browser plugins.

---

### Requirement 5: Explainable AI and Education

**Priority:** P1 - If Time Permits

**User Story:** As a junior process engineer, I want the AI to explain why my targets were or were not met, so that I can learn from the simulation results.

#### Acceptance Criteria (P1 - Basic Explanations)

1. WHEN simulation results do not meet targets, THEN the system SHALL provide a brief explanation of likely causes in the chat response.

2. WHEN suggesting parameter adjustments, THEN the system SHALL explain why each adjustment is expected to improve results.

3. WHEN the user asks a question about results or configuration, THEN the system SHALL respond with relevant information.

---

### Requirement 6: Export and Download Capability

**Priority:** P1 (file download)

**User Story:** As a demo user, I want to download the ProMax project file after the demo, so that I can keep a copy of the work.

#### Acceptance Criteria (P1 - File Download)

1. WHEN the user requests to export their work, THEN the system SHALL save the ProMax project using the COM API (Save method).

2. WHEN exporting project files, THEN the system SHALL provide a download link for the .prx file from the server's working directory.

3. WHEN downloading files, THEN the system SHALL provide clear file names that identify the project.

---

## Non-Functional Requirements

### Requirement 7: Performance

**User Story:** As a demo user, I want the system to respond reasonably quickly to my inputs, so that the demo flows smoothly.

#### Acceptance Criteria

1. WHEN the user submits a chat message, THEN the system SHALL acknowledge the message within 3 seconds.

2. WHEN performing COM API operations on ProMax, THEN the system SHALL execute actions and provide feedback to the user.

3. WHEN streaming the ProMax view via VNC to the browser, THEN the system SHALL maintain a frame rate sufficient for the user to follow agent actions (minimum 5 fps).

---

### Requirement 8: Reliability

**User Story:** As a demo user, I want the system to handle errors gracefully, so that the demo can recover from issues.

#### Acceptance Criteria

1. IF an error occurs during block creation or COM API operation, THEN the system SHALL notify the user with a clear error message and suggest recovery options (retry, restart).

2. IF the ProMax application becomes unresponsive, THEN the system SHALL detect the condition and notify the user.

3. IF a COM API operation fails, THEN the system SHALL consider using Claude Computer Use as a fallback (if applicable).

---

### Requirement 9: Single-PC Deployment

**User Story:** As a demo operator, I want to run the entire system on a single Windows PC without complex infrastructure setup.

#### Acceptance Criteria

1. WHEN deploying ProcAgent for demo, THEN the system SHALL run entirely on a single Windows PC (backend, ProMax, VNC, browser all on same machine).

2. WHEN starting the demo environment, THEN the operator SHALL:
   - Ensure ProMax is installed and licensed
   - Ensure TightVNC Server is running on a fixed port (e.g., 5900)
   - Start the ProcAgent backend server
   - Open a browser to localhost

3. WHEN the system is running, THEN the system SHALL NOT require cloud services, external servers, or multi-machine networking (except for Anthropic API calls).

4. WHEN handling user sessions, THEN the system SHALL support a single user at a time (no multi-tenancy).

---

## Out of Scope (MVP)

The following items are explicitly out of scope for the MVP:

### Deferred to Post-Demo (P2)

- **Full PFD interpretation of ALL blocks** - MVP supports single-block identification; automatic detection of all equipment is deferred
- **Multi-block workflow creation** - MVP focuses on single block (Amine Treater) creation
- **Automatic multi-iteration optimization** - MVP does single run + suggestions; user manually requests re-runs
- **Sophisticated pause/resume with state re-assessment** - MVP allows stop/cancel only
- **Report generation to PDF/Excel/Word formats** - MVP provides ProMax file download only
- **Human-in-the-loop with state detection** - MVP defers complex state re-assessment on resume
- **Block highlighting on PFD with annotation overlay** - Deferred; MVP uses text description to identify blocks

### Out of Scope for MVP Architecture

- **Multi-user SaaS deployment** - MVP is single-PC, single-user demo only
- **Per-session VNC spawning** - MVP uses single fixed VNC instance
- **User authentication and session isolation** - MVP has no login, no multi-tenancy
- **Cloud/distributed deployment** - MVP runs entirely on one Windows PC
- **Data persistence across sessions** - MVP treats each demo as a fresh start
- **Mobile device interfaces** - Desktop browser only
- **Support for simulation software other than ProMax**

---

## Architecture Summary (MVP)

```
Single Windows PC
├── Browser (Chrome/Firefox/Edge)
│   ├── Chat UI (WebSocket to backend)
│   └── noVNC Viewer (WebSocket via websockify)
│
├── ProcAgent Backend (FastAPI)
│   ├── Claude Agent SDK (orchestrator)
│   ├── ProMax MCP Server (COM API tools)
│   └── Computer Use Executor (fallback)
│
├── TightVNC Server (fixed port 5900, fixed password)
├── websockify (VNC to WebSocket proxy)
│
└── ProMax Application (COM automation target)
```

**Key Points:**
- Everything runs on ONE machine
- Single TightVNC instance, NOT per-session
- No authentication, no multi-user
- Anthropic API calls are the only external network dependency
