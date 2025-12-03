# ProcAgent Requirements Document

## Introduction

ProcAgent is an AI copilot designed to assist junior chemical/process engineers in using ProMax, a Windows-based process simulation software. Built primarily on the **ProMax COM API** for reliable programmatic control, ProcAgent aims to lower the barrier to entry for engineers new to the industry by automating workflow creation from Process Flow Diagrams (PFDs), intelligently populating block parameters, optimizing configurations to meet operational targets, and providing educational explanations throughout the process.

**Architecture:** ProcAgent is delivered as a web-based SaaS application. Users access the system through a web browser, while ProMax runs on backend sandbox servers managed by the ProcAgent service. This architecture ensures that corporate users can utilize ProcAgent without needing to install any software on their work laptops, addressing common IT policy restrictions in enterprise environments.

**Technical Approach:**
- **ProMax COM API (Primary):** The system uses the ProMax COM API as the primary mechanism for all ProMax interactions - creating blocks, setting parameters, running simulations, and reading results. This provides reliable, efficient, and deterministic programmatic control.
- **TightVNC (Visibility):** Users can see what is happening on the backend ProMax instance via TightVNC streaming. This enables visual monitoring and allows users to intervene when needed.
- **Claude Computer Use Agent (Fallback):** For edge cases where the COM API cannot accomplish a specific task, Claude's native computer use capabilities (CUA with coordinate-based interactions) can be used as a fallback mechanism for GUI automation.

This MVP focuses on ProMax integration only and targets investor/user demonstrations. The system provides a user-friendly browser-based chat interface with live TightVNC streaming of the backend ProMax sandbox, enabling human-in-the-loop control where users can visually monitor, pause, intervene, and resume AI operations.

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

1. User uploads PFD image and circles the Amine Treater (301-E), or describes it via chat
2. System uses multimodal AI to identify the highlighted block as an Amine Treater column
3. System creates single Amine Treater column in ProMax
4. User provides stream data for parameter population
5. System runs simulation and displays results
6. System compares results to performance targets
7. If targets not met, system suggests parameter adjustments
8. User can manually request another run with adjusted parameters

---

## Priority Classification

### P0 - Must Demo (Core MVP)

These features are essential for the 1-month demo timeline:

| Requirement | Scope for Demo |
|-------------|----------------|
| Req 1: Single Block Creation from PFD or Chat | User uploads PFD image and highlights block OR describes via chat. AI uses multimodal vision to identify block type from image. Creates ONE block (e.g., Amine Treater) in ProMax. NOT full PFD interpretation of all blocks. |
| Req 2: Parameter Population | Fill parameters based on user-provided inlet stream data. Simplified approach without smart inference. |
| Req 3: Single Simulation Run | Run simulation once, display results, compare to targets. Defer multi-iteration optimization. |
| Req 5: Chat + Streaming UI | Basic functional chat interface with live ProMax streaming view. |

### P1 - If Time Permits

These features are nice-to-have if time remains after P0 completion:

| Requirement | Scope for Demo |
|-------------|----------------|
| Req 4: Basic Explanations | Simple explanations of why targets were/were not met. |
| Req 3 (partial): Manual Iterations | 1-2 manual iterations with AI suggestions for parameter adjustments. |
| Req 7: File Download | ProMax file download only, skip report generation. |

### P2 - Post-Demo (Out of MVP Scope)

These features are deferred to future releases:

- Full PFD interpretation with automatic detection of ALL blocks and connections (multi-block workflow)
- Automatic equipment detection without user highlighting
- Human-in-the-loop pause/resume with state re-assessment (Req 6)
- Full educational content and "learn more" features
- Report generation (PDF/Excel/Word)
- Multi-iteration automatic optimization loop
- Multi-block workflow creation from comprehensive PFD analysis

---

## Requirements

### Requirement 1: Single Block Creation from PFD or Chat

**Priority:** P0 - Must Demo

**User Story:** As a junior process engineer, I want to upload a PFD image and highlight a specific block OR describe a process block via chat, so that ProcAgent can identify and create the corresponding block in ProMax without requiring me to know proper engineering terminology or manually navigate the software.

**Rationale:** Junior engineers often receive PFD diagrams from senior engineers or project documentation but may not know the proper terminology to describe equipment blocks. Image upload with visual highlighting provides a more natural and accessible way to specify which block they want to simulate.

#### Acceptance Criteria

1. WHEN the user uploads a PFD image (PNG, JPG, PDF), THEN the system SHALL accept the image and use multimodal AI to interpret it.

2. WHEN the user highlights or circles a specific area on the PFD image, THEN the system SHALL focus on identifying that specific equipment/block in the highlighted region.

3. WHEN interpreting the PFD image, THEN the system SHALL identify the block type (e.g., "Amine Treater column") and relevant stream connections shown in the diagram.

