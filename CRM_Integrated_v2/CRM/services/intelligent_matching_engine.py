import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

# ==============================================================================
# AUTHORITATIVE CRM FIELD INVENTORY & MULTILINGUAL KNOWLEDGE BASE
# ==============================================================================

AUTHORITATIVE_FIELD_INVENTORY: Dict[str, Dict[str, Any]] = {
    'name': {
        'label': 'Full Name',
        'type': 'string',
        'category': 'Identity',
        'is_primary': False,
        'aliases': [
            'full name', 'fullname', 'name', 'lead name', 'student name',
            'candidate name', 'applicant name', 'client name', 'person name',
            'customer name', 'enquirer name', 'contact name', 'student', 'candidate'
        ],
        'multilingual': {
            'ta': ['பெயர்', 'மாணவர் பெயர்', 'விண்ணப்பதாரர் பெயர்', 'முழு பெயர்'],
            'hi': ['नाम', 'पूरा नाम', 'छात्र का नाम', 'उम्मीदवार का नाम', 'विद्यार्थी का नाम']
        },
        'regex': r"^[A-Za-z\s\.\'\-]{2,60}$"
    },
    'first_name': {
        'label': 'First Name',
        'type': 'string',
        'category': 'Identity',
        'is_primary': False,
        'aliases': [
            'first name', 'firstname', 'given name', 'forename', 'fname', 'first'
        ],
        'multilingual': {
            'ta': ['முதல் பெயர்'],
            'hi': ['पहला नाम']
        },
        'regex': r"^[A-Za-z\s\.\'\-]{2,40}$"
    },
    'last_name': {
        'label': 'Last Name',
        'type': 'string',
        'category': 'Identity',
        'is_primary': False,
        'aliases': [
            'last name', 'lastname', 'surname', 'family name', 'lname', 'last'
        ],
        'multilingual': {
            'ta': ['கடைசி பெயர்', 'குடும்பப் பெயர்'],
            'hi': ['अंतिम नाम', 'उपनाम']
        },
        'regex': r"^[A-Za-z\s\.\'\-]{1,40}$"
    },
    'phone': {
        'label': 'Phone Number',
        'type': 'phone',
        'category': 'Contact (Primary Key)',
        'is_primary': True,
        'aliases': [
            'number', 'numbers', 'phone number', 'phonenumber', 'phone', 'mobile number', 'mobilenumber',
            'mobile', 'contact number', 'contactnumber', 'contact', 'whatsapp number',
            'whatsapp', 'contact phone', 'phone no', 'phoneno', 'mobile no', 'mobileno',
            'contact no', 'contactno', 'tel', 'telephone', 'cell', 'cell phone',
            'primary phone', 'primary mobile', 'call number', 'calling number',
            'wa number', 'wa no', 'ph no', 'mob'
        ],
        'multilingual': {
            'ta': ['தொலைபேசி', 'கைபேசி', 'கைபேசி எண்', 'தொலைபேசி எண்', 'தொடர்பு எண்'],
            'hi': ['फ़ोन', 'फोन', 'मोबाइल', 'फ़ोन नंबर', 'मोबाइल नंबर', 'संपर्क नंबर']
        },
        'regex': r"^(?:\+?91[\-\s]?)?[6789]\d{9}$|^\+?[1-9]\d{6,14}$"
    },
    'alternate_phone': {
        'label': 'Alternate Phone',
        'type': 'phone',
        'category': 'Contact',
        'is_primary': False,
        'aliases': [
            'alternate phone', 'alternate mobile', 'alt phone', 'alt mobile',
            'secondary phone', 'alternate number', 'second phone', 'alternate contact',
            'alt phone no', 'alt mobile no', 'alt no', 'secondary mobile', 'other phone',
            'parent phone', 'emergency contact', 'guardian phone', 'father phone'
        ],
        'multilingual': {
            'ta': ['மாற்று தொலைபேசி', 'மாற்று எண்', 'இரண்டாவது கைபேசி'],
            'hi': ['वैकल्पिक फ़ोन', 'अन्य नंबर', 'दूसरा मोबाइल']
        },
        'regex': r"^(?:\+?91[\-\s]?)?[6789]\d{9}$|^\+?[1-9]\d{6,14}$"
    },
    'email': {
        'label': 'Email Address',
        'type': 'email',
        'category': 'Contact',
        'is_primary': False,
        'aliases': [
            'email address', 'emailaddress', 'email', 'e mail', 'e-mail',
            'e mail address', 'mail id', 'mailid', 'email id', 'emailid',
            'mail', 'electronic mail', 'student email', 'candidate email'
        ],
        'multilingual': {
            'ta': ['மின்னஞ்சல்', 'மின்னஞ்சல் முகவரி', 'ஈமெயில்'],
            'hi': ['ईमेल', 'ई-मेल', 'ईमेल पता']
        },
        'regex': r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    },
    'product': {
        'label': 'Product / Course',
        'type': 'entity_product',
        'category': 'Interest',
        'is_primary': False,
        'aliases': [
            'interested course', 'interested product', 'course', 'product',
            'program', 'interested in', 'course interested', 'course name',
            'stream', 'training program', 'technology', 'specialization',
            'course opted', 'subject', 'courses',
            'wat course are you looking for ?', 'wat course are you looking for',
            'what course are you looking for ?', 'what course are you looking for',
            'which course are you interested in?', 'which course are you interested in',
            'select course', 'chosen course'
        ],
        'multilingual': {
            'ta': ['படிப்பு', 'பாடநெறி', 'விருப்பமான படிப்பு', 'பயிற்சி திட்டம்'],
            'hi': ['कोर्स', 'पाठ्यक्रम', 'विषय', 'पसंदीदा कोर्स']
        }
    },
    'branch': {
        'label': 'Branch / Center',
        'type': 'entity_branch',
        'category': 'Location',
        'is_primary': False,
        'aliases': [
            'branch', 'center', 'centre', 'branch center', 'location', 'city',
            'preferred branch', 'preferred location', 'campus', 'preferred center',
            'office location', 'training center', 'institute location', 'hub',
            'preferred city', 'nearest branch', 'nearest center'
        ],
        'multilingual': {
            'ta': ['கிளை', 'மையம்', 'இடம்', 'விருப்பமான கிளை', 'வளாகம்'],
            'hi': ['शाखा', 'केंद्र', 'स्थान', 'पसंदीदा शाखा']
        }
    },
    'channel': {
        'label': 'Lead Channel / Source',
        'type': 'entity_channel',
        'category': 'Marketing',
        'is_primary': False,
        'aliases': [
            'channel', 'lead source', 'source', 'platform', 'campaign',
            'channel name', 'acquisition channel', 'medium', 'utm source',
            'marketing channel', 'origin', 'inquiry source'
        ],
        'multilingual': {
            'ta': ['சேனல்', 'மூலம்', 'வழியே', 'தொடர்பு வழி'],
            'hi': ['स्रोत', 'माध्यम', 'चैनल']
        }
    },
    'class_mode': {
        'label': 'Class Mode / Learning Preference',
        'type': 'choice_mode',
        'category': 'Interest',
        'is_primary': False,
        'aliases': [
            'class mode', 'mode', 'learning mode', 'training mode',
            'mode of class', 'mode of training', 'preference', 'join preference',
            'online offline', 'online / offline', 'mode of study', 'batch type',
            'learning preference', 'attendance mode', 'demo class', 'demo'
        ],
        'multilingual': {
            'ta': ['பயிற்சி முறை', 'சேர்க்கை முறை', 'வகுப்பு முறை', 'ஆன்லைன் அல்லது ஆஃப்லைன்'],
            'hi': ['प्रवेश मोड', 'कक्षा मोड', 'प्रशिक्षण का प्रकार', 'ऑनलाइन या ऑफलाइन']
        },
        'allowed_values': ['online', 'offline', 'hybrid', 'classroom', 'direct', 'remote']
    },
    'status': {
        'label': 'Lead Status',
        'type': 'choice_status',
        'category': 'Pipeline',
        'is_primary': False,
        'aliases': [
            'status', 'lead status', 'current status', 'stage', 'lead stage',
            'disposition', 'call status', 'call outcome'
        ],
        'multilingual': {
            'ta': ['நிலை', 'தற்போதைய நிலை', 'முன்னேற்றம்'],
            'hi': ['स्थिति', 'लीड स्थिति', 'वर्तमान स्थिति']
        }
    },
    'notes': {
        'label': 'Notes / Remarks',
        'type': 'text',
        'category': 'Communication',
        'is_primary': False,
        'aliases': [
            'notes', 'remarks', 'comments', 'feedback', 'message', 'query',
            'comments / questions', 'comments/questions',
            'what you looking for?', 'what you looking for',
            'what is your current status?', 'what is your current status',
            'requirement', 'conservation step', 'inquiry details', 'description',
            'additional info', 'client remarks', 'conversation summary'
        ],
        'multilingual': {
            'ta': ['குறிப்புகள்', 'கருத்துக்கள்', 'விவரங்கள்', 'கேள்விகள்'],
            'hi': ['टिप्पणियाँ', 'विवरण', 'सुझाव', 'संदेश']
        }
    },
    'assigned_counselor': {
        'label': 'Assigned Counselor',
        'type': 'entity_user',
        'category': 'Assignment',
        'is_primary': False,
        'aliases': [
            'counselors', 'counselor', 'assigned counselor', 'telecaller', 'assigned telecaller',
            'executive', 'staff', 'owner', 'lead owner', 'assigned to',
            'advisor', 'academic counselor', 'counselor name'
        ],
        'multilingual': {
            'ta': ['ஆலோசகர்', 'பொறுப்பாளர்'],
            'hi': ['सलाहकार', 'प्रभारी']
        }
    },
    'walkin_date': {
        'label': 'Walk-in / Visit Date',
        'type': 'date',
        'category': 'Scheduling',
        'is_primary': False,
        'aliases': [
            'walk in date', 'walkin date', 'walk-in date', 'visit date',
            'appointment date', 'date of visit', 'enquiry date', 'inquiry date',
            'scheduled date', 'demo date', 'followup date', 'follow up date',
            'walkin', 'walk in'
        ],
        'multilingual': {
            'ta': ['நேரடி வருகை தேதி', 'வருகை தேதி', 'தேதி'],
            'hi': ['मुलाकात की तारीख', 'दौरे की तारीख', 'दिनांक']
        }
    },
    'gender': {
        'label': 'Gender',
        'type': 'choice_gender',
        'category': 'Demographics',
        'is_primary': False,
        'aliases': [
            'gender', 'sex'
        ],
        'multilingual': {
            'ta': ['பாலினம்'],
            'hi': ['लिंग']
        },
        'allowed_values': ['male', 'female', 'other', 'transgender', 'm', 'f']
    },
    'degree': {
        'label': 'Degree / Qualification',
        'type': 'string',
        'category': 'Qualification',
        'is_primary': False,
        'aliases': [
            'degree', 'qualification', 'highest qualification', 'education',
            'educational qualification', 'academic degree', 'department',
            'college degree', 'grad degree', 'undergraduate', 'postgraduate'
        ],
        'multilingual': {
            'ta': ['பட்டப்படிப்பு', 'கல்வித்தகுதி', 'படிப்புத் தகுதி'],
            'hi': ['डिग्री', 'योग्यता', 'शैक्षिक योग्यता']
        }
    },
    'passed_out': {
        'label': 'Passed Out Year / Year of Graduation',
        'type': 'year',
        'category': 'Qualification',
        'is_primary': False,
        'aliases': [
            'passed out', 'pass out year', 'passed out year', 'yop',
            'year of pass', 'year of passing', 'graduation year', 'batch',
            'completion year', 'grad year'
        ],
        'multilingual': {
            'ta': ['முடித்த ஆண்டு', 'தேர்ச்சி பெற்ற ஆண்டு', 'ஆண்டு'],
            'hi': ['उत्तीर्ण वर्ष', 'पास होने का वर्ष', 'वर्ष']
        },
        'regex': r"^(?:19|20)\d{2}$"
    },
    'working_status': {
        'label': 'Working Status / Employment',
        'type': 'choice_employment',
        'category': 'Qualification',
        'is_primary': False,
        'aliases': [
            'working status', 'employment status', 'job status', 'current employment',
            'employed', 'working', 'occupation', 'profession', 'are you working?'
        ],
        'multilingual': {
            'ta': ['வேலை நிலை', 'தொழில் நிலை'],
            'hi': ['कार्य स्थिति', 'रोजगार की स्थिति']
        },
        'allowed_values': ['employed', 'unemployed', 'student', 'working', 'fresher', 'job seeker']
    },
    'location': {
        'label': 'Student Location / Native City',
        'type': 'string',
        'category': 'Location',
        'is_primary': False,
        'aliases': [
            'location', 'native', 'native location', 'home town', 'hometown',
            'current location', 'residence', 'address', 'area', 'native place'
        ],
        'multilingual': {
            'ta': ['சொந்த ஊர்', 'இடம்', 'இருப்பிடம்'],
            'hi': ['मूल स्थान', 'निवास स्थान', 'शहर']
        }
    }
}


