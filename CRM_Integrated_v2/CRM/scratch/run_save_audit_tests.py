import sys
import os
import unittest

sys.path.insert(0, r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from leads.tests_save_audit import SaveActionAuditTests

suite = unittest.TestLoader().loadTestsFromTestCase(SaveActionAuditTests)
runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

if result.wasSuccessful():
    print("\nALL SAVE ACTION TESTS PASSED PERFECTLY!")
    sys.exit(0)
else:
    print("\nSOME TESTS FAILED!")
    sys.exit(1)
