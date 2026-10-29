"""
Centralized Semantic Status Classifier for TechPanda CRM.
Intelligently classifies raw spreadsheet, form, and telecaller remarks into:
(lead_status, call_status, call_outcome)
"""
from typing import Any, Tuple
from leads.models import LeadStatus
from calls.models import CallStatus, CallOutcome


def classify_sheet_status(status_raw: Any) -> Tuple[str, str, str]:
    """
    Intelligently classifies a raw status/remarks string into:
    (lead_status, call_status, call_outcome)

    Evaluation Hierarchy (Evaluates negative/rejection patterns before positive keywords):
    1. Switched Off
    2. No Answer / Unreachable / RNR
    3. Not Interested / Ineligible / Wrong Number
    4. Demo Scheduled
    5. Follow-up Required / Need Time / Callback
    6. Interested / Details Shared / Planning to visit
    7. Exact match in LeadStatus choices
    8. Free-form fallback -> Contacted with CallNotes preserved
    9. Empty -> LeadStatus.NEW, Queued, Follow-up Required
    """
    if not status_raw:
        return LeadStatus.NEW, 'Queued', 'Follow-up Required'

    s_clean = str(status_raw).strip()
    if not s_clean:
        return LeadStatus.NEW, 'Queued', 'Follow-up Required'

    s_lower = s_clean.lower()

    # 1. Switched Off rule
    if ('switch' in s_lower and 'off' in s_lower) or 'switchedoff' in s_lower:
        switched_off_val = getattr(LeadStatus, 'SWITCHED_OFF', 'Switched Off')
        return switched_off_val, CallStatus.FAILED, CallOutcome.NO_ANSWER

    # 2. No Answer / Unreachable / RNR rule
    no_answer_patterns = (
        'not connected', 'not connect', 'not picked', 'not piicked', 'out of service', 'out of services',
        'rnr', 'ring no response', 'not reachable', 'unreachable', 'number not reachable',
        'not exist', 'does not exist', 'no answer', 'busy', 'call busy'
    )
    if any(pat in s_lower for pat in no_answer_patterns):
        return LeadStatus.NO_ANSWER, CallStatus.NO_ANSWER, CallOutcome.RNR

    # 3. Not Interested / Ineligible / Wrong Number rule (Checked BEFORE 'interested')
    not_interested_patterns = (
        'not interested', 'not interest', 'by mistake', 'already enrolled',
        'wrong number', 'want internship only', 'not eligible', 'not willing',
        'not looking', 'disinterested'
    )
    if any(pat in s_lower for pat in not_interested_patterns):
        return LeadStatus.NOT_INTERESTED, CallStatus.CONNECTED, CallOutcome.NOT_INTERESTED

    # 4. Demo Scheduled rule
    demo_patterns = ('demo fix', 'demo scheduled', 'need demo', 'demo class', 'demo attended')
    if any(pat in s_lower for pat in demo_patterns) or s_lower == 'demo':
        return LeadStatus.DEMO_SCHEDULED, CallStatus.CONNECTED, CallOutcome.INTERESTED

    # 5. Follow-up rule
    followup_patterns = (
        'follow up', 'follow-up', 'followup', 'call later', 'call back', 'callback',
        'need time', 'call after', 'discuss with family', 'let you know',
        'will call', 'share the details', 'later', 'think and say', 'call tomorrow'
    )
    if any(pat in s_lower for pat in followup_patterns):
        return LeadStatus.FOLLOW_UP, CallStatus.CONNECTED, CallOutcome.FOLLOW_UP_REQUIRED

    # 6. Interested rule
    interested_patterns = (
        'interested', 'details shared', 'planning to visit', 'full stack', 'fullstock',
        'course details', 'looking for class', 'want to join', 'joining'
    )
    if any(pat in s_lower for pat in interested_patterns):
        return LeadStatus.INTERESTED, CallStatus.CONNECTED, CallOutcome.INTERESTED

    # 7. Exact match against LeadStatus.choices
    for code, label in LeadStatus.choices:
        if s_lower == code.lower() or s_lower == label.lower():
            outcome = CallOutcome.INTERESTED if code in ('Interested', 'Converted', 'Enrolled') else CallOutcome.FOLLOW_UP_REQUIRED
            return code, CallStatus.CONNECTED, outcome

    # 8. Default fallback for other unclassified free-form remarks:
    # Set to 'Contacted', preserve exact text in call notes
    return LeadStatus.CONTACTED, CallStatus.CONNECTED, CallOutcome.FOLLOW_UP_REQUIRED
