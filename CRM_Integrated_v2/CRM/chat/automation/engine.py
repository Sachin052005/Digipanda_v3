"""
WhatsApp Automation Engine Execution Kernel (Graph-Based).

DELIVERY UNCERTAINTY & EXACTLY-ONCE SEMANTICS:
- Internal CRM State: Guarantees exactly-once internal state transitions using database
  transactional locks (select_for_update) and atomic operations.
- External WhatsApp Delivery: WhatsApp Cloud API operates over cellular/internet networks.
  Once a message payload is dispatched to Meta's API, external delivery is inherently
  at-least-once. In the event of network partitions or Meta timeouts, message resends may
  result in duplicated delivery to the user's handset. The CRM records outgoing WhatsApp
  message IDs and status webhooks to deduplicate incoming delivery receipts.

Supports 15 canonical node types:
1. Trigger
2. Welcome Message / Text Message
3. Button Message (Interactive)
4. List Message (Interactive Menu)
5. Condition / If-Else Branching
6. Media Sender (Brochures / Documents / Images)
7. Location Sender (GPS coordinates / Branch addresses)
8. Wait / Delay (Durable database-backed scheduling)
9. Question / Capture Answer
10. Save Data / Update Lead
11. Assign Telecaller / Counselor
12. Human Handover
13. Webhook / Outbound API (SSRF Protected)
14. Go To / Subflow (Execution Stack)
15. End Flow
"""

from datetime import timedelta
import json
import logging
import re
from typing import Optional, Dict, Any, List, Union

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import connection, transaction, NotSupportedError
from django.utils import timezone

