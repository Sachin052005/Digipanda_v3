import os
import sys

# Add CRM directory to sys.path
crm_path = r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM'
if crm_path not in sys.path:
    sys.path.insert(0, crm_path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

import django
from django.conf import settings

# Override DATABASES to use in-memory sqlite for clean sandboxed tests
settings.DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

django.setup()

from django.core.management import call_command
call_command('migrate')
call_command('test', 'leads.tests_qualification_autofill', verbosity=2)
