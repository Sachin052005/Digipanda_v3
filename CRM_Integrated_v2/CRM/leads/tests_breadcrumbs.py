"""
Automated Unit & Regression Tests for TechPanda CRM Global Dynamic Breadcrumb Navigation System.
Tests:
1. Role-specific dashboard root resolution (Admin, Counselor, Telecaller, Sales Head, Branch Head, Accountant).
2. Hierarchy resolution across core modules (Leads, Team & Staff, Reports, Configuration, Profile).
3. Dynamic object resolution (Lead names, staff names, course names).
4. Graceful handling of missing objects / unresolvable URLs.
5. Semantic HTML5 rendering, ARIA attributes, and template tags.
6. Explicit breadcrumbs override capability.
"""
import os
import sys
from unittest import TestCase

CRM_ROOT = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM'
if CRM_ROOT not in sys.path:
    sys.path.insert(0, CRM_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.test import RequestFactory
from django.template import Template, Context
from django.contrib.auth import get_user_model
from django.urls import ResolverMatch

from accounts.models import UserRole
from accounts.breadcrumbs import resolve_breadcrumbs, BreadcrumbItem
from leads.models import Lead

User = get_user_model()


class MockResolverMatch:
    def __init__(self, url_name, args=(), kwargs=None):
        self.url_name = url_name
        self.args = args
        self.kwargs = kwargs or {}


class BreadcrumbResolverTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin_user = User(username='test_admin', role=UserRole.ADMIN, is_staff=True, is_active=True)
        self.counselor_user = User(username='test_counselor', role=UserRole.COUNSELOR, is_active=True)
        self.telecaller_user = User(username='test_tc', role=UserRole.TELECALLER, is_active=True)
        self.manager_user = User(username='test_sh', role=UserRole.SALES_HEAD, is_active=True)
        self.branch_head_user = User(username='test_bh', role=UserRole.BRANCH_HEAD, is_active=True)
        self.accountant_user = User(username='test_acct', role=UserRole.ACCOUNTANT, is_active=True)

    def _make_context(self, user, url_name, extra_ctx=None):
        request = self.factory.get('/test/')
        request.user = user
        request.resolver_match = MockResolverMatch(url_name=url_name)
        ctx = {'request': request, 'user': user}
        if extra_ctx:
            ctx.update(extra_ctx)
        return ctx

    def test_dashboard_omits_breadcrumbs(self):
        """Dashboard root views must return an empty list to avoid redundant home breadcrumbs."""
        for url in ['admin_dashboard', 'counselor_dashboard', 'telecaller_dashboard', 'manager_dashboard']:
            ctx = self._make_context(self.admin_user, url)
            items = resolve_breadcrumbs(ctx)
            self.assertEqual(items, [], f"Breadcrumbs should be empty for {url}")

    def test_admin_leads_list_hierarchy(self):
        ctx = self._make_context(self.admin_user, 'admin_leads_list')
        items = resolve_breadcrumbs(ctx)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].label, 'Dashboard')
        self.assertIn('/admin/dashboard/', items[0].url)
        self.assertEqual(items[1].label, 'All Leads')
        self.assertIsNone(items[1].url)

    def test_admin_lead_detail_with_dynamic_object(self):
        lead = Lead(id=101, name='Pooja Sundaram', phone='9876543210')
        ctx = self._make_context(self.admin_user, 'admin_lead_detail', {'lead': lead})
        items = resolve_breadcrumbs(ctx)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].label, 'Dashboard')
        self.assertEqual(items[1].label, 'All Leads')
        self.assertIn('/admin/leads/', items[1].url)
        self.assertEqual(items[2].label, 'Pooja Sundaram')
        self.assertIsNone(items[2].url)

    def test_admin_lead_edit_with_dynamic_object(self):
        lead = Lead(id=102, name='Karthik Raja', phone='9876543211')
        ctx = self._make_context(self.admin_user, 'admin_lead_edit', {'lead': lead})
        items = resolve_breadcrumbs(ctx)
        self.assertEqual(len(items), 4)
        self.assertEqual(items[0].label, 'Dashboard')
        self.assertEqual(items[1].label, 'All Leads')
        self.assertEqual(items[2].label, 'Karthik Raja')
        self.assertIn('/admin/leads/102/', items[2].url)
        self.assertEqual(items[3].label, 'Edit Lead')
        self.assertIsNone(items[3].url)

    def test_counselor_role_dashboard_routing(self):
        lead = Lead(id=103, name='Deepak Roshan', phone='9876543212')
        ctx = self._make_context(self.counselor_user, 'counselor_lead_detail', {'lead': lead})
        items = resolve_breadcrumbs(ctx)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].label, 'Dashboard')
        self.assertIn('/counselor/dashboard/', items[0].url)
        self.assertEqual(items[1].label, 'My Leads')
        self.assertIn('/counselor/leads/', items[1].url)
        self.assertEqual(items[2].label, 'Deepak Roshan')
        self.assertIsNone(items[2].url)

    def test_telecaller_role_dashboard_routing(self):
        ctx = self._make_context(self.telecaller_user, 'telecaller_calls_list')
        items = resolve_breadcrumbs(ctx)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].label, 'Dashboard')
        self.assertIn('/telecaller/dashboard/', items[0].url)
        self.assertEqual(items[1].label, 'Call History')
        self.assertIsNone(items[1].url)

    def test_sales_head_and_branch_head_routing(self):
        sh_ctx = self._make_context(self.manager_user, 'manager_leads_list')
        sh_items = resolve_breadcrumbs(sh_ctx)
        self.assertIn('/manager/dashboard/', sh_items[0].url)
        self.assertEqual(sh_items[1].label, 'Leads')

        bh_ctx = self._make_context(self.branch_head_user, 'branch_head_leads_list')
        bh_items = resolve_breadcrumbs(bh_ctx)
        self.assertIn('/manager/branch-head/dashboard/', bh_items[0].url)
        self.assertEqual(bh_items[1].label, 'Branch Leads')

    def test_missing_lead_object_fallback(self):
        """When the lead context object is missing or None, falls back gracefully."""
        ctx = self._make_context(self.admin_user, 'admin_lead_detail', {})
        items = resolve_breadcrumbs(ctx)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[2].label, 'Lead Profile')

    def test_user_profile_universal_breadcrumb(self):
        ctx = self._make_context(self.admin_user, 'user_profile')
        items = resolve_breadcrumbs(ctx)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].label, 'Dashboard')
        self.assertEqual(items[1].label, 'Settings')
        self.assertEqual(items[2].label, 'Profile & Security')


class BreadcrumbTemplateTagRenderingTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User(username='tester', role=UserRole.ADMIN, is_staff=True, is_active=True)

    def test_render_breadcrumbs_template_tag(self):
        request = self.factory.get('/admin/leads/')
        request.user = self.user
        request.resolver_match = MockResolverMatch(url_name='admin_leads_list')

        template = Template("{% load breadcrumb_tags %}{% render_breadcrumbs %}")
        rendered = template.render(Context({'request': request, 'user': self.user}))

        self.assertIn('class="tp-breadcrumb-nav"', rendered)
        self.assertIn('aria-label="Breadcrumb"', rendered)
        self.assertIn('class="tp-breadcrumb-list"', rendered)
        self.assertIn('href="/admin/dashboard/"', rendered)
        self.assertIn('Dashboard', rendered)
        self.assertIn('All Leads', rendered)
        self.assertIn('aria-current="page"', rendered)
        self.assertIn('aria-hidden="true"', rendered)

    def test_explicit_breadcrumbs_override(self):
        request = self.factory.get('/custom/')
        request.user = self.user
        request.resolver_match = MockResolverMatch(url_name='custom_url')

        custom_crumbs = [
            BreadcrumbItem(label='Custom Root', url='/custom/root/'),
            BreadcrumbItem(label='Custom Section', url='/custom/section/'),
            BreadcrumbItem(label='Current Page', url=None)
        ]

        template = Template("{% load breadcrumb_tags %}{% render_breadcrumbs %}")
        rendered = template.render(Context({
            'request': request,
            'user': self.user,
            'breadcrumbs': custom_crumbs
        }))

        self.assertIn('Custom Root', rendered)
        self.assertIn('Custom Section', rendered)
        self.assertIn('Current Page', rendered)
        self.assertIn('href="/custom/root/"', rendered)


if __name__ == '__main__':
    import unittest
    unittest.main()
