# WhatsApp Automation Flow Builder — Execution Engine Architecture

## 1. Engine Core Overview (`AutomationEngine`)

The `AutomationEngine` (`CRM/chat/automation/engine.py`) is the asynchronous, graph-driven state machine kernel executing WhatsApp conversational workflows. It runs independently of any active browser session.

```mermaid
stateDiagram-v2
    [*] --> InboundMessage
    InboundMessage --> SessionLookup

    state SessionLookup {
        ActiveSession --> ContinueCurrentNode: User replies to question/button/list
        HandedOver --> Silent: Counselor in control
        CompletedOrExpired --> TriggerMatch: Check greetings / keywords
        NoSession --> TriggerMatch: Brand new customer
    }

    TriggerMatch --> CreateFreshSession: Match found (e.g. 'Hi', 'Course')
    TriggerMatch --> Silent: No trigger match

    CreateFreshSession --> ExecuteNode
    ContinueCurrentNode --> ExecuteNode

    state ExecuteNode {
        MessageNode --> SendText
        ButtonsNode --> SendButtons: Pause (waiting_for_input = True)
        ListNode --> SendListMenu: Pause (waiting_for_input = True)
        QuestionNode --> SendPrompt: Pause (waiting_for_input = True)
        ConditionNode --> EvaluateBranch: Branch YES / NO
        EndNode --> SendClosingText: Complete session
    }

    SendButtons --> [*]
    SendListMenu --> [*]
    SendPrompt --> [*]
    SendText --> AdvanceNextNode --> ExecuteNode
    EvaluateBranch --> AdvanceNextNode
    SendClosingText --> Completed --> [*]
```

---

## 2. Supported Node Types & Execution Handlers

| Node Type | Execution Behavior | Output Ports | State Transition |
| :--- | :--- | :--- | :--- |
| **`trigger` / `start`** | Evaluates entry conditions. Instantiates `UserFlowSession`. | `default` | Advances immediately to first connected node. |
| **`message`** | Interpolates `{{variable}}` placeholders and dispatches text message via WhatsApp Cloud API. | `default` | Immediate transition to next node (`depth + 1`). |
| **`buttons`** | Dispatches interactive quick-reply buttons (1–3 options). Saves selected option to `collected_data[variable_name]`. | `opt_1`, `opt_2`, `opt_3` | Sets `waiting_for_input = True`, pauses session until reply arrives. |
| **`list`** | Dispatches interactive list menu (up to 10 rows). Maps selection to `collected_data[variable_name]`. | `default` or row-specific ports | Sets `waiting_for_input = True`, pauses session. |
| **`question`** | Sends question prompt. Captures open text, validates format (email, number, phone), and retries on failure. | `default` | Sets `waiting_for_input = True`. |
| **`condition`** | Evaluates boolean expressions (`equals`, `contains`, `exists`). | `YES` / `NO` | Immediate branch transition based on variable evaluation. |
| **`save_data`** | Stores explicit static or transformed variable values into session. | `default` | Immediate transition. |
| **`media`** | Sends brochure PDF, image, or video attachment with optional caption. | `default` | Immediate transition. |
| **`location`** | Sends interactive WhatsApp GPS map pin for a designated academy branch. | `default` | Immediate transition. |
| **`lead_status`** | Updates CRM lead status (`Interested`, `Follow Up Required`, `Demo Scheduled`). | `default` | Immediate transition. |
| **`assign_telecaller`** | Executes round-robin or specific counselor assignment in CRM. | `default` | Immediate transition. |
| **`human_handover`** | Pauses bot, alerts staff, and sets status to `STATUS_HANDED_OVER`. | None (Terminal) | Session pauses permanently until agent returns conversation. |
| **`end`** | Sends closing text and sets status to `STATUS_COMPLETED`. | None (Terminal) | Marks session completed, persists summary. |

---

## 3. Re-Triggering & Session Lifecycle Mechanics
- **Completed / Expired Sessions**: When a customer finishes a flow and reaches `end_1`, the session status is recorded as `completed`.
- **Automatic Re-Entry**: When that customer messages again with standard greetings (`hi`, `hello`, `hey`, `start`, `restart`, `menu`) or configured keywords, the engine initiates a **fresh `UserFlowSession`** rather than locking the customer out.
- **Loop Protection**: Guarded by `MAX_DEPTH = 25` to prevent accidental instant cycle loops during synchronous linear transitions.
- **Audit Logging**: Every single transition emits a structured `AutomationExecution` record.
