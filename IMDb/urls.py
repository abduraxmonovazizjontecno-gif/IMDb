from apps.sitemaps import sitemaps
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.urls')),
    path(
        'sitemap.xml',
        sitemap,
        {'sitemaps': sitemaps},
        name='django.contrib.sitemaps.views.sitemap',
    ),
    path(
        'robots.txt',
        TemplateView.as_view(template_name='robots.txt', content_type='text/plain'),
        name='robots',
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
