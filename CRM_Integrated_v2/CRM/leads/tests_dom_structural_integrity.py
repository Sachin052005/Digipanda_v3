import os
import sys
import re
from unittest import TestCase
from html.parser import HTMLParser

CRM_ROOT = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM'
if CRM_ROOT not in sys.path:
    sys.path.insert(0, CRM_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.template.loader import render_to_string
from django.test import RequestFactory
from django.core.paginator import Paginator

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


class DOMStructuralIntegrityTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.mock_user = type('MockUser', (), {
            'is_authenticated': True,
            'username': 'admin_dom_test',
            'email': 'admin_dom@test.com',
            'role': 'admin',
            'is_staff': True,
            'is_superuser': True,
            'branch': None,
            'pk': 9999,
            'id': 9999,
        })()
        paginator = Paginator([], 25)
        self.mock_page_obj = paginator.page(1)

    def test_base_html_command_palette_and_logout_overlay_are_siblings(self):
        """Verify that #tp-logout-overlay is not nested inside #tp-command-palette in base.html."""
        rendered = render_to_string('base.html', {'request': self.factory.get('/'), 'user': self.mock_user})
        doc = parse_html(rendered)
        
        palette = doc.find('div', id='tp-command-palette')
        logout = doc.find('div', id='tp-logout-overlay')
        
        self.assertIsNotNone(palette, "#tp-command-palette should exist in base.html")
        self.assertIsNotNone(logout, "#tp-logout-overlay should exist in base.html")
        
        # Verify logout is NOT inside palette
        self.assertIsNone(palette.find('div', id='tp-logout-overlay'), 
                         "CRITICAL: #tp-logout-overlay must NOT be a child of #tp-command-palette")
        
        # Verify both are direct children of the same parent container
        self.assertEqual(palette.parent, logout.parent, 
                         "Both #tp-command-palette and #tp-logout-overlay should share the same parent container")

    def test_admin_leads_list_title_block_contains_no_html(self):
        """Verify that <title> in rendered admin/leads_list.html contains only plaintext title."""
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
        self.assertIsNotNone(title_node, "Page must have a <title> tag")
        title_text = title_node.get_text().strip()
        
        self.assertIn("Leads - DigipandaCRM", title_text)
        self.assertIsNone(title_node.find('div'), "CRITICAL: <title> must not contain <div> tags!")
        self.assertIsNone(title_node.find('aside'), "CRITICAL: <title> must not contain <aside> tags!")
        self.assertLess(len(title_text), 150, 
                        f"<title> length ({len(title_text)}) is too large; HTML is likely leaked!")

    def test_filter_drawer_exists_inside_body(self):
        """Verify that the filter drawer exists in the document body and has correct IDs."""
        context = {
            'leads': [],
            'page_obj': self.mock_page_obj,
            'active_view': 'all',
            'user': self.mock_user,
            'request': self.factory.get('/leads/'),
            'allowed_page_sizes': [25, 50, 100],
            'page_size': 25,
        }
        rendered = render_to_string('admin/leads_list.html', context)
        doc = parse_html(rendered)
        
        body = doc.find('body')
        self.assertIsNotNone(body, "Document must have a <body>")
        
        drawer = body.find('aside', id='filterDrawer')
        overlay = body.find('div', id='filterDrawerOverlay')
        
        self.assertIsNotNone(drawer, "#filterDrawer must be rendered inside <body>")
        self.assertIsNotNone(overlay, "#filterDrawerOverlay must be rendered inside <body>")

if __name__ == '__main__':
    import unittest
    unittest.main()
