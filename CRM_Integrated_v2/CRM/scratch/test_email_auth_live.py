import os
import sys
import django

sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import authenticate
from django.test import Client
from accounts.models import User, UserRole

print("=== TESTING EMAIL AUTHENTICATION ===")
# Find or create a verified test user
test_email = "authtest_live@digipanda.com"
user = User.objects.filter(email=test_email).first()
if not user:
    user = User.objects.create_user(
        username="authtest_live",
        email=test_email,
        password="ValidPassword123!",
        role=UserRole.ADMIN
    )
else:
    user.set_password("ValidPassword123!")
    user.is_active = True
    user.save()

# Test 1: Authenticate with username kwarg containing email
u1 = authenticate(username=test_email, password="ValidPassword123!")
assert u1 is not None and u1.email == test_email, f"Failed username=email auth: {u1}"
print("Test 1 Passed: Authenticate with username=email")

# Test 2: Authenticate with email kwarg
u2 = authenticate(email=test_email, password="ValidPassword123!")
assert u2 is not None and u2.email == test_email, f"Failed email=email auth: {u2}"
print("Test 2 Passed: Authenticate with email=email")

# Test 3: Case-insensitive email authentication
u3 = authenticate(username="AuThTeSt_LiVe@DiGiPaNdA.CoM", password="ValidPassword123!")
assert u3 is not None and u3.email == test_email, f"Failed case-insensitive auth: {u3}"
print("Test 3 Passed: Authenticate case-insensitive email")

# Test 4: Invalid password returns None
u4 = authenticate(username=test_email, password="WrongPassword999!")
assert u4 is None, f"Failed: Invalid password authenticated unexpectedly"
print("Test 4 Passed: Invalid password rejected")

# Test 5: Inactive user
user.is_active = False
user.save()
u5 = authenticate(username=test_email, password="ValidPassword123!")
assert u5 is None, f"Failed: Inactive user authenticated unexpectedly"
user.is_active = True
user.save()
print("Test 5 Passed: Inactive user rejected")

# Test 6: HTTP Client POST to /login/ with 'email'
c = Client()
resp = c.post("/login/", {
    "email": test_email,
    "password": "ValidPassword123!"
}, follow=False)
print(f"Login POST status code: {resp.status_code}, redirect url: {resp.get('Location', '')}")
assert resp.status_code == 302, f"Expected 302 redirect from /login/, got {resp.status_code}"

# Test 7: HTTP Client POST with legacy 'username' param
resp2 = c.post("/login/", {
    "username": test_email,
    "password": "ValidPassword123!"
}, follow=False)
print(f"Legacy username POST status code: {resp2.status_code}, redirect url: {resp2.get('Location', '')}")
assert resp2.status_code == 302, f"Expected 302 redirect for legacy param, got {resp2.status_code}"

print("\nALL 7 EMAIL AUTHENTICATION TESTS PASSED PERFECTLY!")
