import os
import sys
import django

sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from accounts.models import User

users_without_email = User.objects.filter(email="").all()
print(f"Backfilling {users_without_email.count()} users with missing email...")

for u in users_without_email:
    clean_username = u.username.lower().replace("@", "_").replace(" ", "_")
    generated_email = f"{clean_username}@digipanda.internal"
    # Ensure uniqueness
    counter = 1
    base_email = generated_email
    while User.objects.filter(email__iexact=generated_email).exclude(id=u.id).exists():
        generated_email = f"{clean_username}_{counter}@digipanda.internal"
        counter += 1
    u.email = generated_email
    u.save(update_fields=["email"])
    print(f"Updated User {u.id} ({u.username}) -> email: {u.email}")

print("All users now have email addresses!")