4. WHEN the user provides a text description of a block type (e.g., "Amine Treater column") and inlet stream conditions, THEN the system SHALL accept the input and begin block creation.

5. WHEN the user provides both an image and text description, THEN the system SHALL use the text to supplement and clarify the image interpretation.

6. WHEN the system receives a block specification (via image or text), THEN the system SHALL identify the appropriate ProMax block type.

7. WHEN creating the block, THEN the system SHALL create a single block in ProMax using the ProMax COM API on the backend sandbox instance.

8. WHEN the user specifies inlet and outlet stream names (or they are visible in the PFD), THEN the system SHALL create corresponding streams and connect them to the block.

9. IF the block specification is ambiguous or incomplete (whether from image or text), THEN the system SHALL prompt the user for clarification before proceeding.

10. WHEN the block creation is complete, THEN the system SHALL display a summary of the created block and its stream connections to the user.

#### Future Enhancement (P2)

- Full PFD interpretation with ALL blocks and connections (multi-block workflow creation)
- Automatic detection of all equipment without user highlighting
- Multi-block workflow creation from comprehensive PFD analysis

---

### Requirement 2: Parameter Population

**Priority:** P0 - Must Demo

**User Story:** As a junior process engineer, I want to provide inlet stream data and have the system populate block parameters, so that I have a working simulation configuration without manually entering every value.

#### Acceptance Criteria

**Environment and Component Initialization**

1. WHEN creating a new flowsheet in ProMax, THEN the system SHALL configure the thermodynamic environment with all required chemical components BEFORE creating any blocks or streams.

2. WHEN determining required components, THEN the system SHALL analyze all user-provided stream compositions and extract a complete list of chemical species needed for the simulation.

3. WHEN adding components to the environment, THEN the system SHALL use the ProMax COM API's component addition capability (e.g., `env.Components.Add("ComponentName")`) for each required species.

4. WHEN adding components, THEN the system SHALL use component names that exactly match the ProMax species database nomenclature (e.g., "Methane", "Ethane", "MDEA", "Hydrogen Sulfide").

5. IF a component name provided by the user does not match ProMax nomenclature, THEN the system SHALL attempt to map common names/aliases to the correct ProMax species name and notify the user of any unresolved components.

**Block and Stream Creation**

6. WHEN the thermodynamic environment is configured with all components, THEN the system SHALL proceed to create blocks and streams in the flowsheet.

7. WHEN a block is created in ProMax, THEN the system SHALL prompt the user to provide inlet stream data (composition, flow rate, temperature, pressure).

8. WHEN the user provides inlet stream data, THEN the system SHALL populate the corresponding stream properties in ProMax using the ProMax COM API.

**Stream Property and Composition Setting**

9. WHEN populating stream properties, THEN the system SHALL set temperature, pressure, and flow rate values BEFORE setting stream composition.

10. WHEN setting stream composition, THEN the system SHALL set all component values simultaneously using the phase composition SIValues property (tuple of mole fractions summing to 1.0).

11. WHEN stream properties and composition are set, THEN the system SHALL flash the stream to establish thermodynamic equilibrium.

**General Parameter Population**

12. WHEN populating block parameters, THEN the system SHALL use the provided stream data and basic engineering defaults for the block type.

13. WHEN parameters are populated, THEN the system SHALL display the populated values to the user for review.

14. IF any required parameter cannot be determined from user input or defaults, THEN the system SHALL notify the user that manual input is required.

15. WHEN parameters are displayed, THEN the system SHALL allow the user to review and modify any values before simulation.

**Order of Operations**

16. WHEN setting up a complete simulation, THEN the system SHALL follow this mandatory sequence:
    - Step 1: Create flowsheet
    - Step 2: Add all required components to the thermodynamic environment
    - Step 3: Create blocks and streams
    - Step 4: Set stream properties (temperature, pressure, flow rate)
    - Step 5: Set stream compositions
    - Step 6: Flash streams to establish equilibrium

#### Future Enhancement (P1/P2)

- Smart inference of parameters based on process context (upstream/downstream conditions)
- Explanations of why specific default values were chosen
- Industry-standard typical values based on process type

---

### Requirement 3: Simulation Execution and Results

**Priority:** P0 (single run) / P1 (manual iterations)

**User Story:** As a junior process engineer, I want to run a simulation and see results compared to my targets, so that I can understand if the configuration meets requirements and what adjustments might help.

#### Acceptance Criteria (P0 - Single Run)

1. WHEN the user requests to run a simulation, THEN the system SHALL execute the simulation in ProMax using the ProMax COM API.

2. WHEN the simulation completes, THEN the system SHALL retrieve results from ProMax using the ProMax COM API.

3. WHEN results are retrieved, THEN the system SHALL display key output values to the user in a clear format.

