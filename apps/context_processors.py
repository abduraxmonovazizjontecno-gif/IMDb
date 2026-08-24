from django.conf import settings


def site_cfg(request):
    return {
        'GOOGLE_TAG_ID': settings.GOOGLE_TAG_ID,
    }
