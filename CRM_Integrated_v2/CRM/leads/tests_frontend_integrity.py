import os
import sys
from datetime import date, timedelta
from unittest import TestCase
from html.parser import HTMLParser

CRM_ROOT = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM'
if CRM_ROOT not in sys.path:
    sys.path.insert(0, CRM_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.test import RequestFactory
from django.template.loader import render_to_string, get_template
from django.core.paginator import Paginator
from django.utils import timezone

from leads.utils_date_filter import extract_normalized_date_range, parse_iso_date
from leads.templatetags.kpi_tags import build_kpi_url


class SimpleHTMLNode:
    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag.lower()
        self.attrs = dict(attrs) if attrs else {}
        self.parent = parent
        self.children = []
        self.text = ""

    def find(self, tag=None, id=None):
        for child in self.children:
            match_tag = (tag is None or child.tag == tag.lower())
            match_id = (id is None or child.attrs.get('id') == id)
            if match_tag and match_id:
                return child
            res = child.find(tag=tag, id=id)
            if res:
                return res
        return None

    def find_all(self, tag=None, role=None):
        results = []
        for child in self.children:
            match_tag = (tag is None or child.tag == tag.lower())
            match_role = (role is None or child.attrs.get('role') == role)
            if match_tag and match_role:
                results.append(child)
            results.extend(child.find_all(tag=tag, role=role))
        return results

    def get_text(self):
        txt = self.text
        for c in self.children:
            txt += " " + c.get_text()
        return txt.strip()


class TreeHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = SimpleHTMLNode('document')
        self.current = self.root
        self.void_tags = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def handle_starttag(self, tag, attrs):
        node = SimpleHTMLNode(tag, attrs, parent=self.current)
        self.current.children.append(node)
        if tag.lower() not in self.void_tags:
            self.current = node

    def handle_endtag(self, tag):
        if tag.lower() in self.void_tags:
            return
        if self.current.parent:
            self.current = self.current.parent

    def handle_data(self, data):
        self.current.text += data


def parse_html(html_str):
    p = TreeHTMLParser()
    p.feed(html_str)
    return p.root


class FrontendIntegrityTestSuite(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.today = timezone.localdate()
        self.mock_user = type('MockUser', (), {
            'is_authenticated': True,
            'username': 'frontend_qa_admin',
            'email': 'qa_admin@test.com',
            'role': 'admin',
            'is_staff': True,
            'is_superuser': True,
            'branch': None,
            'branch_id': 1,
            'pk': 9991,
            'id': 9991,
        })()
        paginator = Paginator([], 25)
        self.mock_page_obj = paginator.page(1)

    def test_template_compilation_all_role_dashboards(self):
        """Verify that all major role dashboard and listing templates compile cleanly."""
        template_names = [
            'base.html',
            'admin/leads_list.html',
            'admin_dashboard/dashboard.html',
            'telecaller_dashboard/dashboard.html',
            'counselor_dashboard/dashboard.html',
            'manager_dashboard/dashboard.html',
            'branch_head_dashboard/dashboard.html',
            'accountant/dashboard.html',
        ]
        for tname in template_names:
            tpl = get_template(tname)
            self.assertIsNotNone(tpl, f"Template {tname} failed to load or compile!")

    def test_title_block_purity_on_leads_list(self):
        """Verify that rendered leads_list.html produces clean plaintext <title> without HTML markup."""
        context = {
            'leads': [],
            'page_obj': self.mock_page_obj,
            'search_query': '',
            'active_view': 'all',
            'user': self.mock_user,
            'request': self.factory.get('/leads/'),
            'allowed_page_sizes': [25, 50, 100],
            'page_size': 25,
        }
        rendered = render_to_string('admin/leads_list.html', context)
        doc = parse_html(rendered)
        title_node = doc.find('title')
        self.assertIsNotNone(title_node, "<title> tag must exist")
        title_text = title_node.get_text()
        self.assertIn("Leads - DigipandaCRM", title_text)
        self.assertIsNone(title_node.find('div'), "<title> must not contain <div> tags")
        self.assertIsNone(title_node.find('aside'), "<title> must not contain <aside> tags")
        self.assertLess(len(title_text), 100, f"Title text unexpectedly long: {len(title_text)}")

    def test_command_palette_and_logout_overlay_sibling_relationship(self):
        """Verify #tp-command-palette and #tp-logout-overlay are direct siblings in base.html."""
        rendered = render_to_string('base.html', {'request': self.factory.get('/'), 'user': self.mock_user})
        doc = parse_html(rendered)
        palette = doc.find('div', id='tp-command-palette')
        logout = doc.find('div', id='tp-logout-overlay')
        self.assertIsNotNone(palette, "#tp-command-palette must exist")
        self.assertIsNotNone(logout, "#tp-logout-overlay must exist")
        self.assertIsNone(palette.find('div', id='tp-logout-overlay'), 
                         "#tp-logout-overlay must not be nested in #tp-command-palette")
        self.assertEqual(palette.parent, logout.parent, "Must be siblings with same parent")

    def test_modal_accessibility_semantics(self):
        """Verify key modals have role='dialog' and aria-modal='true'."""
        rendered = render_to_string('base.html', {'request': self.factory.get('/'), 'user': self.mock_user})
        doc = parse_html(rendered)
        
        palette = doc.find('div', id='tp-command-palette')
        self.assertEqual(palette.attrs.get('role'), 'dialog')
        self.assertEqual(palette.attrs.get('aria-modal'), 'true')
        
        logout = doc.find('div', id='tp-logout-overlay')
        self.assertEqual(logout.attrs.get('role'), 'dialog')
        self.assertEqual(logout.attrs.get('aria-modal'), 'true')

        call_modal = doc.find('div', id='call-notes-required-modal')
        self.assertEqual(call_modal.attrs.get('role'), 'dialog')
        self.assertEqual(call_modal.attrs.get('aria-modal'), 'true')

    def test_date_alias_normalization_and_reconciliation(self):
        """Verify that date aliases (start_date, from_date, date_from) map reliably."""
        req_from = self.factory.get('/?from_date=2026-10-01&to_date=2026-10-10')
        res_from = extract_normalized_date_range(req_from)
        self.assertEqual(res_from['start_date'], '2026-10-01')
        self.assertEqual(res_from['end_date'], '2026-10-10')

        req_start = self.factory.get('/?start_date=2026-10-01&end_date=2026-10-10')
        res_start = extract_normalized_date_range(req_start)
        self.assertEqual(res_start['start_date'], '2026-10-01')
        self.assertEqual(res_start['end_date'], '2026-10-10')

        req_dfrom = self.factory.get('/?date_from=2026-10-01&date_to=2026-10-10')
        res_dfrom = extract_normalized_date_range(req_dfrom)
        self.assertEqual(res_dfrom['start_date'], '2026-10-01')
        self.assertEqual(res_dfrom['end_date'], '2026-10-10')

    def test_kpi_url_generation_preserves_date_and_branch_filters(self):
        """Verify {% build_kpi_url %} preserves active filters across views."""
        req = self.factory.get('/admin-dashboard/?from_date=2026-10-05&to_date=2026-10-25&branch=2')
        context = {'request': req, 'selected_branch_id': 2}
        url = build_kpi_url(context, 'admin_leads_list', 'status_group', 'connected')
        
        self.assertIn('status_group=connected', url)
        self.assertIn('date_from=2026-10-05', url)
        self.assertIn('date_to=2026-10-25', url)
        self.assertIn('branch=2', url)


if __name__ == '__main__':
    import unittest
    unittest.main()
