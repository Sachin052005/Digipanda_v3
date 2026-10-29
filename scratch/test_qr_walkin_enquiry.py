import os
import sys
import django

sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client
from django.urls import reverse
from django.db import transaction
from branches.models import Branch
from lead_channels.models import Channel
from leads.models import Lead, VisitorStatus

def run_tests():
    print("Running Walk-in QR Code Enquiry Verification Tests...")
    client = Client()

    with transaction.atomic():
        # Setup branch
        branch, _ = Branch.objects.get_or_create(name='Velachery Test', defaults={'status': 'Active', 'phone': '9876543210'})
        walkin_channel, _ = Channel.objects.get_or_create(name='Walk-in', defaults={'status': 'Active'})

        # 1. Test GET /enquiry/
        url_get = reverse('public_student_enquiry_branch', kwargs={'branch_id': branch.id})
        res_get = client.get(url_get)
        assert res_get.status_code == 200, f"Expected 200, got {res_get.status_code}"
        assert "Student Enquiry Form" in res_get.content.decode('utf-8'), "Title not in page"
        print("PASS: GET /enquiry/ returns 200 with student enquiry form")

        # 2. Test POST /enquiry/
        post_data = {
            'name': 'Karthik Subramanian',
            'phone': '9840123456',
            'email': 'karthik@example.com',
            'branch_id': branch.id,
            'dob': '2001-05-15',
            'gender': 'Male',
            'address': 'Flat 4B, Lotus Apartments',
            'city': 'Chennai',
            'state': 'Tamil Nadu',
            'zip_code': '600042',
            'preferred_contact': 'WhatsApp',
            'experience_type': 'Fresher',
            'ug_degree': 'B.Com',
            'ug_year': '2024',
            'backlogs': 'No',
            'highest_education': 'B.Com',
            'professional_status': 'Student / Fresher',
            'career_objective': 'Get a Job in Digital Marketing',
            'dm_experience': 'Beginner',
            'course_track': 'Premium',
            'ref_1_name': 'Suresh',
            'ref_1_phone': '9840999999',
        }
        res_post = client.post(url_get, post_data)
        assert res_post.status_code == 200, f"Expected 200 on post, got {res_post.status_code}"
        html_out = res_post.content.decode('utf-8')
        assert "Welcome, Karthik Subramanian!" in html_out, "Welcome greeting not in output"
        assert "WI-VEL-" in html_out, "Token number not in output"
        print("PASS: POST /enquiry/ creates walkin lead and displays consultation token")

        # Check DB
        lead = Lead.objects.filter(phone='9840123456').first()
        assert lead is not None, "Lead was not saved to database"
        assert lead.name == 'Karthik Subramanian'
        assert lead.channel.name == 'Walk-in'
        assert lead.source == 'Walk-in QR Form'
        assert lead.visitor_status == VisitorStatus.WAITING
        assert lead.is_offline is True
        assert lead.token_number.startswith('WI-VEL-')
        assert lead.custom_fields.get('ug_degree') == 'B.Com'
        assert lead.custom_fields.get('course_track') == 'Premium'
        print(f"PASS: Lead created in DB with ID #{lead.id}, Token: {lead.token_number}, Custom fields saved properly")

        # 3. Test QR Standee View
        from accounts.models import User, UserRole
        admin_user = User.objects.filter(role=UserRole.ADMIN).first()
        if admin_user:
            client.force_login(admin_user)
            standee_url = reverse('branch_qr_standee', kwargs={'branch_id': branch.id})
            res_qr = client.get(standee_url)
            assert res_qr.status_code == 200
            assert "Reception Desk Standee" in res_qr.content.decode('utf-8')
            assert "data:image/png;base64," in res_qr.content.decode('utf-8')
            print("PASS: Branch QR Standee generated high-resolution QR code successfully")

        # Rollback test data
        transaction.set_rollback(True)
        print("All tests passed! Rolled back transaction cleanly.")

if __name__ == '__main__':
    run_tests()
