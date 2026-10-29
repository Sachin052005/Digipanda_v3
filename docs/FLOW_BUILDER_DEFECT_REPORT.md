# WhatsApp Automation Flow Builder — Defect & Resolution Report

This document records all identified architectural, logical, UI/UX, and runtime defects discovered in the WhatsApp Automation Flow Builder, categorized by standard engineering severity:

- **P0**: Critical security, permanent lockout, or production execution failure.
- **P1**: Core feature broken, data loss, or corrupted graph connectivity.
- **P2**: Incomplete feature, limits mismatch, or navigation failure.
- **P3**: Minor usability, visual styling, or ergonomics defect.

---

## Defect Inventory & Resolution Matrix

| Issue ID | Severity | Component | Defect Summary | Root Cause | Status | Resolution |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **DEF-001** | **P0** | `engine.py` | Permanent bot lockout after session completion | `engine.py` hardcoded `return False` on `STATUS_COMPLETED` and `STATUS_EXPIRED`, preventing any subsequent testing or greetings from the same phone number. | **RESOLVED** | Modified engine so completed/expired sessions re-evaluate triggers and greeting keywords (`hi`, `hello`, `course`, `restart`) to start fresh sessions. |
| **DEF-002** | **P1** | `flow_builder.js` / DB | Variable overwriting across sequential nodes | Sequential `buttons` steps defaulted to `variable_name = "choice"`, causing subsequent answers to overwrite earlier answers in CRM sync. | **RESOLVED** | Assigned unique variable identifiers (`interest_type`, `joining_timeframe`, `student_status`, `training_mode`, `program_duration`). |
| **DEF-003** | **P1** | `flow_builder.js` | Connection targets out-of-sync in properties inspector | `refreshNextNodeOptions()` was only called on initial page load, so newly created nodes were missing from the target dropdown. | **RESOLVED** | Integrated `refreshNextNodeOptions()` directly into `selectNode()` so all newly added nodes appear instantly. |
| **DEF-004** | **P2** | `flow_builder.js` | Newly added nodes placed off-screen | `addNewNode()` computed `posY = maxY + 180` without auto-scrolling the viewport, causing nodes beyond 5 to appear off-screen and invisible. | **RESOLVED** | Updated positioning logic to center on the current visible viewport or near selected node, with automatic smooth scroll. |
| **DEF-005** | **P2** | `flow_builder.js` | Meta API 3-button limit confusion | Users attempted to add 4-5 answers to a Buttons step, hitting the Meta limit with no explanatory guidance. | **RESOLVED** | Added prominent in-editor warning badge explaining Meta's 3-button restriction and guiding users to use **List Menu** for 4–10 options. |
| **DEF-006** | **P2** | `urls.py` | 404 error when navigating to `/builder/` path | Router only mapped `/automation/<id>/`; user URLs with trailing `/builder/` returned HTTP 404. | **RESOLVED** | Added explicit alias routes in `urls.py` for `/chat/automations/<id>/builder/` and `/automations/<id>/builder/`. |
| **DEF-007** | **P2** | `messages.py` | Potential Meta API rejection on oversized row/button titles | Meta strictly rejects button titles $> 20$ chars and list row titles $> 24$ chars. | **RESOLVED** | Enforced client-side `maxlength` attributes and server-side string slicing sanitization in `send_interactive_buttons` and `send_interactive_list`. |
| **DEF-008** | **P3** | `flow_builder.css` | Node connection curves clipping on deep zoom levels | SVG canvas bounds did not expand dynamically with negative node coordinates. | **RESOLVED** | Bounded node drag boundaries to minimum positive coordinates (`Math.max(40, x)`) to prevent canvas boundary overflow. |

---

## Verification Summary
- **P0 Defect Count**: 1 (Resolved & Verified)
- **P1 Defect Count**: 2 (Resolved & Verified)
- **P2 Defect Count**: 4 (Resolved & Verified)
- **P3 Defect Count**: 1 (Resolved & Verified)
- **Total Open Defects**: 0
