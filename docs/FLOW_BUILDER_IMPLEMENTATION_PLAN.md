# WhatsApp Automation Flow Builder — Master Phased Implementation Plan

This implementation plan coordinates all 5 specialized agents across the 10 engineering phases:
1. **Planning & Requirements** (`planning-agent`)
2. **UI/UX Design & Motion Experience** (`ui-ux-agent`)
3. **Precision Implementation** (`developer-agent`)
4. **Comprehensive QA Testing** (`qa-testing-agent`)
5. **Root-Cause Debugging & Bug-Fixing** (`debugging-agent`)

---

## Phased Execution Roadmap

### Phase 1: Deep Project Inspection & Baseline Verification
- **Lead Agent**: `planning-agent`
- **Scope**:
  - Audit all models, views, API endpoints, engine kernel, and JavaScript handlers.
  - Establish defect classification and baseline test harness.
  - Deliver architecture, defect report, and master implementation plan.
- **Success Criteria**: 0 uninspected core modules; all architecture layers documented.

### Phase 2: Data Persistence & Model Integrity
- **Lead Agent**: `developer-agent`
- **Scope**:
  - Validate schema for `AutomationFlow`, `UserFlowSession`, and `AutomationExecution`.
  - Ensure draft graphs, node positions, connections, and version snapshots survive server restarts.
  - Implement optimistic concurrency protections on save.
- **Success Criteria**: Automated test verifying JSON round-trip and node position persistence after full reload.

### Phase 3: Visual Editor Ergonomics & Node Operations
- **Lead Agent**: `ui-ux-agent` & `developer-agent`
- **Scope**:
  - Refine drag-and-drop palette, click-to-add, viewport centering, and auto-scroll.
  - Implement dynamic next-node target dropdown updates in properties inspector.
  - Enhance visual feedback for Meta limits (3 buttons max, 10 list rows max).
  - Support keyboard shortcuts: `Ctrl+S`, `Ctrl+Z`, `Ctrl+Y`, `Delete`, `Escape`.
- **Success Criteria**: Adding nodes beyond 5 places them in full visible view; target dropdowns always show current nodes.

### Phase 4: Server-Side Validation & Versioning
- **Lead Agent**: `developer-agent` & `planning-agent`
- **Scope**:
  - Enforce server-side graph validation via `validate_flow_graph`.
  - Disallow mutation of published flows without explicit draft forking.
  - Support version restoration into new drafts with incremented version counter.
- **Success Criteria**: Publishing invalid flows returns HTTP 400 with actionable error messages; published flows remain immutable.

### Phase 5: Automation Execution Engine Kernel
- **Lead Agent**: `developer-agent`
- **Scope**:
  - Maintain state machine in `AutomationEngine` (`active`, `paused`, `handed_over`, `completed`, `expired`).
  - Support automatic re-triggering of completed/expired sessions upon receiving greeting keywords.
  - Support unique variable names for all questions and interactive selections.
  - Implement loop protection and depth limits ($< 25$ steps per cycle).
- **Success Criteria**: Customer conversation progresses step-by-step without premature exit or bot silence.

### Phase 6: In-Memory Safe Simulator
- **Lead Agent**: `developer-agent` & `ui-ux-agent`
- **Scope**:
  - Provide realistic chat bubble simulation for text, quick-reply buttons, and list menus.
  - Maintain session state and collected variables without calling external Meta API or mutating live CRM data.
  - Allow step-by-step debugging of branch routing and variable interpolation.
- **Success Criteria**: Simulator completes multi-step customer journeys matching live engine behavior.

### Phase 7: WhatsApp Business API Integration
- **Lead Agent**: `developer-agent` & `debugging-agent`
- **Scope**:
  - Secure webhook endpoint at `/webhook/whatsapp/` with token verification.
  - Handle inbound message deduplication using WhatsApp Message IDs (`wamid`).
  - Sanitize interactive payloads to strictly satisfy Meta Cloud API limits.
  - Deliver graceful fallbacks when interactive elements cannot be formatted.
- **Success Criteria**: Real WhatsApp incoming events route accurately to the active published flow.

### Phase 8: CRM & Lead Integration
- **Lead Agent**: `developer-agent`
- **Scope**:
  - Automatically associate incoming conversations with CRM leads via `ensure_lead_for_conversation`.
  - Synchronize collected student preferences (`interest_type`, `joining_timeframe`, `student_status`, `training_mode`, `program_duration`) to CRM lead fields.
  - Record execution timeline and counselor assignments.
- **Success Criteria**: Student answers appear immediately inside the CRM lead profile and timeline.

### Phase 9: Security, Authorization & Reliability
- **Lead Agent**: `developer-agent` & `debugging-agent`
- **Scope**:
  - Enforce role-based access control (`CanManageAutomation` restricted to Admin/Superadmin).
  - Verify CSRF protection on session-authenticated API endpoints.
  - Ensure transaction isolation and database connection resilience.
- **Success Criteria**: Non-admin users receive HTTP 403 Forbidden on flow management APIs.

### Phase 10: Comprehensive QA & Verification
- **Lead Agent**: `qa-testing-agent` & `debugging-agent`
- **Scope**:
  - Execute automated Django test suite (`chat.tests_flow_builder`).
  - Run multi-step end-to-end integration and simulation tests.
  - Verify zero console errors, zero 404s, and clean Django system checks.
- **Success Criteria**: 100% test pass rate with zero silenced warnings or unresolved defects.
