# WhatsApp Automation Flow Builder — REST API Reference

All management endpoints require session authentication with role **Admin** or **Superadmin** (`CanManageAutomation`). External webhooks are protected via token verification.

---

## 1. Flow Management Endpoints

### 1.1 List / Create Flows
- **Endpoint**: `GET /api/flows/`
  - **Description**: Returns all accessible automation flows ordered by active status and update timestamp.
  - **Response 200 OK**:
    ```json
    [
      {
        "id": 12,
        "name": "Digipanda",
        "slug": "digipanda",
        "version": 1,
        "status": "published",
        "is_active": true,
        "trigger_type": "first_incoming_message",
        "trigger_keywords": "hi, hello, course, restart, start",
        "node_count": 8,
        "updated_at": "2026-10-22T17:04:30Z"
      }
    ]
    ```

- **Endpoint**: `POST /api/flows/`
  - **Description**: Creates a new flow with default start trigger and end nodes.
  - **Payload**:
    ```json
    {
      "name": "New Course Onboarding",
      "trigger_type": "first_incoming_message",
      "trigger_keywords": "course, join"
    }
    ```
  - **Response 201 Created**: Returns created flow object.

---

### 1.2 Retrieve / Update / Delete Flow
- **Endpoint**: `GET /api/flows/<id>/`
  - **Description**: Returns detailed flow definition including full `flow_data` graph.

- **Endpoint**: `PUT / PATCH /api/flows/<id>/`
  - **Description**: Saves draft graph modifications (`nodes`, `connections`, `viewport`).
  - **Immutable Guardrail**: If the flow is already `published`, returns HTTP 400 with code `PUBLISHED_IMMUTABLE` unless `auto_fork_draft=true` is supplied to fork a new draft.
  - **Payload**:
    ```json
    {
      "name": "Digipanda Admissions",
      "flow_data": {
        "nodes": [...],
        "connections": [...],
        "viewport": {"x": 0, "y": 0, "zoom": 1.0}
      }
    }
    ```

- **Endpoint**: `DELETE /api/flows/<id>/`
  - **Description**: Permanently removes the flow and related draft revisions.

---

## 2. Validation & Publishing Endpoints

### 2.1 Validate Flow Graph
- **Endpoint**: `POST /api/flows/<id>/validate/` or `POST /api/flows/validate/`
  - **Description**: Performs comprehensive server-side graph integrity check.
  - **Response 200 OK (Valid)**:
    ```json
    {
      "valid": true,
      "errors": [],
      "warnings": [],
      "error_count": 0,
      "warning_count": 0
    }
    ```
  - **Response 400 Bad Request (Invalid)**:
    ```json
    {
      "valid": false,
      "errors": [
        {"node_id": "node_buttons_8415", "message": "Buttons step has 4 options. Meta allows max 3 buttons."}
      ],
      "error_count": 1
    }
    ```

---

### 2.2 Publish Flow Version
- **Endpoint**: `POST /api/flows/<id>/publish/`
  - **Description**: Validates graph, atomically marks status as `published`, timestamps publication, and activates flow for live WhatsApp routing.
  - **Response 200 OK**:
    ```json
    {
      "valid": true,
      "message": "Flow \"Digipanda\" successfully published as Version 1!",
      "flow": { ... }
    }
    ```

---

## 3. Simulation & Version History

### 3.1 Step-by-Step Simulator
- **Endpoint**: `POST /api/flows/simulate/` or `POST /api/flows/<id>/simulate/`
  - **Description**: Executes pure in-memory dry-run step of the workflow without contacting Meta API or mutating CRM records.
  - **Payload**:
    ```json
    {
      "flow_data": { ... },
      "current_node_id": "node_buttons_7461",
      "interactive_reply": "opt_1",
      "collected_data": {}
    }
    ```
  - **Response 200 OK**:
    ```json
    {
      "success": true,
      "current_node_id": "node_buttons_8415",
      "waiting_for_input": true,
      "is_complete": false,
      "collected_data": {
        "interest_type": "Training"
      },
      "sim_messages": [
        {
          "type": "buttons",
          "body": "When are you planning to join?",
          "node_id": "node_buttons_8415"
        }
      ]
    }
    ```

---

### 3.2 Versions & Restoration
- **Endpoint**: `GET /api/flows/<id>/versions/`
  - **Description**: Returns version history list for the flow family.

- **Endpoint**: `POST /api/flows/<id>/restore-version/`
  - **Description**: Creates a new editable draft incrementing the version count based on an earlier published snapshot.