4. WHEN the user has specified performance targets, THEN the system SHALL compare results against those targets and indicate pass/fail status.

5. IF simulation results do not meet targets, THEN the system SHALL suggest which parameters might be adjusted to improve results.

#### Acceptance Criteria (P1 - Manual Iterations)

6. WHEN the user requests to run another simulation with adjusted parameters, THEN the system SHALL apply the parameter changes and re-run the simulation.

7. WHEN running follow-up iterations, THEN the system SHALL display current parameters, results, and comparison to previous runs.

8. WHEN each iteration completes, THEN the system SHALL record results for user review.

#### Future Enhancement (P2)

- Automatic multi-iteration optimization loop
- Maximum iteration limits with intelligent stopping criteria
- Parameter tuning recommendations based on process engineering principles
- Historical comparison across all iterations

---

### Requirement 4: Explainable AI and Education

**Priority:** P1 - If Time Permits

**User Story:** As a junior process engineer, I want the AI to explain why my targets were or were not met, so that I can learn from the simulation results and communicate findings to my team.

#### Acceptance Criteria (P1 - Basic Explanations)

1. WHEN simulation results do not meet targets, THEN the system SHALL provide a brief explanation of likely causes.

2. WHEN suggesting parameter adjustments, THEN the system SHALL explain why each adjustment is expected to improve results.

3. WHEN the user asks a question about results or configuration, THEN the system SHALL respond with relevant information.

#### Future Enhancement (P2)

- Optional "learn more" explanations for each major decision
- Educational content introducing industry-standard terminology
- Summary reports for sharing with managers
- Deep-dive explanations of process engineering concepts

---

### Requirement 5: User Interface - Browser-Based Chat and Streaming View

**Priority:** P0 - Must Demo

**User Story:** As a junior process engineer, I want a user-friendly browser-based chat interface with live visibility into what the AI is doing in ProMax on the backend, so that I can follow along, understand the process, and intervene if needed.

#### Acceptance Criteria

1. WHEN the user navigates to the ProcAgent web application, THEN the system SHALL present a browser-based chatbot interface as the primary input method for user commands and questions.

2. WHEN ProcAgent is operating on ProMax, THEN the system SHALL display a live streaming view of the backend ProMax sandbox instance using TightVNC (or similar remote desktop streaming technology) embedded in the browser.

3. WHILE the agent is performing actions via the COM API, THEN the system SHALL show real-time indicators of what actions are being taken (e.g., "Creating Amine Treater block", "Populating stream data").

4. WHEN displaying the TightVNC streaming view, THEN the system SHALL ensure minimal latency so users can follow agent actions in near real-time and see exactly what is happening in ProMax.

5. WHEN the user submits a message in the chat, THEN the system SHALL acknowledge receipt and provide status updates on processing.

6. WHEN accessing the web application, THEN the system SHALL support modern web browsers (Chrome, Firefox, Edge, Safari) without requiring browser plugins or extensions.

7. WHEN rendering the interface, THEN the system SHALL provide a responsive layout suitable for desktop and laptop screen sizes.

8. WHEN displaying the streaming view, THEN the system SHALL enable users to visually observe ProMax state changes made by the COM API, providing transparency into the automation process.

---

### Requirement 6: Human-in-the-Loop Control

**Priority:** P2 - Post-Demo

**User Story:** As a junior process engineer, I want to pause the AI agent, make manual changes in the streamed ProMax view via TightVNC, and then resume AI operation, so that I maintain control over the simulation and can apply my own judgment.

**MVP Note:** For the demo, users can stop/cancel operations and visually monitor via TightVNC streaming, but sophisticated pause/resume with state re-assessment is deferred to post-demo.

#### Acceptance Criteria (Future)

1. WHEN the user clicks the "Pause" button, THEN the system SHALL immediately halt all COM API operations on the backend ProMax instance.

2. WHEN the agent is paused, THEN the system SHALL allow the user to manually interact with the ProMax application through the TightVNC streaming view without interference.

3. WHEN the user clicks the "Resume" button after pausing, THEN the system SHALL re-assess the current ProMax state (via COM API queries) before continuing operations.

4. WHEN resuming, IF the user has made manual changes, THEN the system SHALL acknowledge those changes and incorporate them into its understanding of the current workflow state.

5. WHEN the agent is operating, THEN the system SHALL display a clear "Pause" control that is always accessible to the user in the browser interface.

6. IF the user makes changes that conflict with the AI's planned actions, THEN the system SHALL prompt the user to confirm how to proceed.

---

### Requirement 7: Export and Download Capability

**Priority:** P1 (file download) / P2 (reports)

**User Story:** As a junior process engineer, I want to download my completed work from the backend server, so that I can continue editing locally if I have ProMax, share with colleagues, or archive my projects.

#### Acceptance Criteria (P1 - File Download)

