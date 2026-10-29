import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env
load_dotenv(BASE_DIR / '.env')

# Security settings
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-techpanda-crm-default-key-change-in-prod')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', '*').split(',') if h.strip()]
# Browser logins/forms over https through ngrok or the live domain (comma-separated, with https://)
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv(
    'CSRF_TRUSTED_ORIGINS', 'https://*.ngrok-free.app,https://*.ngrok.app,https://digipandacrm.in,https://www.digipandacrm.in,https://crm.techpanda.academy'
).split(',') if o.strip()]
if 'https://digipandacrm.in' not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.extend(['https://digipandacrm.in', 'https://www.digipandacrm.in'])

# Application definition
INSTALLED_APPS = [
    # Daphne first: `runserver` then serves both normal pages and the WhatsApp inbox WebSockets.
    # (The Django Channels library itself is NOT listed: its app label 'channels' is used by the
    # CRM's own lead_channels app. Channels' layers/consumers work without being installed as an app.)
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',

    # Third-party: REST API + login tokens for the CRM Call Sync Android app
    'rest_framework',
    'rest_framework.authtoken',
    
    # DIGIPANDA CRM Core Apps
    'accounts.apps.AccountsConfig',
    'branches.apps.BranchesConfig',
    'lead_channels.apps.ChannelsConfig',
    'products.apps.ProductsConfig',
    'leads.apps.LeadsConfig',
    'managers.apps.ManagersConfig',
    'branch_heads.apps.BranchHeadsConfig',
    'counselors.apps.CounselorsConfig',
    'telecallers.apps.TelecallersConfig',
    'followups.apps.FollowupsConfig',
    'calls.apps.CallsConfig',
    'activities.apps.ActivitiesConfig',
    'reports.apps.ReportsConfig',
    'drive.apps.DriveConfig',

    # WhatsApp inbox + no-code automation (WhatsApp leads) and Facebook Lead Ads (Facebook leads)
    'chat.apps.ChatConfig',
    'fb_leads.apps.FbLeadsConfig',
    'finance.apps.FinanceConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.DeviceTimezoneMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.crm_context',
            ],
            'libraries': {
                'breadcrumb_tags': 'accounts.templatetags.breadcrumb_tags',
            },
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# WhatsApp inbox live updates (Django Channels). In-memory works for one server process.
# For several worker processes in production, install channels-redis and use Redis instead:
# CHANNEL_LAYERS = {'default': {'BACKEND': 'channels_redis.core.RedisChannelLayer',
#                               'CONFIG': {'hosts': [(os.getenv('REDIS_HOST', '127.0.0.1'), 6379)]}}}
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# Database configuration (MySQL CRM database loaded securely from environment)
DB_ENGINE = os.getenv('DB_ENGINE', 'django.db.backends.mysql')
DB_NAME = os.getenv('DB_NAME', 'tech')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_PORT = os.getenv('DB_PORT', '3306')

