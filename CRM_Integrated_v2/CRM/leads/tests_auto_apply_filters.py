from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from accounts.models import User, UserRole
from branches.models import Branch
from products.models import Product
from lead_channels.models import Channel
from leads.models import Lead, LeadStatus, LeadCategory


class AutoApplyFiltersTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin_autofilter",
            password="Password123!",
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True
        )

        self.branch_anna, _ = Branch.objects.get_or_create(name="Anna Nagar Auto", defaults={'status': "Active"})
        self.branch_vela, _ = Branch.objects.get_or_create(name="Velachery Auto", defaults={'status': "Active"})

        self.tc_anna = User.objects.create_user(
            username="tc_anna",
            password="Password123!",
            role=UserRole.TELECALLER,
            branch=self.branch_anna,
            first_name="Kavitha",
            last_name="R"
        )
        self.tc_vela = User.objects.create_user(
            username="tc_vela",
            password="Password123!",
            role=UserRole.TELECALLER,
            branch=self.branch_vela,
            first_name="Praveen",
            last_name="S"
        )

        self.counselor_anna = User.objects.create_user(
            username="counselor_anna",
            password="Password123!",
            role=UserRole.COUNSELOR,
            branch=self.branch_anna,
            first_name="Deepa",
            last_name="M"
        )

        self.product = Product.objects.create(name="Full Stack Python", price=25000)
        self.channel = Channel.objects.create(name="Google Ads", status="Active")

        now = timezone.now()
        # Lead 1: Anna Nagar, tc_anna, counselor_anna, NEW, TRAINING, Google Ads
        self.lead1 = Lead.objects.create(
            name="Alice Smith",
            phone="9876543210",
            email="alice@example.com",
            status=LeadStatus.NEW,
            category=LeadCategory.TRAINING,
            branch=self.branch_anna,
            assigned_telecaller=self.tc_anna,
            assigned_counselor=self.counselor_anna,
            product=self.product,
            channel=self.channel,
            source="Google Search"
        )
        # Lead 2: Velachery, tc_vela, PROSPECTED, PLACEMENT
        self.lead2 = Lead.objects.create(
            name="Bob Jones",
            phone="9876543211",
            email="bob@example.com",
            status=LeadStatus.CONTACTED,
            category=LeadCategory.PLACEMENT,
            branch=self.branch_vela,
            assigned_telecaller=self.tc_vela,
            product=self.product,
            channel=self.channel,
            source="Walk-in"
        )

        self.client.force_login(self.admin)

    def test_no_apply_or_filter_submit_button_in_rendered_page(self):
        """Verify that the leads list page does NOT render an 'Apply' or 'Apply Filters' button in the filter form."""
        response = self.client.get(reverse('admin_leads_list'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Check filter form specifically
        self.assertIn('class="filter-form"', content)
        # Verify no submit button with Apply
        self.assertNotIn('<button type="submit" class="btn btn-primary" style="font-weight: 600;">Apply</button>', content)
        self.assertNotIn('Apply Filter</button>', content)

        # Reset button should be preserved
        self.assertIn('Reset</a>', content)

    def test_auto_filter_script_loaded(self):
        """Verify that auto-filter.js is loaded in the page."""
        response = self.client.get(reverse('admin_leads_list'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('auto-filter.js', content)

    def test_telecaller_and_counselor_have_data_branch_attributes(self):
        """Verify that telecaller and counselor options have data-branch attributes for client-side syncing."""
        response = self.client.get(reverse('admin_leads_list'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn(f'data-branch="{self.branch_anna.id}"', content)
        self.assertIn(f'data-branch="{self.branch_vela.id}"', content)

    def test_filter_by_branch(self):
        """Selecting branch returns only matching leads."""
        response = self.client.get(reverse('admin_leads_list'), {'branch': str(self.branch_anna.id)})
        self.assertEqual(response.status_code, 200)
        leads = list(response.context['page_obj'])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].id, self.lead1.id)

    def test_filter_by_telecaller(self):
        """Selecting telecaller returns only matching leads."""
        response = self.client.get(reverse('admin_leads_list'), {'telecaller': str(self.tc_vela.id)})
        self.assertEqual(response.status_code, 200)
        leads = list(response.context['page_obj'])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].id, self.lead2.id)

    def test_filter_by_counselor(self):
        """Selecting counselor returns only matching leads."""
        response = self.client.get(reverse('admin_leads_list'), {'counselor': str(self.counselor_anna.id)})
        self.assertEqual(response.status_code, 200)
        leads = list(response.context['page_obj'])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].id, self.lead1.id)

    def test_filter_by_status(self):
        """Selecting status returns only matching leads."""
        response = self.client.get(reverse('admin_leads_list'), {'status': LeadStatus.CONTACTED})
        self.assertEqual(response.status_code, 200)
        leads = list(response.context['page_obj'])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].id, self.lead2.id)

    def test_filter_by_category(self):
        """Selecting category returns only matching leads."""
        response = self.client.get(reverse('admin_leads_list'), {'category': LeadCategory.TRAINING})
        self.assertEqual(response.status_code, 200)
        leads = list(response.context['page_obj'])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].id, self.lead1.id)

    def test_filter_by_search(self):
        """Searching text returns matching leads."""
        response = self.client.get(reverse('admin_leads_list'), {'search': 'Alice'})
        self.assertEqual(response.status_code, 200)
        leads = list(response.context['page_obj'])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].id, self.lead1.id)

    def test_multiple_filters_work_together(self):
        """Multiple combined filters return matching intersection."""
        response = self.client.get(reverse('admin_leads_list'), {
            'branch': str(self.branch_anna.id),
            'status': LeadStatus.NEW,
            'category': LeadCategory.TRAINING,
            'telecaller': str(self.tc_anna.id)
        })
        self.assertEqual(response.status_code, 200)
        leads = list(response.context['page_obj'])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].id, self.lead1.id)

        # Incompatible filter combination should yield 0 results
        response2 = self.client.get(reverse('admin_leads_list'), {
            'branch': str(self.branch_anna.id),
            'status': LeadStatus.CONTACTED
        })
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(len(list(response2.context['page_obj'])), 0)

    def test_selected_filters_remain_visible_in_html(self):
        """Selected values are rendered with 'selected' in the DOM after filtering."""
        response = self.client.get(reverse('admin_leads_list'), {
            'branch': str(self.branch_anna.id),
            'status': LeadStatus.NEW
        })
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Check option selected for branch
        self.assertIn(f'value="{self.branch_anna.id}" selected', content)
        # Check option selected for status
        self.assertIn(f'value="{LeadStatus.NEW}" selected', content)

    def test_sorting_and_pagination_preserved(self):
        """Sorting parameter is passed and preserved in hidden form input."""
        response = self.client.get(reverse('admin_leads_list'), {'sort': 'name'})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('<input type="hidden" name="sort" value="name">', content)

    def test_clearing_filters_restores_default_results(self):
        """Clearing query parameters restores full list of results."""
        response = self.client.get(reverse('admin_leads_list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(list(response.context['page_obj'])), 2)

    def test_new_leads_and_status_leads_have_no_filter_button(self):
        """Verify dedicated new_leads and status_leads pages also have no submit buttons in their filter forms."""
        response_new = self.client.get(reverse('admin_new_leads'))
        self.assertEqual(response_new.status_code, 200)
        content_new = response_new.content.decode('utf-8')
        filter_form_part = content_new.split('class="filter-form"')[1].split('</form>')[0]
        self.assertNotIn('<button type="submit"', filter_form_part)
        self.assertIn('auto-filter.js', content_new)

        response_status = self.client.get(reverse('admin_interested_leads'))
        self.assertEqual(response_status.status_code, 200)
        content_status = response_status.content.decode('utf-8')
        filter_form_status = content_status.split('class="filter-form"')[1].split('</form>')[0]
        self.assertNotIn('<button type="submit"', filter_form_status)
        self.assertIn('auto-filter.js', content_status)