# ==============================================================================
# NORMALIZATION & FUZZY MATCHING UTILITIES
# ==============================================================================

def normalize_header(header: Any) -> str:
    """
    Normalizes a column header:
    - Strips leading/trailing whitespace
    - Normalizes Unicode (NFKC) preserving non-Latin scripts (Tamil, Hindi)
    - Replaces punctuation, hyphens, and multiple spaces with a single space
    - Converts Latin characters to lowercase
    """
    if header is None:
        return ''
    s = unicodedata.normalize('NFKC', str(header)).strip().lower()
    # Replace special chars, separators, underscores, punctuation with space
    s = re.sub(r'[\s_\-\.\:\;\,\?\!\/\|\(\)\[\]\{\}\<\>]+', ' ', s)
    return s.strip()


def fuzzy_similarity_score(s1: str, s2: str) -> float:
    """
    Computes a robust similarity score between two normalized strings:
    Combines Levenshtein ratio (via SequenceMatcher) with token sort ratio.
    Pure Python - zero external C-dependencies.
    """
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0

    # 1. Standard SequenceMatcher ratio
    base_ratio = SequenceMatcher(None, s1, s2).ratio()

    # 2. Token sort ratio (handles word reordering, e.g. "number phone" vs "phone number")
    tokens1 = sorted(s1.split())
    tokens2 = sorted(s2.split())
    sorted_s1 = " ".join(tokens1)
    sorted_s2 = " ".join(tokens2)
    token_sort_ratio = SequenceMatcher(None, sorted_s1, sorted_s2).ratio()

    # 3. Substring containment bonus
    containment_bonus = 0.0
    if (s1 in s2 or s2 in s1) and min(len(s1), len(s2)) >= 3:
        containment_bonus = 0.15

    score = max(base_ratio, token_sort_ratio) + containment_bonus
    return min(1.0, round(score, 4))