if DB_ENGINE == 'django.db.backends.sqlite3' or (not DB_PASSWORD and not os.getenv('DB_NAME')):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': DB_NAME,
            'USER': DB_USER,
            'PASSWORD': DB_PASSWORD,
            'HOST': DB_HOST,
            'PORT': DB_PORT,
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Authentication Backends (Email-based primary login)
AUTHENTICATION_BACKENDS = [
    'accounts.backends.EmailAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Authentication URLs
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'login_redirect'
LOGOUT_REDIRECT_URL = 'login'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    {
        'NAME': 'accounts.validators.ComplexityValidator',
        'OPTIONS': {'min_length': 8},
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.getenv('TIME_ZONE', 'Asia/Kolkata')
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# CRM Call Sync (Android app): Google Ads calls + call recordings.
# App recordings are stored OUTSIDE MEDIA_ROOT and only streamed to permitted users through
# /drive/stream/<id>/ (role-based checks). Keep private_media/ out of web-server aliases and git.
CALLS = {
    'PRIVATE_MEDIA_ROOT': Path(os.getenv('PRIVATE_MEDIA_ROOT', BASE_DIR / 'private_media')),
    'MAX_RECORDING_MB': 50,
    'CALLBACK_WITHIN_MINUTES': 15,      # missed Google call -> follow-up due this soon
    'MATCH_WINDOW_SECONDS': 600,        # recording <-> call matching tolerance
    'GOOGLE_CALL_SOURCE': 'Google Call',
    'APP_LOGIN_ROLES': (
        'SUPERADMIN',
        'ADMIN',
        'SALES_HEAD',
        'BRANCH_HEAD',
        'BRANCH_ADMIN',
        'COUNSELOR',
        'TELECALLER',
        'RECEPTIONIST',
        'ACCOUNTANT',
    ),
    'ON_MISSED_CALL': None,             # optional dotted path to function(call_event)
}
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # bigger recordings stream to a temp file
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    # Session = logged-in CRM users (WhatsApp inbox / flow builder); Token = Call Sync app
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S%z',
}

# ---------------------------------------------------------------------------
# WhatsApp Cloud API (Meta). Per-number tokens can also be saved on each Business Account.
# ---------------------------------------------------------------------------
WHATSAPP_ACCESS_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN', '')
WHATSAPP_APP_SECRET = os.getenv('WHATSAPP_APP_SECRET', os.getenv('FB_APP_SECRET', ''))
WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv('WHATSAPP_BUSINESS_ACCOUNT_ID', '')
WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', '')
WHATSAPP_API_VERSION = os.getenv('WHATSAPP_API_VERSION', 'v20.0')
# CRM branch for new WhatsApp leads when the WhatsApp number has no branch set (exact branch name)
WHATSAPP_DEFAULT_BRANCH = os.getenv('WHATSAPP_DEFAULT_BRANCH', '')
MAX_UPLOAD_SIZE = 16 * 1024 * 1024  # 16 MB max WhatsApp media upload
ALLOWED_MEDIA_TYPES = [
    'image/jpeg', 'image/png', 'image/webp', 'application/pdf', 'audio/mpeg', 'audio/ogg', 'video/mp4',
]

# ---------------------------------------------------------------------------
# Facebook Lead Ads (fb_leads). Values come from .env, never commit them.
# ---------------------------------------------------------------------------
FB_VERIFY_TOKEN = os.getenv('FB_VERIFY_TOKEN', '')
FB_APP_SECRET = os.getenv('FB_APP_SECRET', '')
FB_PAGE_TOKEN = os.getenv('FB_PAGE_TOKEN', '')
FB_PAGE_ID = os.getenv('FB_PAGE_ID', '')
FB_GRAPH_VERSION = os.getenv('FB_GRAPH_VERSION', 'v23.0')
# CRM branch for new Facebook leads when the form has no branch question (exact branch name)
FB_DEFAULT_BRANCH = os.getenv('FB_DEFAULT_BRANCH', '')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Logging configuration
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'crm.log',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'crm': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Email Configuration (Environment Configurable with Gmail SMTP defaults)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
EMAIL_USE_SSL = False
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', 'admin@digipandaacademy.com')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', '20'))

# CRM Public Application URL & Branding for Email Invitations
CRM_BASE_URL = os.getenv('CRM_BASE_URL', 'http://127.0.0.1:8000')
COMPANY_NAME = os.getenv('COMPANY_NAME', 'DIGIPANDA')
PASSWORD_RESET_TIMEOUT = int(os.getenv('PASSWORD_RESET_TIMEOUT', '86400'))  # 24 Hours Single-Use Expiration

# Google Sheets & OAuth 2.0 Desktop Configuration
GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID', '').strip()
GOOGLE_SHEET_TAB = os.getenv('GOOGLE_SHEET_TAB', 'Form Responses 1').strip()
GOOGLE_OAUTH_CREDENTIALS_PATH = Path(
    os.getenv('GOOGLE_OAUTH_CREDENTIALS_PATH', str(BASE_DIR / 'credentials' / 'credentials.json'))
)
GOOGLE_OAUTH_TOKEN_PATH = Path(
    os.getenv('GOOGLE_OAUTH_TOKEN_PATH', str(BASE_DIR / 'credentials' / 'token.json'))
)
GOOGLE_OAUTH_SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.metadata.readonly',
]
GOOGLE_SERVICE_ACCOUNT_PATH = Path(
    os.getenv('GOOGLE_SERVICE_ACCOUNT_PATH', str(BASE_DIR / 'credentials' / 'service_account.json'))
)
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '').strip()

# GST & Tax Configuration
DEFAULT_GST_RATE = os.getenv('DEFAULT_GST_RATE', '18.00')
