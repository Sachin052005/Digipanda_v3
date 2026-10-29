"""
Flow Graph Validator for WhatsApp Automation Engine.
Enforces structural integrity, port validity, reachability, and configuration rules
before publishing a flow.
"""

from typing import Dict, Any, List


def validate_flow_graph(flow_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates a graph-based flow definition.
    Returns:
    {
        "valid": bool,
        "errors": [{"node_id": str, "message": str}],
        "warnings": [{"node_id": str, "message": str}]
    }
    """
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []

    if not isinstance(flow_data, dict):
        return {
            "valid": False,
            "errors": [{"node_id": "root", "message": "Flow data must be a valid JSON object."}],
            "warnings": []
        }

    nodes = flow_data.get("nodes", [])
    connections = flow_data.get("connections") or flow_data.get("edges") or []

    if not isinstance(nodes, list) or len(nodes) == 0:
        return {
            "valid": False,
            "errors": [{"node_id": "root", "message": "Flow must contain at least one node."}],
            "warnings": []
        }

    node_map = {}
    trigger_nodes = []
    end_nodes = []

    for node in nodes:
        if not isinstance(node, dict) or "id" not in node:
            errors.append({"node_id": "unknown", "message": "Node is missing required 'id' attribute."})
            continue

        nid = node["id"]
        if nid in node_map:
            errors.append({"node_id": nid, "message": f"Duplicate node ID '{nid}' detected."})
        node_map[nid] = node

        ntype = node.get("type", "")
        if ntype in ["trigger", "start"]:
            trigger_nodes.append(node)
        elif ntype == "end":
            end_nodes.append(node)

        # Required node property checks
        if ntype == "question":
            var_name = node.get("variable_name") or node.get("data", {}).get("variable_name")
            if not var_name or not str(var_name).strip():
                errors.append({"node_id": nid, "message": "Question step must specify a variable name to store the customer's answer."})
            expected_type = node.get("expected_type") or node.get("data", {}).get("expected_type", "text")
            if expected_type not in ["text", "number", "email", "choice"]:
                warnings.append({"node_id": nid, "message": f"Question expected type '{expected_type}' is unconventional. Expected text, number, email, or choice."})

        elif ntype == "save_data":
            var_name = node.get("variable_name") or node.get("data", {}).get("variable_name") or node.get("key") or node.get("data", {}).get("variable")
            if not var_name or not str(var_name).strip():
                errors.append({"node_id": nid, "message": "Save Data step must specify a variable name to store."})

        elif ntype == "media":
            source = node.get("source") or node.get("data", {}).get("source", "static")
            media_url = node.get("media_url") or node.get("data", {}).get("media_url")
            if source == "static" and not media_url:
                errors.append({"node_id": nid, "message": "Media document step must specify a valid document or image URL."})

        elif ntype == "lead_status":
            from leads.models import LeadStatus
            status = node.get("status") or node.get("data", {}).get("status")
            if status not in LeadStatus.values:
                errors.append({"node_id": nid, "message": "Lead Status step must select a CRM lead status."})

        elif ntype == "assign_telecaller":
            mode = node.get("mode") or node.get("data", {}).get("mode", "auto")
            tc_id = node.get("telecaller_id") or node.get("data", {}).get("telecaller_id")
            if mode == "specific":
                from accounts.models import User
                if not tc_id or not User.get_telecallers_queryset().filter(pk=tc_id, is_active=True).exists():
                    errors.append({"node_id": nid, "message": "Assign Telecaller step must select an active telecaller."})

        elif ntype == "buttons":
            options = node.get("options") or node.get("data", {}).get("options", [])
            if len(options) == 0:
                errors.append({"node_id": nid, "message": "Buttons step must have at least 1 option."})
            elif len(options) > 3:
                errors.append({"node_id": nid, "message": f"Buttons step has {len(options)} options. Meta WhatsApp Cloud API allows a maximum of 3 buttons. Use a List Menu for 4 to 10 choices."})

        elif ntype == "list":
            source = node.get("source") or node.get("data", {}).get("source", "custom")
            if source != "database":
                sections = node.get("sections") or node.get("data", {}).get("sections", [])
                total_rows = 0
                for s in sections:
                    for r in s.get("rows", []):
                        total_rows += 1
                        rtitle = str(r.get("title", "")).strip()
                        if len(rtitle) > 24:
                            errors.append({"node_id": nid, "message": f"List option '{rtitle}' has {len(rtitle)} characters. WhatsApp limits list options to 24 characters maximum."})
                if total_rows == 0:
                    errors.append({"node_id": nid, "message": "List Menu step must have at least 1 menu option."})
                elif total_rows > 10:
                    errors.append({"node_id": nid, "message": f"List Menu has {total_rows} options. WhatsApp limits list menus to 10 options maximum."})

    # Trigger validation
    if len(trigger_nodes) == 0:
        errors.append({"node_id": "root", "message": "Flow must have a Trigger step to start automatically."})
    elif len(trigger_nodes) > 1:
        errors.append({"node_id": trigger_nodes[1]["id"], "message": "Flow cannot have more than one starting Trigger step."})

    # End node validation
    if len(end_nodes) == 0:
        errors.append({"node_id": "root", "message": "Flow must contain at least one End step to complete conversations cleanly."})

    # Validate Connections
    incoming_counts = {nid: 0 for nid in node_map}
    outgoing_counts = {nid: 0 for nid in node_map}
    outgoing_ports_by_node = {nid: set() for nid in node_map}

    # Normalize any provided connections (supports source/target or from/to or from_node/to_node)
    effective_connections = []
    if isinstance(connections, list) and len(connections) > 0:
        for c in connections:
            if isinstance(c, dict):
                effective_connections.append({
                    "id": c.get("id"),
                    "source": c.get("source") or c.get("from") or c.get("from_node"),
                    "target": c.get("target") or c.get("to") or c.get("to_node"),
                    "source_output": c.get("source_output") or c.get("output") or c.get("sourceHandle") or c.get("source_handle") or "default",
                    "target_input": c.get("target_input") or c.get("input") or "input",
                })

    # Backward compatibility: if connections array is empty, check next_node_id
    if len(effective_connections) == 0:
        for nid, node in node_map.items():
            if node.get("next_node_id"):
                effective_connections.append({
                    "id": f"conn_{nid}_default",
                    "source": nid,
                    "source_output": "default",
                    "target": node["next_node_id"],
                    "target_input": "input"
                })
            if node.get("type") == "buttons" and isinstance(node.get("options"), list):
                for opt in node.get("options"):
                    if opt.get("next_node_id"):
                        effective_connections.append({
                            "id": f"conn_{nid}_{opt.get('id', 'opt')}",
                            "source": nid,
                            "source_output": opt.get("id", "opt"),
                            "target": opt["next_node_id"],
                            "target_input": "input"
                        })

    seen_edge_ids = set()
    for conn in effective_connections:
        if not isinstance(conn, dict):
            errors.append({"node_id": "connections", "message": "Connection definition is malformed."})
            continue

        cid = conn.get("id")
        if cid:
            if cid in seen_edge_ids:
                warnings.append({"node_id": "connections", "message": f"Duplicate connection ID '{cid}'."})
            seen_edge_ids.add(cid)

        src = conn.get("source") or conn.get("from") or conn.get("from_node")
        target = conn.get("target") or conn.get("to") or conn.get("to_node")
        out_port = conn.get("source_output") or conn.get("output") or conn.get("source_handle") or "default"

        # Source exists
        if not src or src not in node_map:
            errors.append({"node_id": str(src or 'unknown'), "message": f"Connection source '{src}' does not exist in graph."})
            continue

        # Target exists
        if not target or target not in node_map:
            errors.append({"node_id": str(src), "message": f"Connection target '{target}' does not exist in graph."})
            continue

        outgoing_counts[src] += 1
        incoming_counts[target] += 1
        outgoing_ports_by_node[src].add(out_port)

    # Trigger outgoing connection check
    for trig in trigger_nodes:
        tid = trig["id"]
        if outgoing_counts.get(tid, 0) == 0:
            errors.append({"node_id": tid, "message": "Trigger step must connect to the first step of the workflow."})

    # Condition outputs check (Must have YES and NO branches)
    for nid, node in node_map.items():
        if node.get("type") == "condition":
            ports = outgoing_ports_by_node.get(nid, set())
            has_yes = any(p.upper() == "YES" or p == "true" for p in ports)
            has_no = any(p.upper() == "NO" or p == "false" for p in ports)
            if not has_yes:
                errors.append({"node_id": nid, "message": f"Condition step '{node.get('title', nid)}' has no connected 'YES' branch."})
            if not has_no:
                errors.append({"node_id": nid, "message": f"Condition step '{node.get('title', nid)}' has no connected 'NO' branch."})

        # Button outputs check
        elif node.get("type") == "buttons":
            options = node.get("options") or node.get("data", {}).get("options", [])
            if isinstance(options, list):
                ports = outgoing_ports_by_node.get(nid, set())
                for opt in options:
                    opt_id = opt.get("id")
                    if opt_id and opt_id not in ports and "default" not in ports and not opt.get("next_node_id"):
                        errors.append({"node_id": nid, "message": f"Button option '{opt.get('title', opt_id)}' is not connected to any next step."})

        # Orphan nodes check (excluding trigger and end)
        ntype = node.get("type")
        if ntype not in ["trigger", "start"] and incoming_counts.get(nid, 0) == 0:
            errors.append({"node_id": nid, "message": f"Orphan step '{node.get('title', nid)}' has no incoming connection."})

    # Reachability check: verify from Trigger to at least one End node
    if len(trigger_nodes) > 0 and len(end_nodes) > 0:
        visited = set()
        queue = [trigger_nodes[0]["id"]]
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            for conn in effective_connections:
                if conn.get("source") == curr:
                    tgt = conn.get("target")
                    if tgt and tgt not in visited:
                        queue.append(tgt)

        end_reachable = any(end_node["id"] in visited for end_node in end_nodes)
        if not end_reachable:
            errors.append({"node_id": "root", "message": "No End step is reachable from the starting Trigger."})

    # Cycle detection without waiting nodes (infinite instant loops)
    WAITING_NODE_TYPES = {"question", "buttons", "list", "human_handover", "end"}
    adj = {nid: [] for nid in node_map}
    for conn in effective_connections:
        s, t = conn.get("source"), conn.get("target")
        if s in adj and t:
            adj[s].append(t)

    def find_instant_cycle(start_nid, current_nid, visited_path):
        if current_nid in visited_path:
            # Cycle found: check if ANY node in visited_path waits for user
            has_wait = any(node_map.get(n, {}).get("type") in WAITING_NODE_TYPES for n in visited_path)
            if not has_wait:
                return True
            return False

        if current_nid not in node_map:
            return False

        visited_path.append(current_nid)
        for neighbor in adj.get(current_nid, []):
            if find_instant_cycle(start_nid, neighbor, list(visited_path)):
                return True
        return False

    for nid in node_map:
        if node_map[nid].get("type") not in WAITING_NODE_TYPES:
            if find_instant_cycle(nid, nid, []):
                errors.append({"node_id": nid, "message": f"Infinite instant loop detected starting at '{node_map[nid].get('title', nid)}'. Workflow would run indefinitely without user input."})
                break

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings)
    }
