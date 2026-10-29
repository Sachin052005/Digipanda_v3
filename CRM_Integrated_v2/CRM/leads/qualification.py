from django.utils.html import escape
from django.utils.safestring import mark_safe
"""
Universal Inbound Lead Qualification Normalizer & Auto-fill Service.
Automatically extracts, normalizes, and maps inbound lead answers from
Facebook Lead Ads, WhatsApp Chat flows, Google Sheets, and Walk-in forms
into structured Lead Qualification fields, custom_fields JSON, and CRM records.
"""
import re
import logging
from typing import Dict, Any, Tuple, Optional

from products.models import Product
from branches.models import Branch

log = logging.getLogger('crm')

# Canonical in-call qualification field keys
QUALIFICATION_FIELDS = {
    'degree',
    'passed_out',
    'working_status',
    'designation',
    'join_preference',
    'lead_source',
    'location',
    'purpose',
    'total_experience',
    'courses',
    'pref_branch',
    'pref_exam_loc',
    'college',
    'current_ctc',
    'expected_ctc',
    'retargeted',
}

# Synonym aliases mapping inbound question keys to canonical qualification keys
QUESTION_ALIASES = {
    'degree': [
        'degree', 'qualification', 'education', 'highest qualification',
        'course completed', 'educational qualification', 'study', 'major'
    ],
    'passed_out': [
        'passedout', 'passed out', 'year of pass', 'passing year', 'yop',
        'year of passing', 'graduation year', 'passout year', 'batch year'
    ],
    'working_status': [
        'working status', 'employment status', 'working', 'job status',
        'status of work', 'what best describes you',
        'current status', 'employment', 'are you currently working',
        'are you working or student', 'profession', 'occupation',
        'what describes you best'
    ],
    'designation': [
        'designation', 'role', 'current role', 'job title', 'current designation',
        'position', 'current position'
    ],
    'join_preference': [
        'class mode', 'class_mode', 'demo class', 'demo', 'how would you like to join the course', 'joining preference', 'mode',
        'course mode', 'batch mode', 'prefer learning mode',
        'preferred mode', 'learning mode', 'which batch would you prefer',
        'batch preference', 'training mode', 'preferred batch',
        'mode of training', 'timing', 'batch'
    ],
    'lead_source': [
        'lead source', 'source', 'lead source 1', 'how did you hear about us',
        'referral source'
    ],
    'location': [
        'location', 'city', 'native', 'address', 'current city', 'town',
        'residing city', 'place', 'state'
    ],
    'purpose': [
        'purpose', 'objective', 'reason', 'intent', 'why do you want to learn',
        'goal', 'learning goal'
    ],
    'total_experience': [
        'total experience', 'experience', 'exp', 'work experience',
        'years of experience', 'total exp'
    ],
    'courses': [
        'courses', 'course', 'domain', 'subject', 'interested course',
        'program', 'programme', 'which course are you looking for',
        'interested in', 'selected course'
    ],
    'pref_branch': [
        'preferred branch', 'pref branch', 'branch location', 'nearest branch',
        'preferred center', 'center'
    ],
    'pref_exam_loc': [
        'preferred exam location', 'exam location', 'exam city', 'pref exam loc'
    ],
    'college': [
        'college', 'university', 'institution', 'college name', 'school name',
        'institute', 'university/college'
    ],
    'current_ctc': [
        'current ctc', 'ctc', 'current salary', 'salary', 'present salary',
        'annual salary', 'present ctc'
    ],
    'expected_ctc': [
        'expected ctc', 'exp ctc', 'expected salary', 'future ctc'
    ],
    'retargeted': [
        'retargeted', 'retarget', 're-target', 'is retargeted'
    ]
}


def _clean_str(s: str) -> str:
    s = str(s or '').lower().replace('_', ' ').replace('-', ' ')
    s = re.sub(r'[^a-z0-9 ]', ' ', s)
    return ' '.join(s.split())


# Reverse lookup dictionary: clean lowercase question alias -> canonical field key
_ALIAS_TO_CANONICAL = {}
for canonical, aliases in QUESTION_ALIASES.items():
    _ALIAS_TO_CANONICAL[_clean_str(canonical)] = canonical
    for a in aliases:
        _ALIAS_TO_CANONICAL[_clean_str(a)] = canonical


