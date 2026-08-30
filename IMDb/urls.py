from apps.sitemaps import sitemaps
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import FileResponse, HttpResponseNotAllowed
from django.urls import include, path
from django.views.generic import TemplateView


def service_worker(request):
    """Service Worker ni ildiz yo'ldan beradi (scope='/' uchun ruxsat headeri bilan).

    SW ni /static/js/ ichidan ro'yxatdan o'tkazish scope='/' ga ruxsat bermaydi,
    shuning uchun uni ildizdan (/sw.js) beramiz va Service-Worker-Allowed headerini qo'yamiz.
    """
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])
    sw_path = settings.BASE_DIR / 'static' / 'js' / 'service-worker.js'
    # FileResponse faylni o'zi yopadi, shuning uchun context manager kerak emas.
    response = FileResponse(open(sw_path, 'rb'), content_type='application/javascript')  # noqa: SIM115
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response


urlpatterns = [
    path('sw.js', service_worker, name='service_worker'),
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
