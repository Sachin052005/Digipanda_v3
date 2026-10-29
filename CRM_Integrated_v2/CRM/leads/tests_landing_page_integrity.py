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
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from accounts.views_public import landing_page_view


class LandingPageIntegrityTests(TestCase):
    """
    Automated regression test suite verifying the Enterprise Landing Page redesign:
    1. HTTP 200 response & template rendering integrity.
    2. Elimination of WebGL/Three.js heavy scripts and cyberpunk visual effects.
    3. Proper inclusion of scoped CSS (landing-page.css) and JS (landing-page.js).
    4. Accurate navigation endpoints and CTA links (login, walk-in enquiry).
    5. Presence of all essential institutional sections, ARIA roles, and accessibility attributes.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/')
        self.request.user = AnonymousUser()
        self.response = landing_page_view(self.request)
        self.content = self.response.content.decode('utf-8')

    def test_http_status_ok(self):
        """Landing page root URL must return HTTP 200."""
        self.assertEqual(self.response.status_code, 200)

    def test_page_title_and_branding(self):
        """Title must reflect Enterprise TechPanda CRM branding."""
        self.assertIn('<title>TechPanda CRM | Next-Gen Admissions &amp; Sales Management Platform</title>', self.content)
        self.assertIn('TechPanda CRM', self.content)
        self.assertIn('DigiPanda', self.content)

    def test_absence_of_three_js_and_cyberpunk(self):
        """Heavyweight Three.js WebGL canvas and dark cyberpunk patterns must be completely removed."""
        self.assertNotIn('three.min.js', self.content)
        self.assertNotIn('three.js', self.content)
        self.assertNotIn('id="three-canvas"', self.content)
        self.assertNotIn('cyberpunk', self.content.lower())
        self.assertNotIn('neon-glow', self.content)
        self.assertNotIn('hologram', self.content.lower())

    def test_external_scoped_static_assets_linked(self):
        """Page must link scoped landing-page.css and landing-page.js."""
        self.assertIn('landing-page.css', self.content)
        self.assertIn('landing-page.js', self.content)
        self.assertIn('design-system.css', self.content)
        self.assertIn('theme-manager.js', self.content)

    def test_navigation_and_cta_endpoints(self):
        """Primary CTAs must resolve to valid Django reverse URLs."""
        login_url = reverse('login')
        enquiry_url = reverse('public_student_enquiry_form')
        
        self.assertIn(f'href="{login_url}"', self.content)
        self.assertIn(f'href="{enquiry_url}"', self.content)
        self.assertIn('Access Live Portal', self.content)
        self.assertIn('Campus Walk-in Desk', self.content)

    def test_all_enterprise_sections_present(self):
        """All key structural sections must exist in semantic order."""
        sections = [
            'id="features"',
            'id="solutions"',
            'id="showcase"',
            'id="calculator"',
            'id="faq"',
        ]
        for section_id in sections:
            with self.subTest(section=section_id):
                self.assertIn(section_id, self.content)

    def test_hero_cockpit_mockup_present(self):
        """Centerpiece hero CRM cockpit mockup must exist above the fold."""
        self.assertIn('class="lp-cockpit-wrapper"', self.content)
        self.assertIn('class="lp-cockpit-frame"', self.content)
        self.assertIn('class="lp-mockup-kpis"', self.content)
        self.assertIn('class="lp-mockup-table"', self.content)
        self.assertIn('Real-Time Ingestion Queue', self.content)

    def test_accessibility_roles_and_aria_attributes(self):
        """Interactive components must feature proper ARIA semantics and roles."""
        self.assertIn('role="banner"', self.content)
        self.assertIn('role="navigation"', self.content)
        self.assertIn('role="tablist"', self.content)
        self.assertIn('role="tab"', self.content)
        self.assertIn('role="tabpanel"', self.content)
        self.assertIn('role="contentinfo"', self.content)
        self.assertIn('aria-expanded="false"', self.content)
        self.assertIn('aria-controls=', self.content)

    def test_json_ld_schema_present(self):
        """Structured JSON-LD schema metadata must be embedded for enterprise SEO."""
        self.assertIn('application/ld+json', self.content)
        self.assertIn('SoftwareApplication', self.content)


if __name__ == '__main__':
    import unittest
    unittest.main()
