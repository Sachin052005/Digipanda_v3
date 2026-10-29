from django.shortcuts import render
from django.http import HttpResponse
from django.utils import timezone


def landing_page_view(request):
    """
    Public Homepage / Landing Page for Digipanda CRM (https://digipandacrm.in/).
    Exposes authentic CRM features, benefits, FAQs, and portal CTAs without
    requiring authentication or triggering 302 redirects for search engine bots.
    """
    context = {
        'canonical_url': 'https://digipandacrm.in/',
        'current_year': timezone.now().year,
        'user': request.user,
        'is_authenticated': request.user.is_authenticated,
    }
    return render(request, 'public/landing_page.html', context)


def robots_txt_view(request):
    """
    Serves /robots.txt with search-engine crawling instructions
    and sitemap location. Protects private authenticated application paths
    while allowing full indexation of public landing and enquiry pages.
    """
    lines = [
        "User-agent: *",
        "Allow: /",
        "Allow: /enquiry/",
        "Allow: /login/",
        "Allow: /static/",
        "Disallow: /admin/",
        "Disallow: /telecaller/",
        "Disallow: /counselor/",
        "Disallow: /manager/",
        "Disallow: /branch-head/",
        "Disallow: /accountant/",
        "Disallow: /receptionist/",
        "Disallow: /api/",
        "Disallow: /django-admin/",
        "",
        "Sitemap: https://digipandacrm.in/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")
