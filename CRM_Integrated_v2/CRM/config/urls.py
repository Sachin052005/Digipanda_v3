from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap

from accounts import views_public
from config.sitemaps import sitemaps

urlpatterns = [
    # Public SEO-Optimized Root Landing Page
    path('', views_public.landing_page_view, name='root'),

    # Search Engine Directives & Sitemap
    path('robots.txt', views_public.robots_txt_view, name='robots_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),

    # Django Admin Site
    path('django-admin/', admin.site.urls),

    # Application Modules
    path('', include('accounts.urls')),
    path('', include('reports.urls')),
    path('', include('managers.urls')),
    path('', include('branch_heads.urls')),
    path('', include('counselors.urls')),
    path('', include('telecallers.urls')),
    path('', include('leads.urls')),
    path('', include('lead_channels.urls')),
    path('', include('products.urls')),
    path('', include('branches.urls')),
    path('', include('calls.urls')),
    path('', include('followups.urls')),
    path('', include('activities.urls')),
    path('drive/', include('drive.urls')),
    path('call-recordings/', include('drive.urls')),
    # WhatsApp inbox (/whatsapp/), automations (/automations/), WhatsApp webhook (/webhook/whatsapp/)
    path('', include('chat.urls')),
    path('chat/', include('chat.urls')),
    # Facebook Lead Ads: list + sync (/facebook-leads/), webhook (/facebook-leads/webhook/)
    path('facebook-leads/', include('fb_leads.urls')),
    # Dedicated Finance Portal Suite
    path('finance/', include('finance.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