def match_canonical_field(raw_key: str) -> Optional[str]:
    """
    Finds the canonical qualification field name for any raw inbound question/key.
    Supports exact matching, alias matching, and substring keyword matching.
    """
    if not raw_key:
        return None
    k_clean = _clean_str(raw_key)

    # 1. Exact match in aliases
    if k_clean in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[k_clean]

    # 2. Substring matching
    for alias_clean, canonical in _ALIAS_TO_CANONICAL.items():
        if len(alias_clean) >= 4 and (alias_clean in k_clean or k_clean in alias_clean):
            return canonical

    return None


def extract_course_from_text(text: str) -> Optional[str]:
    """
    Extracts a likely course/program name from campaign, ad, or form strings.
    E.g. 'DP | Leads | Digital Marketing Course | Oct 06 2026 ad' -> 'Digital Marketing Course'
    """
    if not text:
        return None
    tokens = re.split(r'[|\-:]', str(text))
    for tok in tokens:
        tok_clean = tok.strip()
        if any(w in tok_clean.lower() for w in (
            'course', 'program', 'training', 'marketing', 'python', 'java',
            'data science', 'full stack', 'devops', 'aws', 'cloud', 'ai', 'analytics'
        )):
            cleaned = re.sub(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{4}\b', '', tok_clean, flags=re.I).strip()
            cleaned = re.sub(r'\b(ad|leads|lead|campaign)\b', '', cleaned, flags=re.I).strip()
            if cleaned and len(cleaned) > 2:
                return cleaned
    return None


def normalize_value(canonical_key: str, raw_value: Any) -> Tuple[str, Optional[Tuple[str, str]]]:
    """
    Normalizes raw inbound text into CRM dropdown choices.
    Returns (normalized_value, secondary_field_assignment).
    Example: 'career_switcher' -> ('Working professional', ('purpose', 'Career Transition'))
    """
    if raw_value is None:
        return '', None

    val_str = str(raw_value).strip()
    if not val_str or val_str.lower() in ('null', 'none', 'n/a', 'na', 'empty'):
        return '', None

    v_clean = val_str.lower().replace('-', '_').replace(' ', '_').strip()
    secondary_attr = None

    if canonical_key == 'join_preference':
        # Options: ['Online', 'Classroom', 'Hybrid', 'Weekend Batch', 'Weekday Batch']
        if 'demo' in v_clean:
            val_str = 'Demo Class'
        elif any(w in v_clean for w in ('classroom', 'offline', 'in_person', 'walk_in', 'center')):
            val_str = 'Classroom'
        elif any(w in v_clean for w in ('online', 'zoom', 'virtual', 'remote', 'live_online')):
            val_str = 'Online'
        elif 'hybrid' in v_clean or 'both' in v_clean:
            val_str = 'Hybrid'
        elif any(w in v_clean for w in ('weekend', 'saturday', 'sunday')):
            val_str = 'Weekend Batch'
        elif any(w in v_clean for w in ('weekday', 'daily', 'regular', 'mon_fri')):
            val_str = 'Weekday Batch'

    elif canonical_key == 'working_status':
        # Options: ['Working professional', 'Student', 'Looking for job', 'Fresher', 'Career Gap', 'Freelancer', 'Other']
        if any(w in v_clean for w in ('career_switcher', 'career_change', 'switcher', 'transition')):
            val_str = 'Working professional'
            secondary_attr = ('purpose', 'Career Transition')
        elif any(w in v_clean for w in ('student', 'college', 'studying', 'final_year')):
            val_str = 'Student'
        elif any(w in v_clean for w in ('working', 'employed', 'employee', 'professional', 'salaried')):
            val_str = 'Working professional'
        elif any(w in v_clean for w in ('looking_for_job', 'job_seeker', 'jobseeker', 'unemployed', 'searching')):
            val_str = 'Looking for job'
        elif any(w in v_clean for w in ('fresher', 'recent_grad', 'new_grad', 'passed_out')):
            val_str = 'Fresher'
        elif any(w in v_clean for w in ('gap', 'break', 'career_gap')):
            val_str = 'Career Gap'
        elif any(w in v_clean for w in ('freelancer', 'self_employed', 'business')):
            val_str = 'Freelancer'

    elif canonical_key == 'purpose':
        # Options: ['Career Transition', 'Upskilling', 'Placement Assistance', 'Higher Studies', 'Certification', 'Interview Preparation', 'Other']
        if any(w in v_clean for w in ('career_switcher', 'transition', 'switch', 'career_change')):
            val_str = 'Career Transition'
        elif any(w in v_clean for w in ('upskill', 'knowledge', 'skill', 'learn')):
            val_str = 'Upskilling'
        elif any(w in v_clean for w in ('placement', 'job', 'interview', 'career')):
            val_str = 'Placement Assistance'
        elif any(w in v_clean for w in ('higher_studies', 'ms', 'masters', 'abroad')):
            val_str = 'Higher Studies'
        elif any(w in v_clean for w in ('certif', 'diploma')):
            val_str = 'Certification'

    elif canonical_key == 'passed_out':
        match = re.search(r'\b(19\d\d|20\d\d)\b', val_str)
        if match:
            year_int = int(match.group(1))
            if 1970 <= year_int <= 2040:
                val_str = str(year_int)

    elif canonical_key == 'location':
        parts = [p.capitalize() for p in val_str.replace('_', ' ').split()]
        val_str = " ".join(parts)

    elif canonical_key in ('degree', 'college', 'designation'):
        if '_' in val_str:
            val_str = val_str.replace('_', ' ').title()

    return val_str, secondary_attr


def normalize_inbound_payload(data: Dict[str, Any], source: str = '') -> Dict[str, Any]:
    """
    Parses a raw key-value dictionary (from Facebook, WhatsApp, or Google Sheets)
    into a structured qualification mapping.
    """
    if not isinstance(data, dict):
        return {'attributes': {}, 'origins': {}, 'product_suggestion': None, 'branch_suggestion': None}

    attributes = {}
    origins = {}
    product_suggestion = None
    branch_suggestion = None

    skip_keys = {
        'full_name', 'name', 'first_name', 'last_name',
        'phone', 'phone_number', 'alternate_phone', 'email', 'email_address',
        'inbox_url', 'id', 'lead_id', 'provider_event_id', 'created_time',
        '_crm_synced'
    }

    # First check ad/campaign/form names for course extraction
    for metadata_key in ('ad_name', 'campaign_name', 'form_name'):
        meta_val = data.get(metadata_key)
        if meta_val and not product_suggestion:
            ext = extract_course_from_text(meta_val)
            if ext:
                product_suggestion = ext

    for raw_k, raw_v in data.items():
        k_str = str(raw_k).strip()
        if not k_str or k_str.startswith('_') or k_str.lower() in skip_keys:
            continue

        # Check for Course / Product suggestion
        if any(w in k_str.lower() for w in ('course', 'program', 'subject', 'domain')):
            if raw_v and str(raw_v).strip():
                product_suggestion = str(raw_v).strip()

        # Check for Branch / Center suggestion
        if any(w in k_str.lower() for w in ('branch', 'center', 'preferred_branch')):
            if raw_v and str(raw_v).strip():
                branch_suggestion = str(raw_v).strip()

        canonical = match_canonical_field(k_str)
        if canonical:
            val, secondary = normalize_value(canonical, raw_v)
            if val and canonical not in attributes:
                attributes[canonical] = val
                origins[canonical] = source or 'Inbound'
            if secondary:
                sec_key, sec_val = secondary
                if sec_val and sec_key not in attributes:
                    attributes[sec_key] = sec_val
                    origins[sec_key] = source or 'Inbound'

    return {
        'attributes': attributes,
        'origins': origins,
        'product_suggestion': product_suggestion,
        'branch_suggestion': branch_suggestion,
    }


def autofill_lead_qualification(
    lead,
    raw_payload: Dict[str, Any],
    source: str = 'Inbound',
    preserve_manual_edits: bool = True
) -> Dict[str, Any]:
    """
    Applies normalized qualification fields to a Lead instance.
    - Updates lead.custom_fields safely without overwriting human-filled data.
    - Sets lead.product if unassigned and matched (or stores in custom_fields).
    - Sets lead.branch if unassigned and matched.
    - Appends structured notes attributes.
    Returns dictionary of applied fields.
    """
    if not lead or not raw_payload:
        return {}

    parsed = normalize_inbound_payload(raw_payload, source=source)
    attributes = parsed['attributes']
    origins = parsed['origins']

    cf = dict(lead.custom_fields or {})
    field_origins = dict(cf.get('_field_origins') or {})

    applied = {}
    updated_fields = set()

    for key, val in attributes.items():
        existing_val = cf.get(key)
        if preserve_manual_edits and existing_val and str(existing_val).strip() not in ('', 'Empty'):
            continue

        cf[key] = val
        field_origins[key] = origins.get(key, source)
        applied[key] = val

    # Resolve product if lead has no product
    prod_candidate = parsed.get('product_suggestion') or attributes.get('courses')
    if prod_candidate:
        if not lead.product_id:
            matched_prod = (
                Product.objects.filter(name__iexact=prod_candidate, status='Active').first()
                or Product.objects.filter(name__icontains=prod_candidate, status='Active').first()
            )
            if matched_prod:
                lead.product = matched_prod
                updated_fields.add('product')
                applied['courses'] = matched_prod.name
            else:
                if 'courses' not in cf or not cf['courses']:
                    cf['courses'] = prod_candidate
                    field_origins['courses'] = origins.get('courses', source)
                    applied['courses'] = prod_candidate

    # Resolve branch if lead has no branch
    if not lead.branch_id:
        branch_candidate = parsed.get('branch_suggestion') or attributes.get('pref_branch') or attributes.get('location')
        if branch_candidate:
            matched_branch = (
                Branch.objects.filter(name__iexact=branch_candidate, status='Active').first()
                or Branch.objects.filter(name__icontains=branch_candidate, status='Active').first()
            )
            if matched_branch:
                lead.branch = matched_branch
                updated_fields.add('branch')
                applied['branch'] = matched_branch.name

    if applied or ('_field_origins' not in cf and field_origins):
        cf['_field_origins'] = field_origins
        lead.custom_fields = cf
        updated_fields.add('custom_fields')

    # Synchronize structured attributes into notes format (pipes) for legacy compatibility
    if applied:
        from .detail_service import update_lead_notes_attribute
        current_notes = lead.notes or ''
        for k, v in applied.items():
            if k in QUALIFICATION_FIELDS:
                current_notes = update_lead_notes_attribute(current_notes, k, v)
        if current_notes != lead.notes:
            lead.notes = current_notes
            updated_fields.add('notes')

    if updated_fields:
        lead.save(update_fields=list(updated_fields) + ['updated_at'])
        log.info("Autofilled lead #%s qualification from %s: %s", lead.id, source, list(applied.keys()))

    return applied


def generate_smart_precall_pitch(lead) -> str:
    """
    Generates a high-impact, contextual 1-line or 2-line pre-call brief for Telecallers
    based on the lead's qualification attributes.
    Example:
    'Sandhiya Babu is a Career Transition looking for Classroom Training in Coimbatore for Digital Marketing Course.'
    """
    cf = lead.custom_fields or {}
    
    name = lead.name or "The lead"
    status = cf.get('working_status') or ''
    purpose = cf.get('purpose') or ''
    mode = cf.get('join_preference') or ''
    loc = cf.get('location') or (lead.branch.name if lead.branch else '')
    course = lead.product.name if lead.product else cf.get('courses', '')

    # Qualification persona
    if purpose and purpose not in ('Other', 'Empty'):
        persona = purpose
    elif status and status not in ('Other', 'Empty'):
        persona = status
    else:
        persona = ""

        # Sanitize and HTML-escape all user-controlled values to eliminate Stored XSS
    safe_name = escape(name)
    safe_persona = escape(persona)
    safe_mode = escape(mode)
    safe_course = escape(course)
    safe_loc = escape(loc)

    desc = f"<strong>{safe_name}</strong>"
    if persona:
        desc += f" is a <strong>{safe_persona}</strong>"
    if mode and mode != 'Empty':
        desc += f" interested in <strong>{safe_mode}</strong>"
    if course and course != 'Empty':
        desc += f" for <strong>{safe_course}</strong>"
    if loc and loc != 'Empty':
        desc += f" (<em>{safe_loc}</em>)"

    if desc == f"<strong>{safe_name}</strong>":
        return ""
    
    return mark_safe(desc + ".")