1. WHEN the user requests to export their work, THEN the system SHALL provide options to download ProMax project files (.prx or equivalent format).

2. WHEN exporting project files, THEN the system SHALL package all necessary files (project, streams, configurations) into a downloadable archive.

3. WHEN a simulation session is complete, THEN the system SHALL display export options prominently in the interface.

4. WHEN downloading files, THEN the system SHALL provide clear file names that identify the project and timestamp.

#### Future Enhancement (P2)

- Report generation in common formats (PDF, Excel, Word)
- Summary reports including simulation setup, parameters, and results
- Prompt to export before ending session with unsaved changes

---

## Non-Functional Requirements

### Requirement 8: Performance

**User Story:** As a user, I want the system to respond quickly to my inputs and perform simulations without excessive delays, so that I can work efficiently.

#### Acceptance Criteria

1. WHEN the user submits a chat message, THEN the system SHALL acknowledge the message within 2 seconds.

2. WHEN performing COM API operations on ProMax, THEN the system SHALL execute actions efficiently while maintaining reliability.

3. WHEN streaming the ProMax view via TightVNC to the browser, THEN the system SHALL maintain a frame rate sufficient for the user to follow agent actions (minimum 5 fps).

4. WHEN handling concurrent users, THEN the backend system SHALL provision isolated ProMax sandbox instances to maintain performance.

---

### Requirement 9: Reliability

**User Story:** As a user, I want the system to handle errors gracefully and not leave ProMax in an inconsistent state, so that I can trust the tool for important work.

#### Acceptance Criteria

1. IF an error occurs during block creation, THEN the system SHALL stop, notify the user, and provide options to retry or rollback.

2. IF the backend ProMax instance becomes unresponsive, THEN the system SHALL detect the condition and notify the user with recovery options.

3. WHEN performing multi-step operations, THEN the system SHALL implement checkpointing so partial progress is preserved on failure.

4. IF the browser connection is interrupted, THEN the system SHALL preserve session state on the backend and allow reconnection without data loss.

---

### Requirement 10: Compatibility

**User Story:** As a user, I want ProcAgent to work with my web browser without special configurations, so that I can access the service easily.

#### Acceptance Criteria

1. WHEN accessing the web application, THEN the system SHALL be compatible with the latest versions of Chrome, Firefox, Edge, and Safari browsers.

2. WHEN connecting to ProMax on the backend, THEN the backend system SHALL support standard ProMax installations without requiring modifications to ProMax.

3. WHEN using COM API integration, THEN the backend system SHALL handle different ProMax versions gracefully with appropriate version detection.

4. WHEN rendering the interface, THEN the system SHALL function correctly on screens with minimum resolution of 1280x720.

---

### Requirement 11: Security and Data Handling

**User Story:** As a user at an engineering firm, I want my simulation data and PFD uploads to be handled securely in the cloud environment, so that proprietary information is protected.

#### Acceptance Criteria

1. WHEN the user uploads files or provides data, THEN the system SHALL transmit the data securely over HTTPS/TLS to the backend server.

2. WHEN interacting with AI models, THEN the system SHALL use secure API connections (HTTPS/TLS).

3. WHEN storing session data, THEN the system SHALL maintain data on secure backend servers with appropriate access controls.

4. WHEN a user session ends, THEN the system SHALL provide options to download work before clearing session data from the backend.

5. WHEN handling user data, THEN the system SHALL isolate each user's ProMax sandbox instance to prevent data leakage between users.

6. WHEN authenticating users, THEN the system SHALL require secure login credentials before granting access to the application.

7. WHEN transmitting TightVNC streaming video of the ProMax sandbox, THEN the system SHALL use encrypted connections to protect visual data.

---

## Out of Scope (MVP)

The following items are explicitly out of scope for the MVP:

### Deferred to Post-Demo (P2)

- **Full PFD interpretation of ALL blocks** - MVP supports single-block identification from PFD with user highlighting; automatic detection of all equipment and connections is deferred
- **Multi-block workflow creation** - MVP focuses on single block (Amine Treater) creation
- **Automatic multi-iteration optimization** - MVP does single run + suggestions; user manually requests re-runs
- **Sophisticated pause/resume with state re-assessment** - MVP allows stop/cancel only
- **Report generation to PDF/Excel/Word formats** - MVP provides ProMax file download only
- **Full educational content** - MVP provides basic explanations only
- **Human-in-the-loop with state detection** - MVP defers complex state re-assessment on resume

### Out of Scope for All Releases (Current Planning)

- Support for simulation software other than ProMax
- Multi-user collaboration features (real-time collaborative editing)
- Mobile device interfaces (smartphone/tablet optimized views)
- Advanced optimization algorithms (genetic algorithms, etc.)
- Integration with external engineering databases
- Automated report generation to regulatory standards
- Self-hosted/on-premises deployment options
- Offline mode or local installation
