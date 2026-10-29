from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """
    Publicly indexable canonical sitemap for Digipanda CRM.
    Only valid, canonical, publicly accessible URLs are exposed.
    Private dashboards, APIs, and staff-only portals are strictly excluded.
    """
    protocol = 'https'

    def items(self):
        return [
            ('root', 1.0, 'daily'),
            ('public_student_enquiry_form', 0.9, 'weekly'),
            ('login', 0.6, 'monthly'),
        ]

    def location(self, item):
        return reverse(item[0])

    def priority(self, item):
        return item[1]

    def changefreq(self, item):
        return item[2]


sitemaps = {
    'static': StaticViewSitemap,
}