# ==============================================================================
# CELL VALUE PATTERN ANALYZER
# ==============================================================================

# Common regex patterns for cell data
PHONE_REGEX = re.compile(r"^(?:p:|tel:)?(?:\+?91[\-\s]?)?[6789]\d{9}$|^(?:p:|tel:)?\+?[1-9]\d{6,14}$", re.IGNORECASE)
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DATE_REGEX = re.compile(r"^\d{4}[\-\/]\d{1,2}[\-\/]\d{1,2}$|^\d{1,2}[\-\/]\d{1,2}[\-\/]\d{2,4}$")
YEAR_REGEX = re.compile(r"^(?:19|20)\d{2}$")
NAME_REGEX = re.compile(r"^[A-Za-z\u0B80-\u0BFF\u0900-\u097F\s\.\'\-]{2,60}$")


def analyze_column_values(values: List[Any], active_entities: Optional[Dict[str, List[str]]] = None) -> Dict[str, float]:
    """
    Analyzes non-empty sample cell values in a column to compute statistical
    affinity scores [0.0 - 1.0] for known CRM data types.
    """
    cleaned_vals = [str(v).strip() for v in values if v is not None and str(v).strip() != '']
    if not cleaned_vals:
        return {}

    total = len(cleaned_vals)
    phone_matches = 0
    email_matches = 0
    date_matches = 0
    year_matches = 0
    name_matches = 0
    gender_matches = 0
    mode_matches = 0
    branch_matches = 0
    product_matches = 0
    counselor_matches = 0

    known_branches = [b.lower() for b in (active_entities.get('branches', []) if active_entities else [])]
    known_products = [p.lower() for p in (active_entities.get('products', []) if active_entities else [])]
    known_users = [u.lower() for u in (active_entities.get('users', []) if active_entities else [])]

    gender_set = {'male', 'female', 'other', 'm', 'f', 'transgender', 'ஆண்', 'பெண்', 'पुरुष', 'महिला'}
    mode_set = {'online', 'offline', 'hybrid', 'classroom', 'direct', 'நேரடி', 'ஆன்லைன்'}

    for val in cleaned_vals:
        val_clean = val.lower()
        val_digits = re.sub(r'\D', '', val)

        # Phone check: 10 Indian digits, or 10-15 international digits
        if len(val_digits) == 10 and val_digits[0] in '6789':
            phone_matches += 1
        elif 10 <= len(val_digits) <= 13 and (PHONE_REGEX.match(val) or val_digits[-10:-9] in '6789'):
            phone_matches += 1

        # Email check
        if EMAIL_REGEX.match(val):
            email_matches += 1

        # Date check
        if DATE_REGEX.match(val):
            date_matches += 1

        # Year check
        if YEAR_REGEX.match(val):
            year_matches += 1

        # Name check (valid string without digits or @)
        if NAME_REGEX.match(val) and not re.search(r'\d', val) and '@' not in val:
            name_matches += 1

        # Gender check
        if val_clean in gender_set:
            gender_matches += 1

        # Mode check
        if val_clean in mode_set:
            mode_matches += 1

        # Branch entity check
        if any(b in val_clean or val_clean in b for b in known_branches if len(b) >= 3):
            branch_matches += 1

        # Product entity check
        if any(p in val_clean or val_clean in p for p in known_products if len(p) >= 3):
            product_matches += 1

        # Counselor check
        if any(u in val_clean or val_clean in u for u in known_users if len(u) >= 3):
            counselor_matches += 1

    return {
        'phone': round(phone_matches / total, 3),
        'email': round(email_matches / total, 3),
        'date': round(date_matches / total, 3),
        'year': round(year_matches / total, 3),
        'name': round(name_matches / total, 3),
        'gender': round(gender_matches / total, 3),
        'class_mode': round(mode_matches / total, 3),
        'branch': round(branch_matches / total, 3),
        'product': round(product_matches / total, 3),
        'assigned_counselor': round(counselor_matches / total, 3),
    }


