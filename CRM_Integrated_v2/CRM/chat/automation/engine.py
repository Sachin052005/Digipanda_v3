"""
WhatsApp Automation Engine Execution Kernel (Graph-Based).
Handles state machine evaluation, session priority, idempotency, variable interpolation,
interactive buttons/lists dispatch, condition branching, dynamic course/branch lookups,
and human handover.
"""

import re
import logging
from typing import Optional, Dict, Any, List
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from chat.models import (
    BusinessAccount,
    Conversation,
    Message,
    AutomationFlow,
    UserFlowSession,
    Course,
    Branch,
    AutomationExecution
)
from chat.serializers import MessageSerializer
from chat.whatsapp.messages import (
    send_text_message,
    send_interactive_buttons,
    send_interactive_list,
    send_media_message,
    send_location_message
)
from chat.automation.templates import get_default_admissions_flow_data

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """
    Normalizes incoming user text by stripping punctuation, emojis, and extra whitespace.
    e.g. 'Hi!!!' -> 'hi', '  HELLO  ' -> 'hello'
    """
    if not text:
        return ''
    cleaned = re.sub(r'[^\w\s]', '', text.lower()).strip()
    return ' '.join(cleaned.split())


class AutomationEngine:
    """
    Executes automated WhatsApp flows against incoming messages with strict session priority.
    """

    @classmethod
    def get_or_create_default_flow(cls, business_account: Optional[BusinessAccount] = None) -> AutomationFlow:
        """
        Retrieves active published flow or seeds the default graph flow.
        """
        query = AutomationFlow.objects.filter(is_active=True, status=AutomationFlow.STATUS_PUBLISHED)
        if business_account:
            flow = query.filter(business_account=business_account).first()
            if flow:
                return flow

        flow = query.filter(business_account__isnull=True).first()
        if not flow:
            flow = AutomationFlow.objects.create(
                business_account=business_account,
                name="Admissions & Training Flow",
                slug="admissions-training-flow",
                version=1,
                status=AutomationFlow.STATUS_PUBLISHED,
                trigger_type=AutomationFlow.TRIGGER_FIRST_MESSAGE,
                trigger_keywords="hi, hello, hey, start, menu, info, admission, course, training",
                flow_data=get_default_admissions_flow_data(),
                is_active=True,
                published_at=timezone.now()
            )
        return flow

    @classmethod
    def log_execution(cls, session: Optional[UserFlowSession], flow: Optional[AutomationFlow], node_id: str, event_type: str, input_data: dict = None, output_data: dict = None, error: str = ""):
        """Creates an AutomationExecution audit log."""
        try:
            flow_version = session.flow_version if session else (flow.version if flow else 1)
            AutomationExecution.objects.create(
                session=session,
                flow=flow or (session.flow if session else None),
                flow_version=flow_version,
                node_id=node_id or "",
                event_type=event_type,
                input_data=input_data or {},
                output_data=output_data or {},
                error=error or ""
            )
        except Exception as exc:
            logger.warning(f"Failed to write AutomationExecution log: {exc}")

    @classmethod
    def process_incoming(cls, conversation: Conversation, incoming_text: str, incoming_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Main entry point for incoming WhatsApp customer messages.
        STRICT SESSION STATE PRIORITY:
        1. If session exists and ACTIVE -> continue current node.
        2. If session exists and HANDED_OVER -> DO NOTHING (silent).
        3. If session exists and COMPLETED -> DO NOTHING (silent forever; no restart).
        4. If session exists and EXPIRED -> DO NOTHING.
        5. ONLY if NO SESSION exists -> evaluate trigger to start flow.
        """
        biz = conversation.business_account
        if biz and not biz.automation_enabled:
            logger.info(f"Automation is disabled on Business Account '{biz.name}'. Skipping bot.")
            return False

        # STEP 2: Find the customer's existing automation session
        session = UserFlowSession.objects.filter(conversation=conversation).order_by('-started_at').first()

        if session:
            # ACTIVE session -> Continue current node
            if session.status == UserFlowSession.STATUS_ACTIVE:
                return cls.continue_current_node(conversation, session, incoming_text, incoming_data)

            # HANDED_OVER -> Bot remains silent
            elif session.status == UserFlowSession.STATUS_HANDED_OVER:
                logger.info(f"Conversation {conversation.id} is handed over to human. Bot remains silent.")
                return False

            # COMPLETED -> Bot remains silent forever
            elif session.status == UserFlowSession.STATUS_COMPLETED:
                logger.info(f"Session for conversation {conversation.id} is completed. Bot remains silent.")
                return False

            # EXPIRED -> Bot remains silent
            elif session.status == UserFlowSession.STATUS_EXPIRED:
                logger.info(f"Session for conversation {conversation.id} has expired. Bot remains silent.")
                return False

        # STEP 5: Only when NO SESSION exists -> Find latest published flow & evaluate trigger
        flow = cls.get_or_create_default_flow(biz)
        if not flow or not flow.is_active or flow.status != AutomationFlow.STATUS_PUBLISHED:
            return False

        trigger_matched = False
        norm = normalize_text(incoming_text)

        if flow.trigger_type in [AutomationFlow.TRIGGER_FIRST_MESSAGE, AutomationFlow.TRIGGER_ALWAYS_ON]:
            trigger_matched = True
        elif flow.trigger_type == AutomationFlow.TRIGGER_KEYWORD:
            keywords = [normalize_text(k) for k in flow.trigger_keywords.split(',') if k.strip()]
            for kw in keywords:
                if kw in norm or norm in kw:
                    trigger_matched = True
                    break
        elif flow.trigger_type == AutomationFlow.TRIGGER_BUTTON and incoming_data and incoming_data.get('type') == 'button_reply':
            trigger_matched = True
        elif flow.trigger_type == AutomationFlow.TRIGGER_LIST and incoming_data and incoming_data.get('type') == 'list_reply':
            trigger_matched = True

        if not trigger_matched:
            return False

        # Create fresh session locked to this flow and version
        trigger_node_id = cls.get_trigger_node_id(flow.flow_data)
        session = UserFlowSession.objects.create(
            conversation=conversation,
            flow=flow,
            flow_version=flow.version,
            current_node_id=trigger_node_id,
            status=UserFlowSession.STATUS_ACTIVE,
            collected_data={}
        )

        cls.log_execution(
            session=session,
            flow=flow,
            node_id=trigger_node_id,
            event_type="TRIGGER_STARTED",
            input_data={"incoming_text": incoming_text, "trigger_type": flow.trigger_type}
        )

        # Advance from trigger to first connected step
        target_id = cls.get_target_node_id(flow.flow_data, trigger_node_id, "default")
        if target_id:
            return cls.execute_node(conversation, session, target_id)
        return True

    @classmethod
    def get_trigger_node_id(cls, flow_data: dict) -> str:
        """Finds trigger or start node ID."""
        for n in flow_data.get('nodes', []):
            if n.get('type') in ['trigger', 'start']:
                return n.get('id', 'trigger_1')
        return 'trigger_1'

    @classmethod
    def continue_current_node(cls, conversation: Conversation, session: UserFlowSession, incoming_text: str, incoming_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Continues execution of an ACTIVE session upon receiving customer input.
        NEVER restarts the flow or re-evaluates triggers.
        """
        flow_data = session.flow.flow_data or {}
        nodes = {n['id']: n for n in flow_data.get('nodes', [])}
        curr_node = nodes.get(session.current_node_id)

        if not curr_node:
            logger.warning(f"Node '{session.current_node_id}' not found in flow v{session.flow_version}.")
            session.status = UserFlowSession.STATUS_COMPLETED
            session.completed_at = timezone.now()
            session.save(update_fields=['status', 'completed_at'])
            return False

        # Check for handover keywords inside flow settings
        settings = flow_data.get('settings', {})
        handover_keywords = [normalize_text(k) for k in settings.get('handover_keywords', ['agent', 'human', 'support'])]
        if normalize_text(incoming_text) in handover_keywords:
            session.status = UserFlowSession.STATUS_HANDED_OVER
            session.handed_over_at = timezone.now()
            session.save(update_fields=['status', 'handed_over_at', 'updated_at'])
            cls.send_bot_message(conversation, "👤 You have been connected to an admissions representative. Our counselor will assist you shortly.")
            cls.log_execution(session, session.flow, session.current_node_id, "HANDOVER", {"keyword": incoming_text})
            return True

        node_type = curr_node.get('type')
        data_block = curr_node.get('data', {})
        target_next_id = None

        # 1. QUESTION NODE
        if node_type == 'question':
            var_name = curr_node.get('variable_name') or data_block.get('variable_name', 'answer')
            expected_type = curr_node.get('expected_type') or data_block.get('expected_type', 'text')
            answer_val = incoming_text.strip()

            # Input format validation
            is_valid = True
            if expected_type == 'number':
                is_valid = bool(re.match(r'^\d+(\.\d+)?$', answer_val))
            elif expected_type == 'email':
                is_valid = bool(re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', answer_val))

            if not is_valid:
                retry_key = f"__retry_{session.current_node_id}"
                retries = int(session.collected_data.get(retry_key, 0)) + 1
                session.collected_data[retry_key] = retries
                max_retries = int(curr_node.get('retry_limit') or data_block.get('retry_limit', 3))

                if retries < max_retries:
                    session.save(update_fields=['collected_data', 'updated_at'])
                    default_err = f"Please provide a valid {expected_type} to continue." if expected_type != 'text' else "Invalid answer. Please try again:"
                    err_msg = curr_node.get('invalid_message') or data_block.get('invalid_message') or default_err
                    cls.send_bot_message(conversation, err_msg)
                    cls.log_execution(session, session.flow, session.current_node_id, "QUESTION_RETRY", {"expected_type": expected_type, "retries": retries})
                    return True
                else:
                    cls.log_execution(session, session.flow, session.current_node_id, "QUESTION_MAX_RETRIES", {"expected_type": expected_type})
                    target_next_id = cls.get_target_node_id(flow_data, session.current_node_id, "fallback") or cls.get_target_node_id(flow_data, session.current_node_id, "default")
            else:
                session.collected_data[var_name] = answer_val
                session.waiting_for_input = False
                session.save(update_fields=['collected_data', 'waiting_for_input', 'updated_at'])
                cls.log_execution(session, session.flow, session.current_node_id, "DATA_SAVED", {"variable": var_name, "value": answer_val})
                target_next_id = cls.get_target_node_id(flow_data, session.current_node_id, "default")

        # 2. BUTTONS NODE
        elif node_type == 'buttons':
            var_name = curr_node.get('variable_name') or data_block.get('variable_name', 'choice')
            options = curr_node.get('options') or data_block.get('options', [])
            matched_option = None

            button_reply_id = ""
            if incoming_data and incoming_data.get('type') == 'button_reply':
                button_reply_id = incoming_data.get('button_reply', {}).get('id', '')

            norm_input = normalize_text(incoming_text)

            for idx, opt in enumerate(options, start=1):
                opt_id = opt.get('id', '')
                opt_title = opt.get('title', '')
                if (
                    (button_reply_id and button_reply_id == opt_id) or
                    norm_input == normalize_text(opt_id) or
                    norm_input == normalize_text(opt_title) or
                    norm_input == str(idx) or
                    normalize_text(opt_title) in norm_input
                ):
                    matched_option = opt
                    break

            if matched_option:
                session.collected_data[var_name] = matched_option.get('title', incoming_text)
                session.waiting_for_input = False
                session.save(update_fields=['collected_data', 'waiting_for_input', 'updated_at'])

                cls.log_execution(session, session.flow, session.current_node_id, "BUTTON_SELECTED", {"option_id": matched_option.get('id')})

                # Follow matching option's output connection
                target_next_id = cls.get_target_node_id(flow_data, session.current_node_id, matched_option.get('id'))
                if not target_next_id:
                    target_next_id = cls.get_target_node_id(flow_data, session.current_node_id, "default")
            else:
                # Re-prompt politely without restarting
                cls.send_bot_message(conversation, "Please tap one of the provided options above to proceed:")
                return True

        # 3. LIST MENU NODE
        elif node_type == 'list':
            var_name = curr_node.get('variable_name') or data_block.get('variable_name', 'selection')
            is_dynamic_course = (curr_node.get('source') == 'database' or data_block.get('source') == 'database')

            if is_dynamic_course:
                courses = Course.objects.filter(is_active=True).order_by('display_order')[:10]
                matched_course = None
                norm_input = normalize_text(incoming_text)

                for idx, c in enumerate(courses, start=1):
                    cid_str = f"course_{c.id}"
                    c_name_norm = normalize_text(c.name or c.title)
                    if (
                        norm_input == cid_str.lower() or
                        norm_input == c_name_norm or
                        norm_input == str(idx) or
                        c_name_norm in norm_input
                    ):
                        matched_course = c
                        break

                if matched_course:
                    session.collected_data['course_id'] = matched_course.id
                    session.collected_data['course_name'] = matched_course.name or matched_course.title
                    session.collected_data[var_name] = matched_course.name or matched_course.title
                else:
                    session.collected_data[var_name] = incoming_text.strip()
            else:
                session.collected_data[var_name] = incoming_text.strip()

            session.waiting_for_input = False
            session.save(update_fields=['collected_data', 'waiting_for_input', 'updated_at'])
            cls.log_execution(session, session.flow, session.current_node_id, "LIST_SELECTED", {"selection": session.collected_data.get(var_name)})
            target_next_id = cls.get_target_node_id(flow_data, session.current_node_id, "default")

        else:
            # Fallback for linear progression
            target_next_id = cls.get_target_node_id(flow_data, session.current_node_id, "default")

        cls.sync_lead_answers(conversation, session)

        if target_next_id:
            return cls.execute_node(conversation, session, target_next_id, execution_depth=0)
        else:
            session.status = UserFlowSession.STATUS_COMPLETED
            session.completed_at = timezone.now()
            session.save(update_fields=['status', 'completed_at'])
            return False

    @classmethod
    def execute_node(cls, conversation: Conversation, session: UserFlowSession, node_id: str, execution_depth: int = 0) -> bool:
        """
        Executes a specific node and chains non-waiting follow-up steps.
        Includes execution depth guard to prevent infinite loops.
        """
        MAX_DEPTH = 25
        if execution_depth > MAX_DEPTH:
            logger.warning(f"Loop guard: Maximum execution depth ({MAX_DEPTH}) reached in session {session.id} at node '{node_id}'.")
            session.status = UserFlowSession.STATUS_COMPLETED
            session.completed_at = timezone.now()
            session.save(update_fields=['status', 'completed_at'])
            cls.log_execution(session, session.flow, node_id, "LOOP_GUARD_TRIGGERED", error=f"Max execution depth of {MAX_DEPTH} exceeded.")
            return False

        flow_data = session.flow.flow_data or {}
        nodes = {n['id']: n for n in flow_data.get('nodes', [])}
        node = nodes.get(node_id)

        if not node:
            logger.warning(f"Node {node_id} not found in flow {session.flow.id}")
            session.status = UserFlowSession.STATUS_COMPLETED
            session.completed_at = timezone.now()
            session.save(update_fields=['status', 'completed_at'])
            return False

        session.current_node_id = node_id
        session.save(update_fields=['current_node_id', 'updated_at'])

        node_type = node.get('type')
        data_block = node.get('data', {})
        cls.log_execution(session, session.flow, node_id, "NODE_EXECUTED", {"type": node_type, "depth": execution_depth})

        try:
            # 1. MESSAGE NODE
            if node_type == 'message':
                raw_text = node.get('body') or data_block.get('text', '')
                text = cls.interpolate(raw_text, session.collected_data)
                cls.send_bot_message(conversation, text)
                cls.log_execution(session, session.flow, node_id, "MESSAGE_SENT", {"text": text[:100]})
                next_id = cls.get_target_node_id(flow_data, node_id, "default")
                if next_id and next_id != node_id:
                    return cls.execute_node(conversation, session, next_id, execution_depth + 1)
                return True

            # 2. BUTTONS NODE
            elif node_type == 'buttons':
                raw_text = node.get('body') or data_block.get('text', 'Please choose:')
                body = cls.interpolate(raw_text, session.collected_data)
                header = node.get('header') or data_block.get('header')
                footer = node.get('footer') or data_block.get('footer')
                options = node.get('options') or data_block.get('options', [])

                cls.send_bot_buttons(conversation, body, options, header, footer)
                session.waiting_for_input = True
                session.save(update_fields=['waiting_for_input', 'updated_at'])
                return True

            # 3. LIST MENU NODE
            elif node_type == 'list':
                raw_text = node.get('body') or data_block.get('text', 'Select an option:')
                body = cls.interpolate(raw_text, session.collected_data)
                btn_text = node.get('button_text') or data_block.get('button_text', 'View Menu')
                header = node.get('header') or data_block.get('header')
                footer = node.get('footer') or data_block.get('footer')
                source = node.get('source') or data_block.get('source', '')

                if source == 'database':
                    courses = Course.objects.filter(is_active=True).order_by('display_order')[:10]
                    rows = []
                    for c in courses:
                        name_str = (c.name or c.title)[:24]
                        desc_str = (c.description or c.duration or "")[:72]
                        rows.append({"id": f"course_{c.id}", "title": name_str, "description": desc_str})
                    sections = [{"title": "Popular Programs", "rows": rows}]
                else:
                    sections = node.get('sections') or data_block.get('sections', [])

                cls.send_bot_list(conversation, body, btn_text, sections, header, footer)
                session.waiting_for_input = True
                session.save(update_fields=['waiting_for_input', 'updated_at'])
                return True

            # 4. QUESTION NODE
            elif node_type == 'question':
                raw_text = node.get('body') or data_block.get('text', 'Please reply with your details:')
                body = cls.interpolate(raw_text, session.collected_data)
                cls.send_bot_message(conversation, body)
                session.waiting_for_input = True
                session.save(update_fields=['waiting_for_input', 'updated_at'])
                cls.log_execution(session, session.flow, node_id, "QUESTION_WAITING", {"variable": node.get('variable_name') or data_block.get('variable_name')})
                return True

            # 5. CONDITION NODE
            elif node_type == 'condition':
                var_key = node.get('variable') or data_block.get('variable', '')
                operator = node.get('operator') or data_block.get('operator', 'equals')
                target_val = node.get('value') or data_block.get('value', '')

                eval_result = cls.evaluate_condition(session.collected_data.get(var_key), operator, target_val)
                branch_port = "YES" if eval_result else "NO"
                cls.log_execution(session, session.flow, node_id, "CONDITION_EVALUATED", {"variable": var_key, "result": eval_result, "branch": branch_port})

                next_id = cls.get_target_node_id(flow_data, node_id, branch_port)
                if next_id:
                    return cls.execute_node(conversation, session, next_id, execution_depth + 1)
                return True

            # 6. SAVE DATA NODE
            elif node_type == 'save_data':
                var_name = node.get('variable_name') or node.get('variable') or data_block.get('variable_name') or data_block.get('variable')
                raw_val = node.get('value') if 'value' in node else data_block.get('value', '')
                saved_val = cls.interpolate(str(raw_val or ''), session.collected_data)
                if var_name:
                    session.collected_data[var_name] = saved_val
                    session.save(update_fields=['collected_data', 'updated_at'])

                cls.log_execution(session, session.flow, node_id, "DATA_SAVED", {"variable": var_name, "value": saved_val})
                cls.sync_lead_answers(conversation, session)
                next_id = cls.get_target_node_id(flow_data, node_id, "default")
                if next_id:
                    return cls.execute_node(conversation, session, next_id, execution_depth + 1)
                return True

            # 7. SEND MEDIA NODE
            elif node_type == 'media':
                source = node.get('source') or data_block.get('source', 'static')
                caption = cls.interpolate(node.get('caption') or data_block.get('caption', ''), session.collected_data)
                media_url = ""
                filename = node.get('filename') or data_block.get('filename')

                if source == 'selected_course_brochure':
                    cid = session.collected_data.get('course_id')
                    course = Course.objects.filter(id=cid).first() if cid else None
                    if course:
                        media_url = course.get_brochure_url()
                        filename = filename or f"{course.name or course.title}_Brochure.pdf"
                    if not media_url:
                        media_url = data_block.get('fallback_url') or "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
                        filename = filename or "Course_Brochure.pdf"
                else:
                    media_url = node.get('media_url') or data_block.get('media_url', '')

                cls.send_bot_media(conversation, 'document', media_url, caption, filename)
                cls.log_execution(session, session.flow, node_id, "MEDIA_SENT", {"media_url": media_url})
                next_id = cls.get_target_node_id(flow_data, node_id, "default")
                if next_id and next_id != node_id:
                    return cls.execute_node(conversation, session, next_id, execution_depth + 1)
                return True

            # 8. SEND LOCATION NODE
            elif node_type == 'location':
                source = node.get('source') or data_block.get('source', 'static')
                if source == 'dynamic_branch':
                    branch = Branch.objects.filter(is_active=True).first()
                    if branch:
                        name = branch.name
                        address = branch.address
                        lat = float(branch.latitude)
                        lng = float(branch.longitude)
                    else:
                        name = data_block.get('fallback_name', 'Tech Academy Headquarters')
                        address = data_block.get('fallback_address', 'Anna Salai, Chennai')
                        lat = float(data_block.get('fallback_latitude', 13.0827))
                        lng = float(data_block.get('fallback_longitude', 80.2707))
                else:
                    name = node.get('name') or data_block.get('name', 'Branch Location')
                    address = node.get('address') or data_block.get('address', '')
                    lat = float(node.get('latitude') or data_block.get('latitude', 13.0827))
                    lng = float(node.get('longitude') or data_block.get('longitude', 80.2707))

                cls.send_bot_location(conversation, lat, lng, name, address)
                cls.log_execution(session, session.flow, node_id, "LOCATION_SENT", {"lat": lat, "lng": lng, "name": name})
                next_id = cls.get_target_node_id(flow_data, node_id, "default")
                if next_id and next_id != node_id:
                    return cls.execute_node(conversation, session, next_id, execution_depth + 1)
                return True

            # 9. HUMAN HANDOVER NODE
            elif node_type == 'human_handover':
                raw_text = node.get('body') or data_block.get('text', 'Handing over to admissions representative.')
                body = cls.interpolate(raw_text, session.collected_data)
                if body:
                    cls.send_bot_message(conversation, body)
                session.status = UserFlowSession.STATUS_HANDED_OVER
                session.handed_over_at = timezone.now()
                session.save(update_fields=['status', 'handed_over_at', 'updated_at'])
                cls.log_execution(session, session.flow, node_id, "HANDOVER")
                return True

            # 10a. CRM: CHANGE LEAD STATUS (nothing is sent to the student)
            elif node_type == 'lead_status':
                from chat import crm
                status = node.get('status') or data_block.get('status', '')
                hours = node.get('follow_up_hours') or data_block.get('follow_up_hours')
                try:
                    lead = cls.get_lead(conversation)
                    if lead is None:
                        raise ValueError("No CRM lead for this chat")
                    changed = crm.set_lead_status(lead, status, follow_up_hours=hours)
                    cls.log_execution(session, session.flow, node_id, "LEAD_STATUS_CHANGED",
                                      {"lead_id": lead.id, "status": status, "changed": changed})
                except Exception as crm_exc:
                    # A CRM problem must never leave the student stuck: log it and carry on.
                    logger.error(f"Lead status step failed: {crm_exc}", exc_info=True)
                    cls.log_execution(session, session.flow, node_id, "CRM_STEP_FAILED", error=str(crm_exc))
                next_id = cls.get_target_node_id(flow_data, node_id, "default")
                if next_id and next_id != node_id:
                    return cls.execute_node(conversation, session, next_id, execution_depth + 1)
                return True

            # 10b. CRM: ASSIGN TO TELECALLER (nothing is sent to the student)
            elif node_type == 'assign_telecaller':
                from chat import crm
                mode = node.get('mode') or data_block.get('mode', 'auto')
                tc_id = node.get('telecaller_id') or data_block.get('telecaller_id')
                only_unassigned = bool(node.get('only_if_unassigned', data_block.get('only_if_unassigned', False)))
                try:
                    lead = cls.get_lead(conversation)
                    if lead is None:
                        raise ValueError("No CRM lead for this chat")
                    assigned = crm.assign_lead(lead, mode=mode, telecaller_id=tc_id, only_if_unassigned=only_unassigned)
                    cls.log_execution(session, session.flow, node_id, "LEAD_ASSIGNED",
                                      {"lead_id": lead.id, "mode": mode,
                                       "telecaller": (assigned.get_full_name() or assigned.username) if assigned else None})
                except Exception as crm_exc:
                    logger.error(f"Assign telecaller step failed: {crm_exc}", exc_info=True)
                    cls.log_execution(session, session.flow, node_id, "CRM_STEP_FAILED", error=str(crm_exc))
                next_id = cls.get_target_node_id(flow_data, node_id, "default")
                if next_id and next_id != node_id:
                    return cls.execute_node(conversation, session, next_id, execution_depth + 1)
                return True

            # 10. DELAY NODE (Non-blocking)
            elif node_type == 'delay':
                next_id = cls.get_target_node_id(flow_data, node_id, "default")
                if next_id and next_id != node_id:
                    return cls.execute_node(conversation, session, next_id, execution_depth + 1)
                return True

            # 11. END NODE
            elif node_type == 'end':
                raw_text = node.get('body') or data_block.get('text', 'Session completed. Thank you!')
                body = cls.interpolate(raw_text, session.collected_data)
                if body:
                    cls.send_bot_message(conversation, body)
                session.status = UserFlowSession.STATUS_COMPLETED
                session.completed_at = timezone.now()
                session.save(update_fields=['status', 'completed_at', 'updated_at'])
                cls.log_execution(session, session.flow, node_id, "FLOW_COMPLETED")
                return True

        except Exception as exc:
            logger.error(f"Error executing node {node_id} in session {session.id}: {exc}", exc_info=True)
            cls.log_execution(session, session.flow, node_id, "ERROR", error=str(exc))
            return False

        return True

    # -------------------------------------------------------------------------
    # CRM lead helpers
    # -------------------------------------------------------------------------

    @classmethod
    def get_lead(cls, conversation: Conversation):
        """The CRM lead for this chat (created if the webhook hasn't made one yet)."""
        from chat import crm
        lead = crm.lead_for_conversation(conversation)
        if lead is None:
            lead, _ = crm.ensure_lead_for_conversation(conversation)
        return lead

    @classmethod
    def sync_lead_answers(cls, conversation: Conversation, session: UserFlowSession):
        """Copy collected flow answers onto the CRM lead. Never breaks the bot."""
        try:
            from chat import crm
            lead = cls.get_lead(conversation)
            changed = crm.sync_answers(lead, session.collected_data)
            if changed:
                session.save(update_fields=['collected_data', 'updated_at'])
                cls.log_execution(session, session.flow, session.current_node_id, "LEAD_UPDATED", {"fields": changed})
        except Exception as exc:
            logger.error(f"CRM answer sync failed for conversation {conversation.id}: {exc}", exc_info=True)

    @classmethod
    def evaluate_condition(cls, actual: Any, operator: str, target: Any) -> bool:
        """Evaluates condition operator."""
        act_str = str(actual or '').strip().lower()
        tgt_str = str(target or '').strip().lower()

        if operator == 'equals':
            return act_str == tgt_str
        elif operator == 'not_equals':
            return act_str != tgt_str
        elif operator == 'contains':
            return tgt_str in act_str
        elif operator == 'not_contains':
            return tgt_str not in act_str
        elif operator == 'exists':
            return bool(actual)
        elif operator == 'not_exists':
            return not bool(actual)
        return False

    @classmethod
    def get_target_node_id(cls, flow_data: dict, source_id: str, output_port: str = "default") -> Optional[str]:
        """Finds target node from connections or backward-compatible next_node_id."""
        connections = flow_data.get('connections', [])
        # 1. Match source and source_output port
        for conn in connections:
            if conn.get('source') == source_id:
                sport = conn.get('source_output', 'default')
                if sport == output_port or (output_port in ['YES', 'true'] and sport.upper() == 'YES') or (output_port in ['NO', 'false'] and sport.upper() == 'NO'):
                    return conn.get('target')

        # Fallback to default port if specific port had no target
        if output_port != "default":
            for conn in connections:
                if conn.get('source') == source_id and conn.get('source_output', 'default') == 'default':
                    return conn.get('target')

        # Backward compatibility: next_node_id on node
        nodes = {n['id']: n for n in flow_data.get('nodes', [])}
        node = nodes.get(source_id)
        if node:
            if node.get('type') == 'buttons' and isinstance(node.get('options'), list):
                for opt in node.get('options'):
                    if opt.get('id') == output_port and opt.get('next_node_id'):
                        return opt['next_node_id']
            if node.get('type') == 'condition':
                if output_port.upper() in ['YES', 'TRUE'] and node.get('yes_node_id'):
                    return node['yes_node_id']
                if output_port.upper() in ['NO', 'FALSE'] and node.get('no_node_id'):
                    return node['no_node_id']
            return node.get('next_node_id')

        return None

    @classmethod
    def interpolate(cls, template: str, data: Dict[str, Any]) -> str:
        """Replaces {{key}} with collected session variables."""
        if not template:
            return ''
        def replace(match):
            key = match.group(1).strip()
            return str(data.get(key, f"[{key}]"))
        return re.sub(r'\{\{\s*([a-zA-Z0-9_]+)\s*\}\}', replace, template)

    # -------------------------------------------------------------------------
    # Outbound Dispatch Helpers & Message Persistence
    # -------------------------------------------------------------------------

    @classmethod
    def _save_and_broadcast_bot_msg(cls, conversation: Conversation, message_text: str, message_type: str = Message.TYPE_TEXT, whatsapp_msg_id: str = '') -> Message:
        now = timezone.now()
        msg = Message.objects.create(
            conversation=conversation,
            sender=Message.SENDER_AGENT,
            message_type=message_type,
            message_text=message_text,
            whatsapp_message_id=whatsapp_msg_id,
            status=Message.STATUS_SENT,
            timestamp=now
        )
        conversation.last_message = message_text[:100] if message_text else f"[{message_type.title()}]"
        conversation.last_message_time = now
        conversation.save(update_fields=['last_message', 'last_message_time', 'updated_at'])

        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                serializer_data = MessageSerializer(msg).data
                async_to_sync(channel_layer.group_send)(
                    f"chat_{conversation.id}",
                    {"type": "chat_message", "message": serializer_data}
                )
                async_to_sync(channel_layer.group_send)(
                    "inbox_updates",
                    {
                        "type": "conversation_update",
                        "conversation": {
                            "id": conversation.id,
                            "business_account_id": conversation.business_account_id,
                            "customer_name": conversation.customer_name,
                            "phone_number": conversation.phone_number,
                            "last_message": conversation.last_message,
                            "last_message_time": msg.display_time,
                            "unread_count": conversation.unread_count,
                        }
                    }
                )
        except Exception as exc:
            logger.warning(f"WebSocket broadcast error in automation bot: {exc}")

        return msg

    @classmethod
    def send_bot_message(cls, conversation: Conversation, text: str):
        whatsapp_msg_id = ''
        try:
            res = send_text_message(
                to_phone_number=conversation.phone_number,
                text=text,
                business_account=conversation.business_account
            )
            messages = res.get('messages', [])
            if messages:
                whatsapp_msg_id = messages[0].get('id', '')
        except Exception as exc:
            logger.error(f"Failed to dispatch bot text to Meta: {exc}")
        cls._save_and_broadcast_bot_msg(conversation, text, Message.TYPE_TEXT, whatsapp_msg_id)

    @classmethod
    def send_bot_buttons(cls, conversation: Conversation, body: str, options: list, header: Optional[str] = None, footer: Optional[str] = None):
        whatsapp_msg_id = ''
        try:
            res = send_interactive_buttons(
                to_phone_number=conversation.phone_number,
                body_text=body,
                buttons=options,
                header_text=header,
                footer_text=footer,
                business_account=conversation.business_account
            )
            messages = res.get('messages', [])
            if messages:
                whatsapp_msg_id = messages[0].get('id', '')
        except Exception as exc:
            logger.error(f"Failed to dispatch bot buttons to Meta: {exc}")

        btn_str = "\n".join([f"🔘 {opt.get('title')}" for opt in options[:3]])
        full_text = f"{body}\n\n{btn_str}"
        cls._save_and_broadcast_bot_msg(conversation, full_text, Message.TYPE_TEXT, whatsapp_msg_id)

    @classmethod
    def send_bot_list(cls, conversation: Conversation, body: str, button_text: str, sections: list, header: Optional[str] = None, footer: Optional[str] = None):
        whatsapp_msg_id = ''
        try:
            res = send_interactive_list(
                to_phone_number=conversation.phone_number,
                body_text=body,
                button_text=button_text,
                sections=sections,
                header_text=header,
                footer_text=footer,
                business_account=conversation.business_account
            )
            messages = res.get('messages', [])
            if messages:
                whatsapp_msg_id = messages[0].get('id', '')
        except Exception as exc:
            logger.error(f"Failed to dispatch bot list to Meta: {exc}")

        preview = f"{body}\n[📋 {button_text}]"
        cls._save_and_broadcast_bot_msg(conversation, preview, Message.TYPE_TEXT, whatsapp_msg_id)

    @classmethod
    def send_bot_media(cls, conversation: Conversation, media_type: str, media_url: str, caption: str = '', filename: Optional[str] = None):
        whatsapp_msg_id = ''
        try:
            res = send_media_message(
                to_phone_number=conversation.phone_number,
                media_type=media_type,
                media_url_or_id=media_url,
                caption=caption,
                filename=filename,
                business_account=conversation.business_account
            )
            messages = res.get('messages', [])
            if messages:
                whatsapp_msg_id = messages[0].get('id', '')
        except Exception as exc:
            logger.error(f"Failed to dispatch bot media to Meta: {exc}")

        display_text = f"📄 {filename or 'Brochure'}\n{caption}".strip()
        cls._save_and_broadcast_bot_msg(conversation, display_text, Message.TYPE_DOCUMENT, whatsapp_msg_id)

    @classmethod
    def send_bot_location(cls, conversation: Conversation, lat: float, lng: float, name: str, address: str):
        whatsapp_msg_id = ''
        try:
            res = send_location_message(
                to_phone_number=conversation.phone_number,
                latitude=lat,
                longitude=lng,
                name=name,
                address=address,
                business_account=conversation.business_account
            )
            messages = res.get('messages', [])
            if messages:
                whatsapp_msg_id = messages[0].get('id', '')
        except Exception as exc:
            logger.error(f"Failed to dispatch bot location to Meta: {exc}")

        display_text = f"📍 *{name}*\n{address}"
        cls._save_and_broadcast_bot_msg(conversation, display_text, Message.TYPE_TEXT, whatsapp_msg_id)
