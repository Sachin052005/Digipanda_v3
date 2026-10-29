# WhatsApp Automation Flow Builder — Quality Assurance & Test Plan

This document outlines the test strategy, feature inventory, automated test suites, simulation protocols, and acceptance criteria.

---

## 1. Feature Test Inventory

| Category | Component / Feature | Test Cases Covered | Verification Method | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Editor Canvas** | Drag, Move, Pan, Zoom | Coordinates persist, minimap syncs, zoom buttons work. | Manual UI & JS event assertions | **PASS** |
| **Node Palette** | Add Nodes beyond 5 | Node placed in visible viewport, auto-scrolled, selected. | JS DOM integration | **PASS** |
| **Properties** | Target Dropdown Sync | `refreshNextNodeOptions()` runs on selection, targets updated. | JS & API assertions | **PASS** |
| **Meta Guardrails** | Button & List Limits | Buttons $> 3$ rejected with warning; titles capped at 20/24 chars. | `validator.py` unit tests | **PASS** |
| **Persistence** | Draft Autosave & Manual Save | Graph nodes and connections survive page refresh. | `tests_flow_builder.py` | **PASS** |
| **Publishing** | Validation & Immutability | Published flow cannot be mutated directly; draft forking required. | `tests_flow_builder.py` | **PASS** |
| **Engine Kernel** | Step-by-Step Routing | Inbound replies advance session along exact matching connections. | `simulate_step` & engine tests | **PASS** |
| **Re-Triggering** | Re-entry on Greeting | Completed session re-triggers on "Hi", "Hello", "Restart". | Engine simulation test | **PASS** |
| **CRM Sync** | Variable Capture | Unique variables saved to Lead without overwriting. | `crm.sync_answers` test | **PASS** |
| **Security** | Access Control | Non-admin users blocked with HTTP 403. | DRF permission tests | **PASS** |

---

## 2. Automated Test Execution Commands

### Run Full Flow Builder Test Suite
```bash
$env:DB_ENGINE="django.db.backends.sqlite3"; python manage.py test chat.tests_flow_builder
```

### Run Multi-Step Engine Simulation
```bash
python manage.py shell -c "
from chat.models import AutomationFlow
from chat.automation.engine import AutomationEngine

flow = AutomationFlow.objects.get(id=12)
s0 = AutomationEngine.simulate_step(flow.flow_data, message_text='Hi')
s1 = AutomationEngine.simulate_step(flow.flow_data, s0['current_node_id'], interactive_reply='opt_1', collected_data=s0['collected_data'])
s2 = AutomationEngine.simulate_step(flow.flow_data, s1['current_node_id'], interactive_reply='opt_1', collected_data=s1['collected_data'])
s3 = AutomationEngine.simulate_step(flow.flow_data, s2['current_node_id'], interactive_reply='row_2', collected_data=s2['collected_data'])
s4 = AutomationEngine.simulate_step(flow.flow_data, s3['current_node_id'], interactive_reply='opt_1', collected_data=s3['collected_data'])
s5 = AutomationEngine.simulate_step(flow.flow_data, s4['current_node_id'], interactive_reply='opt_2', collected_data=s4['collected_data'])
print('Simulation Result Complete:', s5['is_complete'])
print('Collected Lead Data:', s5['collected_data'])
"
```

---

## 3. Acceptance Verification Results
- `test_routes_exist_and_accessible_for_admin`: **PASS**
- `test_permissions_unauthorized_user_blocked`: **PASS**
- `test_update_draft_flow_success`: **PASS**
- `test_published_flow_cannot_be_mutated_directly`: **PASS**
- `test_published_flow_auto_fork_draft`: **PASS**
- `test_version_history_and_restore`: **PASS**
- `test_validator_detects_broken_or_orphan_nodes`: **PASS**
- `test_simulator_dry_run_step_execution`: **PASS**
- `test_end_to_end_create_new_flow_in_editor_lifecycle`: **PASS**
- **Test Results**: 9 passed, 0 failed, 0 errors in 11.74s.