# ==============================================================================
# SINGLE-COLUMN MATCHING WITH EXPLAINABILITY & CONFIDENCE
# ==============================================================================

class ColumnMatchResult:
    """Holds the match outcome, confidence score, tier, and explainable reasons for a column."""
    def __init__(
        self,
        header: str,
        crm_field: Optional[str],
        confidence: float,
        tier: str,
        reasons: List[str],
        alternatives: List[Dict[str, Any]],
        sample_values: List[Any]
    ):
        self.header = header
        self.crm_field = crm_field
        self.confidence = confidence
        self.tier = tier  # 'HIGH', 'MEDIUM', 'LOW'
        self.reasons = reasons
        self.alternatives = alternatives
        self.sample_values = sample_values[:5]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'header': self.header,
            'crm_field': self.crm_field,
            'confidence': self.confidence,
            'tier': self.tier,
            'reasons': self.reasons,
            'alternatives': self.alternatives,
            'sample_values': self.sample_values,
        }


def match_column(
    header: str,
    sample_values: List[Any],
    active_entities: Optional[Dict[str, List[str]]] = None,
    confirmed_memory: Optional[Dict[str, str]] = None
) -> ColumnMatchResult:
    """
    Evaluates a single header against the CRM field inventory using:
    1. Exact normalized match
    2. Known alias dictionary match
    3. Multilingual (Tamil, Hindi) match
    4. Deterministic token fuzzy match
    5. Cell value pattern validation
    6. Historical mapping memory bonus
    """
    norm_h = normalize_header(header)
    val_affinities = analyze_column_values(sample_values, active_entities)
    sample_preview = [str(v) for v in sample_values if v is not None and str(v).strip() != ''][:5]

    # Generate candidate header representations (handling bloated header cells or concatenated values)
    raw_header_str = str(header).strip() if header is not None else ''
    first_line_clean = raw_header_str.splitlines()[0].strip() if raw_header_str else ''
    norm_first_line = normalize_header(first_line_clean)

    tokens = norm_h.split()
    first_token = tokens[0] if tokens else ''
    two_tokens = " ".join(tokens[:2]) if len(tokens) >= 2 else ''
    three_tokens = " ".join(tokens[:3]) if len(tokens) >= 3 else ''

    header_variants = []
    if norm_h:
        header_variants.append(norm_h)
    if norm_first_line and norm_first_line not in header_variants:
        header_variants.append(norm_first_line)
    if three_tokens and three_tokens not in header_variants:
        header_variants.append(three_tokens)
    if two_tokens and two_tokens not in header_variants:
        header_variants.append(two_tokens)
    if first_token and first_token not in header_variants:
        header_variants.append(first_token)

    candidates: List[Dict[str, Any]] = []

    for field_name, field_def in AUTHORITATIVE_FIELD_INVENTORY.items():
        header_score = 0.0
        reasons: List[str] = []
        is_exact = False
        is_alias = False
        is_multilingual = False

        norm_field_name = normalize_header(field_name)
        norm_field_label = normalize_header(field_def['label'])

        # 1. Exact normalized check across full header and candidate prefixes
        for h_var in header_variants:
            if h_var == norm_field_name or h_var == norm_field_label:
                header_score = 1.0 if h_var == norm_h else 0.96
                is_exact = True
                if h_var == norm_h:
                    reasons.append(f"Exact header match with '{field_def['label']}'")
                else:
                    reasons.append(f"Header prefix '{h_var}' matches '{field_def['label']}'")
                break

        # 2. Alias dictionary check across full header and candidate prefixes
        if not is_exact:
            for alias in field_def.get('aliases', []):
                norm_alias = normalize_header(alias)
                for h_var in header_variants:
                    if h_var == norm_alias:
                        header_score = 0.95
                        is_alias = True
                        if h_var == norm_h:
                            reasons.append(f"Matched known alias '{alias}'")
                        else:
                            reasons.append(f"Header prefix '{h_var}' matched known alias '{alias}'")
                        break
                if is_alias:
                    break
                if norm_h.startswith(norm_alias + ' '):
                    header_score = 0.95
                    is_alias = True
                    reasons.append(f"Header starts with known alias '{alias}'")
                    break

        # 3. Multilingual check (Tamil & Hindi)
        if not is_exact and not is_alias:
            for lang, trans_list in field_def.get('multilingual', {}).items():
                for trans in trans_list:
                    norm_trans = normalize_header(trans)
                    for h_var in header_variants:
                        if h_var == norm_trans:
                            header_score = 0.95
                            is_multilingual = True
                            lang_name = 'Tamil' if lang == 'ta' else 'Hindi'
                            reasons.append(f"Matched {lang_name} translation '{trans}'")
                            break
                    if is_multilingual:
                        break
                    if norm_h.startswith(norm_trans + ' '):
                        header_score = 0.95
                        is_multilingual = True
                        lang_name = 'Tamil' if lang == 'ta' else 'Hindi'
                        reasons.append(f"Header starts with {lang_name} translation '{trans}'")
                        break
                if is_multilingual:
                    break

        # 4. Fuzzy token match across header and candidate prefixes
        if not is_exact and not is_alias and not is_multilingual:
            best_fuzzy = 0.0
            best_fuzzy_target = ''
            all_targets = [field_def['label']] + field_def.get('aliases', [])
            for target in all_targets:
                norm_tgt = normalize_header(target)
                for h_var in header_variants:
                    f_score = fuzzy_similarity_score(h_var, norm_tgt)
                    if f_score > best_fuzzy:
                        best_fuzzy = f_score
                        best_fuzzy_target = target

            if best_fuzzy >= 0.70:
                header_score = round(best_fuzzy * 0.90, 3)
                reasons.append(f"Fuzzy match with '{best_fuzzy_target}' (score: {round(best_fuzzy, 2)})")

        # 5. Cell value pattern affinity
        value_score = 0.0
        contradiction = False
        field_type = field_def.get('type')
        if field_type == 'phone':
            if val_affinities.get('phone', 0) > 0.3:
                value_score = val_affinities['phone']
                reasons.append(f"{int(value_score * 100)}% of sample values match phone regex")
            elif val_affinities.get('email', 0) > 0.5 or val_affinities.get('name', 0) > 0.7:
                contradiction = True
                reasons.append("Contradiction: Sample values do not appear to be phone numbers")
        elif field_type == 'email':
            if val_affinities.get('email', 0) > 0.3:
                value_score = val_affinities['email']
                reasons.append(f"{int(value_score * 100)}% of sample values match email pattern")
            elif val_affinities.get('phone', 0) > 0.5:
                contradiction = True
                reasons.append("Contradiction: Sample values appear to be phone numbers rather than emails")
        elif field_name in ('name', 'first_name', 'last_name'):
            if val_affinities.get('name', 0) > 0.3:
                value_score = val_affinities['name']
                reasons.append(f"{int(value_score * 100)}% of sample values match name text patterns")
            elif val_affinities.get('phone', 0) > 0.5 or val_affinities.get('email', 0) > 0.5:
                contradiction = True
                reasons.append("Contradiction: Sample values are numbers or emails rather than names")
        elif field_type == 'date':
            if val_affinities.get('date', 0) > 0.3:
                value_score = val_affinities['date']
                reasons.append(f"{int(value_score * 100)}% of sample values match date pattern")
        elif field_type == 'year':
            if val_affinities.get('year', 0) > 0.3:
                value_score = val_affinities['year']
                reasons.append(f"{int(value_score * 100)}% of sample values match year pattern")
        elif field_type == 'choice_gender':
            if val_affinities.get('gender', 0) > 0.3:
                value_score = val_affinities['gender']
                reasons.append(f"{int(value_score * 100)}% of sample values are gender values")
        elif field_type == 'choice_mode':
            if val_affinities.get('class_mode', 0) > 0.3:
                value_score = val_affinities['class_mode']
                reasons.append(f"{int(value_score * 100)}% of sample values indicate learning mode")
        elif field_type == 'entity_branch':
            if val_affinities.get('branch', 0) > 0.2:
                value_score = val_affinities['branch']
                reasons.append(f"{int(value_score * 100)}% of sample values match active branch names")
        elif field_type == 'entity_product':
            if val_affinities.get('product', 0) > 0.2:
                value_score = val_affinities['product']
                reasons.append(f"{int(value_score * 100)}% of sample values match active courses")
        elif field_type == 'entity_user':
            if val_affinities.get('assigned_counselor', 0) > 0.2:
                value_score = val_affinities['assigned_counselor']
                reasons.append(f"{int(value_score * 100)}% of sample values match staff counselor names")

        # 6. Memory bonus
        memory_score = 0.0
        if confirmed_memory and confirmed_memory.get(header) == field_name:
            memory_score = 1.0
            reasons.append("Previously confirmed by user for this spreadsheet")

        # 7. Composite score calculation
        if contradiction:
            composite = 0.20
        elif memory_score == 1.0:
            composite = 0.98
        elif is_exact:
            composite = 1.0 if (value_score >= 0.5 or value_score == 0) else 0.88
        elif is_alias or is_multilingual:
            composite = 0.96 if (value_score >= 0.5 or value_score == 0) else 0.85
        elif header_score > 0 and value_score > 0:
            composite = (0.60 * header_score) + (0.40 * value_score)
        elif header_score > 0:
            composite = header_score
        elif value_score > 0:
            # Unmistakable structured data types can match by value pattern alone
            if field_type in ('phone', 'email', 'date', 'year'):
                composite = round(value_score * 0.85, 3)
            elif field_type in ('entity_branch', 'entity_product', 'choice_gender', 'choice_mode'):
                composite = round(value_score * 0.70, 3)
            else:
                # Generic text fields (name, notes, degree, location) CANNOT match by value alone without header cues
                composite = 0.25
        else:
            composite = 0.0

        composite = min(1.0, round(composite, 3))

        if composite >= 0.30:
            candidates.append({
                'field': field_name,
                'label': field_def['label'],
                'confidence': composite,
                'reasons': reasons
            })

    # Sort candidates by confidence descending
    candidates.sort(key=lambda x: x['confidence'], reverse=True)

    if candidates and candidates[0]['confidence'] >= 0.50:
        top = candidates[0]
        field_match = top['field']
        score = top['confidence']
        reasons = top['reasons']
        tier = 'HIGH' if score >= 0.85 else 'MEDIUM'
        alternatives = candidates[1:4]
    else:
        field_match = None
        score = candidates[0]['confidence'] if candidates else 0.0
        reasons = ['No confident CRM field correspondence identified; preserved as custom form data']
        tier = 'LOW'
        alternatives = candidates[:3]

    return ColumnMatchResult(
        header=header,
        crm_field=field_match,
        confidence=score,
        tier=tier,
        reasons=reasons,
        alternatives=alternatives,
        sample_values=sample_preview
    )