from chat.models import (
    BusinessAccount,
    Conversation,
    Message,
    AutomationFlow,
    AutomationFlowVersion,
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
from chat.automation.security import SafeWebhookClient, SSRFProtectionError, ResponseTooLargeError

logger = logging.getLogger('chat.automation.engine')


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
    Executes automated WhatsApp flows against incoming messages with strict session priority,
    durable delay scheduling, version-locked execution, and SSRF-hardened outbound webhooks.
    """

    @classmethod
    def get_flow_data(cls, session: UserFlowSession) -> dict:
        """
        Retrieves the exact flow graph data for a session.
        Priority:
        1. Immutable session.flow_version_ref
        2. flow.published_version
        3. flow.flow_data (backward compatibility)
        """
        if session.flow_version_ref and session.flow_version_ref.flow_data:
            return session.flow_version_ref.flow_data
        if session.flow and session.flow.published_version and session.flow.published_version.flow_data:
            return session.flow.published_version.flow_data
        if session.flow and session.flow.flow_data:
            return session.flow.flow_data
        return {}

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
            default_data = get_default_admissions_flow_data()
            flow = AutomationFlow.objects.create(
                business_account=business_account,
                name="Admissions & Training Flow",
                slug="admissions-training-flow",
                version=1,
                status=AutomationFlow.STATUS_PUBLISHED,
                trigger_type=AutomationFlow.TRIGGER_FIRST_MESSAGE,
                trigger_keywords="hi, hello, hey, start, menu, info, admission, course, training",
                flow_data=default_data,
                is_active=True,
                published_at=timezone.now()
            )
            # Create immutable version 1
            ver, _ = AutomationFlowVersion.objects.get_or_create(
                flow=flow,
                version_number=1,
                defaults={
                    'status': AutomationFlowVersion.STATUS_PUBLISHED,
                    'flow_data': default_data,
                    'change_summary': 'Initial default flow version',
                    'published_at': timezone.now()
                }
            )
            flow.published_version = ver
            flow.save(update_fields=['published_version'])
        elif not flow.published_version:
            ver, _ = AutomationFlowVersion.objects.get_or_create(
                flow=flow,
                version_number=flow.version or 1,
                defaults={
                    'status': AutomationFlowVersion.STATUS_PUBLISHED,
                    'flow_data': flow.flow_data or {},
                    'change_summary': 'Auto-synced version',
                    'published_at': flow.published_at or timezone.now()
                }
            )
            flow.published_version = ver
            flow.save(update_fields=['published_version'])

        return flow

    @classmethod
    def log_execution(
        cls,
        session: Optional[UserFlowSession],
        flow: Optional[AutomationFlow],
        node_id: str,
        event_type: str,
        input_data: dict = None,
        output_data: dict = None,
        error: str = ""
    ):
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
    def process_incoming(
        cls,
        conversation: Conversation,
        incoming_text: str,
        incoming_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Main entry point for incoming WhatsApp customer messages.
        Guarantees strict concurrency safety with database row locking.
        STRICT SESSION STATE PRIORITY:
        1. If session exists and ACTIVE -> continue current node.
        2. If session exists and PAUSED (delay timer) -> interrupt delay and resume.
        3. If session exists and HANDED_OVER -> DO NOTHING (silent; counselor handles).
        4. If session exists and COMPLETED -> allow re-triggering fresh session.
        5. If session exists and EXPIRED -> allow re-triggering fresh session.
        6. If NO SESSION exists -> evaluate triggers to start flow.
        """
        biz = conversation.business_account
        if biz and not biz.automation_enabled:
            logger.info(f"Automation is disabled on Business Account '{biz.name}'. Skipping bot.")
            return False

        # Atomic transaction with concurrency locking
        with transaction.atomic():
            try:
                conv_locked = Conversation.objects.select_for_update().get(id=conversation.id)
            except (NotSupportedError, Exception):
                conv_locked = conversation

            try:
                session = UserFlowSession.objects.select_for_update().filter(
                    conversation=conv_locked
                ).order_by('-started_at').first()
            except (NotSupportedError, Exception):
                session = UserFlowSession.objects.filter(
                    conversation=conv_locked
                ).order_by('-started_at').first()

            if session:
                # ACTIVE session -> Continue current node
                if session.status == UserFlowSession.STATUS_ACTIVE:
                    return cls.continue_current_node(conv_locked, session, incoming_text, incoming_data)

                # PAUSED session (Delay in progress) -> User reply interrupts delay
                elif session.status == UserFlowSession.STATUS_PAUSED:
                    logger.info(f"Session {session.id} delay interrupted by customer reply '{incoming_text}'. Resuming session.")
                    session.status = UserFlowSession.STATUS_ACTIVE
                    target_node = session.resume_node_id or session.paused_node_id
                    session.paused_node_id = ""
                    session.resume_node_id = ""
                    session.resume_at = None
                    session.save(update_fields=['status', 'paused_node_id', 'resume_node_id', 'resume_at', 'updated_at'])

                    cls.log_execution(
                        session=session,
                        flow=session.flow,
                        node_id=target_node or "delay",
                        event_type="DELAY_INTERRUPTED_BY_USER",
                        input_data={"incoming_text": incoming_text}
                    )
                    if target_node:
                        return cls.execute_node(conv_locked, session, target_node)
                    return True

                # HANDED_OVER -> Bot remains silent (human counselor is handling)
                elif session.status == UserFlowSession.STATUS_HANDED_OVER:
                    logger.info(f"Conversation {conv_locked.id} is handed over to human. Bot remains silent.")
                    return False

                # COMPLETED or EXPIRED -> User finished earlier flow; allow re-triggering fresh session
                elif session.status in [UserFlowSession.STATUS_COMPLETED, UserFlowSession.STATUS_EXPIRED]:
                    logger.info(f"Previous session for conversation {conv_locked.id} was {session.status}. Checking triggers.")

            # Find latest published flow & evaluate trigger
            flow = cls.get_or_create_default_flow(biz)
            if not flow or not flow.is_active or flow.status != AutomationFlow.STATUS_PUBLISHED:
                return False

            flow_version = flow.published_version

            trigger_matched = False
            norm = normalize_text(incoming_text)
            has_prior_session = bool(session and session.status in [UserFlowSession.STATUS_COMPLETED, UserFlowSession.STATUS_EXPIRED])
            standard_greetings = {'hi', 'hello', 'hey', 'start', 'restart', 'menu', 'main menu', 'join', 'course', 'courses'}

            if flow.trigger_type == AutomationFlow.TRIGGER_ALWAYS_ON:
                trigger_matched = True
            elif flow.trigger_type == AutomationFlow.TRIGGER_FIRST_MESSAGE:
                if not has_prior_session:
                    trigger_matched = True
                elif norm in standard_greetings:
                    trigger_matched = True
                elif flow.trigger_keywords:
                    keywords = [normalize_text(k) for k in flow.trigger_keywords.split(',') if k.strip()]
                    for kw in keywords:
                        if kw in norm or norm in kw:
                            trigger_matched = True
                            break
            elif flow.trigger_type == AutomationFlow.TRIGGER_KEYWORD:
                keywords = [normalize_text(k) for k in flow.trigger_keywords.split(',') if k.strip()]
                for kw in keywords:
                    if kw in norm or norm in kw:
                        trigger_matched = True
                        break
                if not trigger_matched and (norm in standard_greetings):
                    trigger_matched = True
            elif flow.trigger_type == AutomationFlow.TRIGGER_BUTTON and incoming_data and incoming_data.get('type') == 'button_reply':
                trigger_matched = True
            elif flow.trigger_type == AutomationFlow.TRIGGER_LIST and incoming_data and incoming_data.get('type') == 'list_reply':
                trigger_matched = True

            if not trigger_matched:
                return False

            # Create fresh session locked to this immutable flow version
            flow_data = flow_version.flow_data if flow_version else (flow.flow_data or {})
            trigger_node_id = cls.get_trigger_node_id(flow_data)

            new_session = UserFlowSession.objects.create(
                conversation=conv_locked,
                flow=flow,
                flow_version=flow_version.version_number if flow_version else flow.version,
                flow_version_ref=flow_version,
                current_node_id=trigger_node_id,
                status=UserFlowSession.STATUS_ACTIVE,
                collected_data={},
                execution_stack=[]
            )

            cls.log_execution(
                session=new_session,
                flow=flow,
                node_id=trigger_node_id,
                event_type="TRIGGER_STARTED",
                input_data={"incoming_text": incoming_text, "trigger_type": flow.trigger_type}
            )

            target_id = cls.get_target_node_id(flow_data, trigger_node_id, "default")
            if target_id:
                return cls.execute_node(conv_locked, new_session, target_id)
            return True

    @classmethod
    def get_trigger_node_id(cls, flow_data: dict) -> str:
        """Finds trigger or start node ID."""
        for n in flow_data.get('nodes', []):
            if n.get('type') in ['trigger', 'start']:
                return n.get('id', 'trigger_1')
        return 'trigger_1'

    @classmethod
    def continue_current_node(
        cls,
        conversation: Conversation,
        session: UserFlowSession,
        incoming_text: str,
        incoming_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Continues execution of an ACTIVE session upon receiving customer input.
        NEVER restarts the flow or re-evaluates triggers.
        """
        flow_data = cls.get_flow_data(session)
        nodes = {n['id']: n for n in flow_data.get('nodes', [])}
        curr_node = nodes.get(session.current_node_id)

        if not curr_node:
            logger.warning(f"Active node {session.current_node_id} not found in session {session.id}. Marking completed.")
            session.status = UserFlowSession.STATUS_COMPLETED
            session.completed_at = timezone.now()
            session.save(update_fields=['status', 'completed_at', 'updated_at'])
            return False

        node_type = curr_node.get('type')
        data_block = curr_node.get('data', {})
        cls.log_execution(session, session.flow, session.current_node_id, "CUSTOMER_REPLY",
                          {"text": incoming_text, "data": incoming_data})

        # 1. QUESTION / CAPTURE ANSWER NODE
        if node_type in ['question', 'capture_answer']:
            var_name = curr_node.get('variable_name') or data_block.get('variable_name')
            if var_name:
                session.collected_data[var_name] = incoming_text.strip()
                session.save(update_fields=['collected_data', 'updated_at'])
                cls.log_execution(session, session.flow, session.current_node_id, "VARIABLE_CAPTURED",
                                  {"variable": var_name, "value": incoming_text.strip()})
                cls.sync_lead_answers(conversation, session)

            session.waiting_for_input = False
            session.save(update_fields=['waiting_for_input', 'updated_at'])
            next_id = cls.get_target_node_id(flow_data, session.current_node_id, "default")
            if next_id:
                return cls.execute_node(conversation, session, next_id)
            return True

        # 2. BUTTONS NODE
        elif node_type == 'buttons':
            selected_id = None
            if incoming_data and incoming_data.get('type') == 'button_reply':
                selected_id = incoming_data.get('id')
            else:
                norm_in = normalize_text(incoming_text)
                options = curr_node.get('options') or data_block.get('options', [])
                for opt in options:
                    if normalize_text(opt.get('title', '')) == norm_in or opt.get('id') == incoming_text.strip():
                        selected_id = opt.get('id')
                        break

            if not selected_id:
                raw_body = curr_node.get('body') or data_block.get('text', 'Please choose an option:')
                prompt_text = "Please tap one of the buttons below to proceed:\n\n" + cls.interpolate(raw_body, session.collected_data)
                cls.send_bot_message(conversation, prompt_text)
                return True

            var_name = curr_node.get('variable_name') or data_block.get('variable_name')
            if var_name:
                session.collected_data[var_name] = selected_id
                session.save(update_fields=['collected_data', 'updated_at'])
                cls.sync_lead_answers(conversation, session)

            session.waiting_for_input = False
            session.save(update_fields=['waiting_for_input', 'updated_at'])

            next_id = cls.get_target_node_id(flow_data, session.current_node_id, selected_id)
            if not next_id:
                next_id = cls.get_target_node_id(flow_data, session.current_node_id, "default")
            if next_id:
                return cls.execute_node(conversation, session, next_id)
            return True

        # 3. LIST MENU NODE
        elif node_type == 'list':
            selected_row_id = None
            if incoming_data and incoming_data.get('type') == 'list_reply':
                selected_row_id = incoming_data.get('id')
            else:
                norm_in = normalize_text(incoming_text)
                sections = curr_node.get('sections') or data_block.get('sections', [])
                for sec in sections:
                    for row in sec.get('rows', []):
                        if normalize_text(row.get('title', '')) == norm_in or row.get('id') == incoming_text.strip():
                            selected_row_id = row.get('id')
                            break
                    if selected_row_id:
                        break

            if not selected_row_id:
                raw_body = curr_node.get('body') or data_block.get('text', 'Please select from the menu:')
                prompt_text = "Please select an item from the list to continue:\n\n" + cls.interpolate(raw_body, session.collected_data)
                cls.send_bot_message(conversation, prompt_text)
                return True

            var_name = curr_node.get('variable_name') or data_block.get('variable_name')
            if var_name:
                session.collected_data[var_name] = selected_row_id
                session.save(update_fields=['collected_data', 'updated_at'])
                cls.sync_lead_answers(conversation, session)

            session.waiting_for_input = False
            session.save(update_fields=['waiting_for_input', 'updated_at'])

            next_id = cls.get_target_node_id(flow_data, session.current_node_id, selected_row_id)
            if not next_id:
                next_id = cls.get_target_node_id(flow_data, session.current_node_id, "default")
            if next_id:
                return cls.execute_node(conversation, session, next_id)
            return True

        return True

    @classmethod
    def execute_node(
        cls,
        conversation: Conversation,
        session: UserFlowSession,
        node_id: str,
        execution_depth: int = 0
    ) -> bool:
        """
        Executes a specific node and chains non-waiting follow-up steps.
        Includes loop protection guard and supports all 15 canonical node types.
        """
        MAX_DEPTH = 30
        if execution_depth > MAX_DEPTH:
            logger.warning(f"Loop guard: Maximum execution depth ({MAX_DEPTH}) reached in session {session.id} at node '{node_id}'.")
            session.status = UserFlowSession.STATUS_COMPLETED
            session.completed_at = timezone.now()
            session.save(update_fields=['status', 'completed_at', 'updated_at'])
            cls.log_execution(session, session.flow, node_id, "LOOP_GUARD_TRIGGERED", error=f"Max execution depth of {MAX_DEPTH} exceeded.")
            return False

        flow_data = cls.get_flow_data(session)
        nodes = {n['id']: n for n in flow_data.get('nodes', [])}
        node = nodes.get(node_id)

        if not node:
            logger.warning(f"Node {node_id} not found in flow {session.flow.id}")
            session.status = UserFlowSession.STATUS_COMPLETED
            session.completed_at = timezone.now()
            session.save(update_fields=['status', 'completed_at', 'updated_at'])
            return False

        session.current_node_id = node_id
        session.save(update_fields=['current_node_id', 'updated_at'])

        node_type = node.get('type')
        data_block = node.get('data', {})
        cls.log_execution(session, session.flow, node_id, "NODE_EXECUTED", {"type": node_type, "depth": execution_depth})

        try:
            # 1. TRIGGER / START NODE
            if node_type in ['trigger', 'start']:
                next_id = cls.get_target_node_id(flow_data, node_id, "default")
                if next_id and next_id != node_id:
                    return cls.execute_node(conversation, session, next_id, execution_depth + 1)
                return True

            # 2. MESSAGE / WELCOME NODE
            elif node_type in ['message', 'welcome']:
                raw_text = node.get('body') or data_block.get('text', '')
                text = cls.interpolate(raw_text, session.collected_data)
                cls.send_bot_message(conversation, text)
                cls.log_execution(session, session.flow, node_id, "MESSAGE_SENT", {"text": text[:100]})
                next_id = cls.get_target_node_id(flow_data, node_id, "default")
                if next_id and next_id != node_id:
                    return cls.execute_node(conversation, session, next_id, execution_depth + 1)
                return True

            # 3. BUTTONS NODE
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

            # 4. LIST MENU NODE
            elif node_type == 'list':
                raw_text = node.get('body') or data_block.get('text', 'Select an option:')
                body = cls.interpolate(raw_text, session.collected_data)
                btn_text = node.get('button_text') or data_block.get('button_text', 'View Menu')
                header = node.get('header') or data_block.get('header')
                footer = node.get('footer') or data_block.get('footer')
                source = node.get('source') or data_block.get('source', '')

                if source == 'database':
                    courses = list(Course.objects.filter(is_active=True).order_by('display_order')[:10])
                    if courses:
                        rows = []
                        for c in courses:
                            name_str = (c.name or c.title)[:24]
                            desc_str = (c.description or c.duration or "")[:72]
                            rows.append({"id": f"course_{c.id}", "title": name_str, "description": desc_str})
                        sections = [{"title": "Popular Programs", "rows": rows}]
                    else:
                        sections = node.get('sections') or data_block.get('sections', [])
                else:
                    sections = node.get('sections') or data_block.get('sections', [])

                cls.send_bot_list(conversation, body, btn_text, sections, header, footer)
                session.waiting_for_input = True
                session.save(update_fields=['waiting_for_input', 'updated_at'])
                return True

            # 5. QUESTION / CAPTURE ANSWER NODE
            elif node_type in ['question', 'capture_answer']:
                raw_text = node.get('body') or data_block.get('text', 'Please reply with your details:')
                body = cls.interpolate(raw_text, session.collected_data)
                cls.send_bot_message(conversation, body)
                session.waiting_for_input = True
                session.save(update_fields=['waiting_for_input', 'updated_at'])
                cls.log_execution(session, session.flow, node_id, "QUESTION_WAITING",
                                  {"variable": node.get('variable_name') or data_block.get('variable_name')})
                return True

            # 6. CONDITION / IF-ELSE NODE
            elif node_type == 'condition':
                var_key = node.get('variable') or data_block.get('variable', '')
                operator = node.get('operator') or data_block.get('operator', 'equals')
                target_val = node.get('value') or data_block.get('value', '')

                eval_result = cls.evaluate_condition(session.collected_data.get(var_key), operator, target_val)
                branch_port = "YES" if eval_result else "NO"
                cls.log_execution(session, session.flow, node_id, "CONDITION_EVALUATED",
                                  {"variable": var_key, "result": eval_result, "branch": branch_port})

                next_id = cls.get_target_node_id(flow_data, node_id, branch_port)
                if next_id:
                    return cls.execute_node(conversation, session, next_id, execution_depth + 1)
                return True

            # 7. SAVE DATA / UPDATE LEAD NODE
            elif node_type in ['save_data', 'update_lead']:
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

            # 8. SEND MEDIA NODE
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

            # 9. SEND LOCATION NODE
            elif node_type == 'location':
                source = node.get('source') or data_block.get('source', 'custom')
                lat = None
                lng = None
                name = node.get('name') or data_block.get('name')
                address = node.get('address') or data_block.get('address')

                custom_lat = node.get('latitude') if node.get('latitude') is not None else data_block.get('latitude')
                custom_lng = node.get('longitude') if node.get('longitude') is not None else data_block.get('longitude')

                if source == 'dynamic_branch':
                    branch = None
                    if hasattr(Branch, 'Status'):
                        branch = Branch.objects.filter(status=Branch.Status.ACTIVE).first()
                    elif hasattr(Branch, 'is_active'):
                        branch = Branch.objects.filter(is_active=True).first()
                    else:
                        branch = Branch.objects.first()

                    if branch:
                        name = name or branch.name
                        address = address or getattr(branch, 'address', '')
                        lat = getattr(branch, 'latitude', None)
                        lng = getattr(branch, 'longitude', None)

                try:
                    lat = float(custom_lat if custom_lat is not None else (lat or 13.0827))
                except (ValueError, TypeError):
                    lat = 13.0827

                try:
                    lng = float(custom_lng if custom_lng is not None else (lng or 80.2707))
                except (ValueError, TypeError):
                    lng = 80.2707

                name = name or 'DigiPanda Tech Academy'
                address = address or 'Anna Salai, Chennai, Tamil Nadu'

                cls.send_bot_location(conversation, lat, lng, name, address)
                cls.log_execution(session, session.flow, node_id, "LOCATION_SENT", {"lat": lat, "lng": lng, "name": name})
                next_id = cls.get_target_node_id(flow_data, node_id, "default")
                if next_id and next_id != node_id:
                    return cls.execute_node(conversation, session, next_id, execution_depth + 1)
                return True

            # 10. WAIT / DELAY NODE (DURABLE DATABASE SCHEDULING)
            elif node_type == 'delay':
                # Parse duration
                delay_sec = 0
                if 'delay_seconds' in data_block:
                    delay_sec = int(data_block['delay_seconds'])
                elif 'seconds' in data_block:
                    delay_sec = int(data_block['seconds'])
                elif 'amount' in data_block:
                    amt = int(data_block.get('amount', 1))
                    unit = str(data_block.get('unit', 'minutes')).lower()
                    if unit.startswith('sec'):
                        delay_sec = amt
                    elif unit.startswith('min'):
                        delay_sec = amt * 60
                    elif unit.startswith('hour'):
                        delay_sec = amt * 3600
                    elif unit.startswith('day'):
                        delay_sec = amt * 86400
                else:
                    delay_sec = int(node.get('delay_seconds') or 60)

                next_id = cls.get_target_node_id(flow_data, node_id, "default")
                if not next_id:
                    logger.info(f"Delay node {node_id} has no target node. Completing session.")
                    session.status = UserFlowSession.STATUS_COMPLETED
                    session.completed_at = timezone.now()
                    session.save(update_fields=['status', 'completed_at', 'updated_at'])
                    return True

                session.status = UserFlowSession.STATUS_PAUSED
                session.paused_node_id = node_id
                session.resume_node_id = next_id
                session.resume_at = timezone.now() + timedelta(seconds=max(1, delay_sec))
                session.save(update_fields=['status', 'paused_node_id', 'resume_node_id', 'resume_at', 'updated_at'])

                cls.log_execution(
                    session=session,
                    flow=session.flow,
                    node_id=node_id,
                    event_type="DELAY_SCHEDULED",
                    output_data={
                        "resume_at": session.resume_at.isoformat(),
                        "resume_node_id": next_id,
                        "delay_seconds": delay_sec
                    }
                )
                # Pause cleanly without immediate downstream execution
                return True

            # 11. OUTBOUND WEBHOOK / API NODE (SSRF PROTECTED)
            elif node_type in ['webhook', 'api_request']:
                target_url = cls.interpolate(node.get('url') or data_block.get('url', ''), session.collected_data)
                method = (node.get('method') or data_block.get('method', 'POST')).upper()
                headers = data_block.get('headers') or node.get('headers') or {}
                if isinstance(headers, str):
                    try:
                        headers = json.loads(cls.interpolate(headers, session.collected_data))
                    except Exception:
                        headers = {}

                payload_data = None
                raw_payload = data_block.get('body') or data_block.get('payload') or node.get('body')
                if raw_payload:
                    if isinstance(raw_payload, dict):
                        payload_data = raw_payload
                    elif isinstance(raw_payload, str):
                        try:
                            payload_data = json.loads(cls.interpolate(raw_payload, session.collected_data))
                        except Exception:
                            payload_data = {"text": cls.interpolate(raw_payload, session.collected_data)}

                save_var = data_block.get('save_response_to') or node.get('save_response_to')

                client = SafeWebhookClient()
                try:
                    resp = client.request(
                        method=method,
                        url=target_url,
                        headers=headers,
                        json_data=payload_data if method in ('POST', 'PUT', 'PATCH') else None
                    )
                    cls.log_execution(session, session.flow, node_id, "WEBHOOK_SUCCESS",
                                      output_data={"status_code": resp['status_code'], "url": target_url})

                    if save_var:
                        session.collected_data[save_var] = resp.get('json') or resp.get('text')
                        session.save(update_fields=['collected_data', 'updated_at'])

                    next_id = cls.get_target_node_id(flow_data, node_id, "default")
                except (SSRFProtectionError, ResponseTooLargeError) as sec_err:
                    logger.error(f"Webhook security block at node {node_id}: {sec_err}")
                    cls.log_execution(session, session.flow, node_id, "WEBHOOK_SECURITY_BLOCKED", error=str(sec_err))
                    next_id = cls.get_target_node_id(flow_data, node_id, "error") or cls.get_target_node_id(flow_data, node_id, "default")
                except Exception as req_err:
                    logger.error(f"Webhook request failed at node {node_id}: {req_err}")
                    cls.log_execution(session, session.flow, node_id, "WEBHOOK_FAILED", error=str(req_err))
                    next_id = cls.get_target_node_id(flow_data, node_id, "error") or cls.get_target_node_id(flow_data, node_id, "default")

                if next_id and next_id != node_id:
                    return cls.execute_node(conversation, session, next_id, execution_depth + 1)
                return True

            # 12. GO TO / SUBFLOW NODE
            elif node_type in ['subflow', 'goto']:
                target_flow_id = data_block.get('flow_id') or node.get('flow_id')
                target_node = data_block.get('target_node_id') or node.get('target_node_id')

                if node_type == 'goto' and target_node:
                    cls.log_execution(session, session.flow, node_id, "GOTO_JUMP", {"target_node_id": target_node})
                    return cls.execute_node(conversation, session, target_node, execution_depth + 1)

                elif node_type == 'subflow' and target_flow_id:
                    subflow = AutomationFlow.objects.filter(id=target_flow_id, is_active=True).first()
                    if subflow and subflow.published_version:
                        next_after_subflow = cls.get_target_node_id(flow_data, node_id, "default")
                        stack = list(session.execution_stack or [])
                        stack.append({
                            'flow_id': session.flow_id,
                            'flow_version_id': session.flow_version_ref_id,
                            'resume_node_id': next_after_subflow
                        })
                        session.execution_stack = stack
                        session.flow = subflow
                        session.flow_version_ref = subflow.published_version
                        session.save(update_fields=['execution_stack', 'flow', 'flow_version_ref', 'updated_at'])

                        sub_data = subflow.published_version.flow_data or {}
                        sub_trigger = cls.get_trigger_node_id(sub_data)
                        sub_first = cls.get_target_node_id(sub_data, sub_trigger, "default") or sub_trigger
                        cls.log_execution(session, subflow, node_id, "SUBFLOW_INVOKED", {"subflow_id": subflow.id})
                        return cls.execute_node(conversation, session, sub_first, execution_depth + 1)

                next_id = cls.get_target_node_id(flow_data, node_id, "default")
                if next_id and next_id != node_id:
                    return cls.execute_node(conversation, session, next_id, execution_depth + 1)
                return True

            # 13. HUMAN HANDOVER NODE
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

            # 14a. CRM: CHANGE LEAD STATUS
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
                    logger.error(f"Lead status step failed: {crm_exc}", exc_info=True)
                    cls.log_execution(session, session.flow, node_id, "CRM_STEP_FAILED", error=str(crm_exc))

                next_id = cls.get_target_node_id(flow_data, node_id, "default")
                if next_id and next_id != node_id:
                    return cls.execute_node(conversation, session, next_id, execution_depth + 1)
                return True

            # 14b. CRM: ASSIGN TO TELECALLER / COUNSELOR
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

            # 15. END NODE
            elif node_type == 'end':
                raw_text = node.get('body') or data_block.get('text', 'Session completed. Thank you!')
                body = cls.interpolate(raw_text, session.collected_data)
                if body:
                    cls.send_bot_message(conversation, body)

                # Check if this was a subflow return
                if session.execution_stack:
                    stack = list(session.execution_stack)
                    caller_frame = stack.pop()
                    session.execution_stack = stack
                    parent_flow = AutomationFlow.objects.filter(id=caller_frame['flow_id']).first()
                    parent_ver = AutomationFlowVersion.objects.filter(id=caller_frame.get('flow_version_id')).first()
                    if parent_flow:
                        session.flow = parent_flow
                        session.flow_version_ref = parent_ver or parent_flow.published_version
                    session.save(update_fields=['execution_stack', 'flow', 'flow_version_ref', 'updated_at'])

                    resume_target = caller_frame.get('resume_node_id')
                    if resume_target:
                        cls.log_execution(session, parent_flow, node_id, "SUBFLOW_RETURNED", {"resume_node_id": resume_target})
                        return cls.execute_node(conversation, session, resume_target, execution_depth + 1)

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
        """
        Finds target node from connections, React Flow edges, or backward-compatible node definitions.
        Checks both 'connections' and 'edges' arrays.
        Matches 'source_output', 'sourceHandle', or handles.
        """
        links = flow_data.get('connections') or flow_data.get('edges') or []
        for link in links:
            if link.get('source') == source_id:
                sport = link.get('source_output') or link.get('sourceHandle') or 'default'
                if sport == output_port:
                    return link.get('target')
                if output_port.upper() in ['YES', 'TRUE'] and str(sport).upper() in ['YES', 'TRUE']:
                    return link.get('target')
                if output_port.upper() in ['NO', 'FALSE'] and str(sport).upper() in ['NO', 'FALSE']:
                    return link.get('target')

        # Fallback to default port if specific port had no target
        if output_port != "default":
            for link in links:
                if link.get('source') == source_id:
                    sport = link.get('source_output') or link.get('sourceHandle') or 'default'
                    if sport == 'default' or not sport:
                        return link.get('target')

        # Backward compatibility: explicit next_node_id on node
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
    def _save_and_broadcast_bot_msg(
        cls,
        conversation: Conversation,
        message_text: str,
        message_type: str = Message.TYPE_TEXT,
        whatsapp_msg_id: str = ''
    ) -> Message:
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

    # -------------------------------------------------------------------------
    # In-Memory Safe Simulator
    # -------------------------------------------------------------------------

    @classmethod
    def simulate_step(
        cls,
        flow_data: Dict[str, Any],
        current_node_id: Optional[str] = None,
        message_text: str = '',
        collected_data: Optional[Dict[str, Any]] = None,
        interactive_reply: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Pure in-memory step simulation of a flow graph.
        Never calls Meta Graph API, never sends real WhatsApp messages,
        never modifies CRM Lead objects.
        """
        if collected_data is None:
            collected_data = {}
        else:
            collected_data = dict(collected_data)

        nodes = flow_data.get('nodes', [])
        node_map = {n['id']: n for n in nodes if isinstance(n, dict) and 'id' in n}

        sim_messages = []
        crm_actions = []

        if not current_node_id:
            start_node = next((n for n in nodes if n.get('type') in ['trigger', 'start']), None)
            if not start_node and nodes:
                start_node = nodes[0]
            if not start_node:
                return {
                    'error': 'No trigger step found in workflow.',
                    'current_node_id': None,
                    'collected_data': collected_data,
                    'sim_messages': [],
                    'is_complete': True
                }
            current_node_id = start_node['id']

        curr_node = node_map.get(current_node_id)
        if not curr_node:
            return {
                'error': f"Node '{current_node_id}' not found.",
                'current_node_id': None,
                'collected_data': collected_data,
                'sim_messages': [],
                'is_complete': True
            }

        next_node_id = None
        ntype = curr_node.get('type')

        if ntype in ['question', 'capture_answer']:
            var_name = curr_node.get('variable_name') or curr_node.get('data', {}).get('variable_name', 'input')
            collected_data[var_name] = message_text
            next_node_id = cls.get_target_node_id(flow_data, current_node_id, 'default')

        elif ntype == 'buttons':
            chosen_opt_id = interactive_reply or message_text
            options = curr_node.get('options') or curr_node.get('data', {}).get('options', [])
            matched_opt = next((o for o in options if o.get('id') == chosen_opt_id or o.get('title', '').lower() == message_text.lower()), None)
            if matched_opt:
                var_name = curr_node.get('variable_name') or curr_node.get('data', {}).get('variable_name', 'choice')
                collected_data[var_name] = matched_opt.get('title')
                next_node_id = matched_opt.get('next_node_id') or cls.get_target_node_id(flow_data, current_node_id, matched_opt.get('id'))
            else:
                next_node_id = cls.get_target_node_id(flow_data, current_node_id, 'default')

        elif ntype == 'list':
            var_name = curr_node.get('variable_name') or curr_node.get('data', {}).get('variable_name', 'selection')
            chosen_row_title = interactive_reply or message_text
            sections = curr_node.get('sections') or curr_node.get('data', {}).get('sections', [])
            matched_row_id = interactive_reply
            for sec in sections:
                for row in sec.get('rows', []):
                    if (interactive_reply and row.get('id') == interactive_reply) or (message_text and row.get('title', '').strip().lower() == message_text.strip().lower()):
                        chosen_row_title = row.get('title')
                        matched_row_id = row.get('id')
                        break
            collected_data[var_name] = chosen_row_title
            next_node_id = cls.get_target_node_id(flow_data, current_node_id, matched_row_id)
            if not next_node_id:
                next_node_id = cls.get_target_node_id(flow_data, current_node_id, 'default')

        elif ntype in ['trigger', 'start']:
            next_node_id = cls.get_target_node_id(flow_data, current_node_id, 'default')

        else:
            next_node_id = current_node_id

        MAX_DEPTH = 30
        depth = 0
        is_complete = False
        waiting_for_input = False

        while next_node_id and depth < MAX_DEPTH:
            depth += 1
            node = node_map.get(next_node_id)
            if not node:
                break

            curr_type = node.get('type')
            current_node_id = node['id']

            if curr_type in ['message', 'welcome']:
                raw_text = node.get('body') or node.get('data', {}).get('text') or ''
                text = cls.interpolate(raw_text, collected_data)
                sim_messages.append({'type': 'text', 'body': text, 'node_id': node['id']})
                next_node_id = cls.get_target_node_id(flow_data, node['id'], 'default')

            elif curr_type == 'buttons':
                raw_text = node.get('body') or node.get('data', {}).get('text') or ''
                text = cls.interpolate(raw_text, collected_data)
                opts = node.get('options') or node.get('data', {}).get('options', [])
                sim_messages.append({
                    'type': 'buttons',
                    'header': node.get('header') or node.get('data', {}).get('header', ''),
                    'body': text,
                    'footer': node.get('footer') or node.get('data', {}).get('footer', ''),
                    'options': opts,
                    'node_id': node['id']
                })
                waiting_for_input = True
                break

            elif curr_type == 'list':
                raw_text = node.get('body') or node.get('data', {}).get('text') or ''
                text = cls.interpolate(raw_text, collected_data)
                btn_txt = node.get('button_text') or node.get('data', {}).get('button_text') or 'View Options'
                sec_list = node.get('sections') or node.get('data', {}).get('sections', [])
                if not sec_list:
                    try:
                        from chat.models import Course
                        active_courses = Course.objects.filter(is_active=True).order_by('display_order', 'name')[:10]
                        if active_courses.exists():
                            rows = [{"id": f"course_{c.id}", "title": (c.name or "")[:24], "description": (c.description or c.duration or "")[:72]} for c in active_courses]
                            sec_list = [{"title": "Programs", "rows": rows}]
                    except Exception:
                        sec_list = []
                sim_messages.append({
                    'type': 'list',
                    'header': node.get('header') or node.get('data', {}).get('header', ''),
                    'body': text,
                    'button_text': btn_txt,
                    'footer': node.get('footer') or node.get('data', {}).get('footer', ''),
                    'sections': sec_list,
                    'node_id': node['id']
                })
                waiting_for_input = True
                break

            elif curr_type in ['question', 'capture_answer']:
                raw_text = node.get('body') or node.get('data', {}).get('text') or ''
                text = cls.interpolate(raw_text, collected_data)
                sim_messages.append({
                    'type': 'question',
                    'body': text,
                    'expected_type': node.get('expected_type') or node.get('data', {}).get('expected_type', 'text'),
                    'node_id': node['id']
                })
                waiting_for_input = True
                break

            elif curr_type == 'condition':
                var = node.get('variable') or node.get('variable_name') or node.get('data', {}).get('variable') or node.get('data', {}).get('variable_name') or ''
                op = node.get('operator') or node.get('data', {}).get('operator', 'contains')
                val = str(node.get('value') or node.get('data', {}).get('value', ''))
                actual = str(collected_data.get(var, ''))
                res = cls.evaluate_condition(actual, op, val)
                port = 'YES' if res else 'NO'
                next_node_id = cls.get_target_node_id(flow_data, node['id'], port)

            elif curr_type in ['save_data', 'update_lead']:
                k = node.get('key') or node.get('variable_name') or node.get('data', {}).get('variable_name') or node.get('data', {}).get('variable') or 'data'
                v = node.get('value') or node.get('data', {}).get('value', '')
                collected_data[k] = cls.interpolate(str(v), collected_data)
                next_node_id = cls.get_target_node_id(flow_data, node['id'], 'default')

            elif curr_type == 'media':
                sim_messages.append({
                    'type': 'media',
                    'caption': cls.interpolate(node.get('caption') or node.get('data', {}).get('caption', ''), collected_data),
                    'filename': node.get('filename') or 'Brochure.pdf',
                    'node_id': node['id']
                })
                next_node_id = cls.get_target_node_id(flow_data, node['id'], 'default')

            elif curr_type == 'location':
                sim_messages.append({
                    'type': 'location',
                    'name': node.get('name') or 'Tech Academy Campus',
                    'address': node.get('address') or '100 Tech Park, Anna Salai',
                    'node_id': node['id']
                })
                next_node_id = cls.get_target_node_id(flow_data, node['id'], 'default')

            elif curr_type == 'lead_status':
                st = node.get('status') or node.get('data', {}).get('status', 'Interested')
                hrs = node.get('follow_up_hours') or node.get('data', {}).get('follow_up_hours')
                crm_actions.append(f"Set Lead status to '{st}'" + (f" (follow up in {hrs}h)" if hrs else ""))
                next_node_id = cls.get_target_node_id(flow_data, node['id'], 'default')

            elif curr_type == 'assign_telecaller':
                mode = node.get('mode') or node.get('data', {}).get('mode', 'auto')
                crm_actions.append(f"Assign Telecaller (Mode: {mode})")
                next_node_id = cls.get_target_node_id(flow_data, node['id'], 'default')

            elif curr_type == 'delay':
                d_sec = node.get('delay_seconds') or node.get('data', {}).get('delay_seconds', 60)
                sim_messages.append({
                    'type': 'delay',
                    'body': f"⏱️ Wait for {d_sec} seconds (simulated)",
                    'node_id': node['id']
                })
                next_node_id = cls.get_target_node_id(flow_data, node['id'], 'default')

            elif curr_type in ['webhook', 'api_request']:
                target = node.get('url') or node.get('data', {}).get('url', 'https://api.example.com')
                sim_messages.append({
                    'type': 'webhook',
                    'body': f"🌐 Outbound webhook dispatched to {target} (simulated)",
                    'node_id': node['id']
                })
                next_node_id = cls.get_target_node_id(flow_data, node['id'], 'default')

            elif curr_type == 'human_handover':
                sim_messages.append({
                    'type': 'handover',
                    'body': '👤 Flow transferred to a human counselor.',
                    'node_id': node['id']
                })
                is_complete = True
                break

            elif curr_type == 'end':
                raw_text = node.get('body') or node.get('data', {}).get('text') or 'Session complete.'
                text = cls.interpolate(raw_text, collected_data)
                sim_messages.append({'type': 'end', 'body': text, 'node_id': node['id']})
                is_complete = True
                break

            else:
                next_node_id = cls.get_target_node_id(flow_data, node['id'], 'default')

        return {
            'success': True,
            'current_node_id': current_node_id,
            'waiting_for_input': waiting_for_input,
            'is_complete': is_complete,
            'collected_data': collected_data,
            'sim_messages': sim_messages,
            'crm_actions': crm_actions
        }
