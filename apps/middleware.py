from urllib.parse import urlparse

from django.conf import settings


class SecurityHeadersMiddleware:
    """Qo'shimcha xavfsizlik header'lari (CSP, Permissions-Policy, CORP, X-Robots-Tag)."""

    _FRAME_SOURCES = (
        'https://www.youtube.com https://www.youtube-nocookie.com https://vidsrc.to '
        'https://www.googletagmanager.com'
    )
    _SCRIPT_SOURCES = (
        "'self' https://www.youtube.com https://www.youtube-nocookie.com "
        'https://www.googletagmanager.com'
    )
    _CONNECT_SOURCES = (
        "'self' https://www.google-analytics.com https://analytics.google.com "
        'https://stats.g.doubleclick.net'
    )

    def __init__(self, get_response):
        self.get_response = get_response
        media = settings.MEDIA_URL or ''
        if media.startswith(('http://', 'https://')):
            parsed = urlparse(media)
            media_origin = f'{parsed.scheme}://{parsed.netloc}'
        else:
            media_origin = "'self'"
        self._csp = (
            "default-src 'self'; "
            f"script-src {self._SCRIPT_SOURCES}; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            f"img-src 'self' data: blob: {media_origin}; "
            f"frame-src {self._FRAME_SOURCES}; "
            f"media-src 'self' blob: {media_origin}; "
            f"connect-src {self._CONNECT_SOURCES}; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'"
        )

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault('Content-Security-Policy', self._csp)
        response.setdefault('Permissions-Policy',
                            'camera=(), microphone=(), geolocation=(), payment=(), usb=()')
        response.setdefault('Cross-Origin-Resource-Policy', 'same-origin')
        if request.path.startswith('/admin/'):
            response.setdefault('X-Robots-Tag', 'noindex, nofollow')
        return response