# ==============================================================================
# MULTI-COLUMN MATCHING & CONFLICT RESOLUTION
# ==============================================================================

def match_all_columns(
    headers: List[str],
    sample_rows: List[Dict[str, Any]],
    active_entities: Optional[Dict[str, List[str]]] = None,
    existing_mapping: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Intelligently maps an entire spreadsheet's headers against the CRM inventory.
    Resolves column-to-field collisions (e.g. primary vs alternate phone, first/last vs full name).
    Returns comprehensive mapping proposal, confidence tiers, and unmapped fields.
    """
    # Extract sample column values
    col_samples: Dict[str, List[Any]] = {h: [] for h in headers}
    for r in sample_rows[:50]:
        for h in headers:
            v = r.get(h)
            if v is not None and str(v).strip():
                col_samples[h].append(str(v).strip())

    initial_matches: Dict[str, ColumnMatchResult] = {}
    for h in headers:
        initial_matches[h] = match_column(
            header=h,
            sample_values=col_samples.get(h, []),
            active_entities=active_entities,
            confirmed_memory=existing_mapping
        )

    # Conflict Resolution: Ensure 1-to-1 mapping for CRM fields unless distinct roles exist
    field_to_headers: Dict[str, List[Tuple[str, float]]] = {}
    for h, res in initial_matches.items():
        if res.crm_field:
            field_to_headers.setdefault(res.crm_field, []).append((h, res.confidence))

    for crm_field, col_list in list(field_to_headers.items()):
        if len(col_list) > 1:
            sorted_cols = sorted(col_list, key=lambda x: x[1], reverse=True)
            winner_h = sorted_cols[0][0]

            for runner_up_h, _ in sorted_cols[1:]:
                # Special disambiguation for phone -> alternate_phone
                if crm_field == 'phone' and 'alternate_phone' not in field_to_headers:
                    initial_matches[runner_up_h].crm_field = 'alternate_phone'
                    initial_matches[runner_up_h].tier = 'MEDIUM'
                    initial_matches[runner_up_h].reasons.append("Disambiguated to Alternate Phone (secondary phone column)")
                    field_to_headers['alternate_phone'] = [(runner_up_h, initial_matches[runner_up_h].confidence)]
                else:
                    initial_matches[runner_up_h].crm_field = None
                    initial_matches[runner_up_h].tier = 'LOW'
                    initial_matches[runner_up_h].reasons.append(
                        f"Field '{crm_field}' assigned to '{winner_h}' with higher confidence"
                    )

    # Final summary collections
    confirmed_field_map: Dict[str, str] = {}
    detailed_columns: Dict[str, Any] = {}
    unmapped_headers: List[str] = []

    for h in headers:
        res = initial_matches[h]
        detailed_columns[h] = res.to_dict()
        if res.crm_field:
            confirmed_field_map[res.crm_field] = h
        else:
            unmapped_headers.append(h)

    # Check for recommended critical fields
    missing_critical: List[str] = []
    if 'phone' not in confirmed_field_map and 'email' not in confirmed_field_map:
        missing_critical.append('phone')
        missing_critical.append('email')

    return {
        'column_mappings': detailed_columns,
        'field_to_header': confirmed_field_map,
        'unmapped_headers': unmapped_headers,
        'missing_critical_fields': missing_critical,
        'total_columns': len(headers),
        'high_confidence_count': sum(1 for r in initial_matches.values() if r.tier == 'HIGH'),
        'medium_confidence_count': sum(1 for r in initial_matches.values() if r.tier == 'MEDIUM'),
        'low_confidence_count': sum(1 for r in initial_matches.values() if r.tier == 'LOW'),
    }


def get_active_crm_entities() -> Dict[str, List[str]]:
    """
    Safely retrieves list of active branch names, product names, and counselor usernames
    from the CRM database for value pattern matching.
    """
    try:
        from branches.models import Branch
        from products.models import Product
        from django.contrib.auth import get_user_model

        User = get_user_model()
        branches = list(Branch.objects.filter(status='Active').values_list('name', flat=True)[:100])
        products = list(Product.objects.filter(status='Active').values_list('name', flat=True)[:100])
        users = list(User.objects.filter(is_active=True).values_list('username', flat=True)[:100])
        return {
            'branches': branches,
            'products': products,
            'users': users
        }
    except Exception:
        return {'branches': [], 'products': [], 'users': []}
