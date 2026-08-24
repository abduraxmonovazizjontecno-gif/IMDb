from contextlib import suppress
from io import BytesIO

from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from PIL import Image

# Kirill → Lotin transliteratsiya (o'zbekcha qidiruv uchun)
CYRILLIC_MAP = {
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'E',
    'Ж': 'J', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
    'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
    'Ф': 'F', 'Х': 'X', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sh', 'Ъ': '',
    'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya', 'Ғ': 'G', 'Қ': 'Q',
    'Ў': 'O', 'Ҳ': 'H', 'Ұ': 'U', 'Ө': 'O', 'Ү': 'U', 'НҚ': 'Nq',
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'j', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'x', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sh', 'ъ': '',
    'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya', 'ғ': 'g', 'қ': 'q',
    'ҳ': 'h', 'ў': 'o', 'ұ': 'u', 'ө': 'i', 'ү': 'u', 'Ң': 'N', 'ң': 'n',
}


def to_latin(text):
    """Kirill (yoki aralash) matnni lotinga o'giradi — qidiruvga moslashtirish uchun."""
    return ''.join(CYRILLIC_MAP.get(ch, ch) for ch in text)


def get_client_ip(request):
    """Foydalanuvchi IP-manzili — XFF faqat ishonchli proxy orqali kelganda o'qiladi.

    Proxy mavjud bo'lsa (SECURE_PROXY_SSL_HEADER to'g'ri kelganida) XFF zanjirining
    eng oxirgi (proxy tomonidan qo'shilgan) qiymati olinadi; aks holda REMOTE_ADDR.
    Bu mijoz tomonidan soxta X-Forwarded-For yuborib rate-limitni chetlab
    o'tishning oldini oladi.
    """
    header = getattr(settings, 'SECURE_PROXY_SSL_HEADER', None)
    proxied = bool(header) and request.META.get(header[0]) == header[1]
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if proxied and forwarded:
        return forwarded.split(',')[-1].strip() or 'unknown'
    return request.META.get('REMOTE_ADDR') or 'unknown'


def rate_limit_exceeded(request, key, limit=5, window=900):
    """Brute-force himoyasi: IP yoki (IP+hujjat) uchun urinishlar sonini cheklaydi.

    Qaytaram:
        True → blok (urinishlar limitdan oshdi),
        False → davom etish mumkin.
    """
    ip = get_client_ip(request)
    cache_key = f'rl:{key}:{ip}'
    attempts = cache.get(cache_key, 0)
    if attempts >= limit:
        return True
    cache.set(cache_key, attempts + 1, window)
    return False


def rate_limit_reset(request, key):
    ip = get_client_ip(request)
    cache.delete(f'rl:{key}:{ip}')


def smart_convert(instance, field_name, size, quality=82):
    """Yuklangan rasmni markazlashtirib kesadi, o'lchamini normallashtiradi va WebP ga aylantiradi.

    Agar rasm ochilmasa (masalan SVG) yoki oddiy fayl bo'lsa — tegmagan holda qoldiriladi.
    """
    import logging
    logger = logging.getLogger(__name__)
    image_field = getattr(instance, field_name, None)
    if not image_field or not image_field.name:
        return
    try:
        img = Image.open(image_field)
        img.load()
    except Exception as e:
        logger.error('Failed to open image for %s: %s', field_name, e)
        return
    if getattr(img, 'format', '') == 'SVG':
        return
    try:
        img = img.convert('RGB')
        tw, th = size
        w, h = img.size
        target_ratio = tw / th
        ratio = w / h
        if ratio > target_ratio:
            new_w = max(int(h * target_ratio), 1)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        elif ratio < target_ratio:
            new_h = max(int(w / target_ratio), 1)
            top = (h - new_h) // 2
            img = img.crop((0, top, w, top + new_h))
        if (w, h) != size:
            img = img.resize(size, Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format='WEBP', quality=quality)
        base = image_field.name.rsplit('.', 1)[0]
        orig_name = image_field.name
        new_name = f'{base}.webp'
        image_field.save(new_name, ContentFile(buf.getvalue()), save=False)
        if new_name != orig_name:
            with suppress(Exception):
                image_field.storage.delete(orig_name)
    except Exception as e:
        logger.error('Failed to process image %s: %s', field_name, e)


def dashboard_callback(request, context):
    """django-unfold boshqaruv paneli uchun KPI statistika va qisqa yorliqlar."""
    from apps.models import Movie, MovieRating, MovieReview, User

    published = Movie.objects.filter(status='published').count()
    kpi_list = [
        {'title': 'Filmlar', 'metric': Movie.objects.count(), 'footer': f"{published} tasi nashr etilgan"},
        {'title': 'Foydalanuvchilar', 'metric': User.objects.count(), 'footer': "Ro'yxatdan o'tgan"},
        {'title': 'Jami baholar', 'metric': MovieRating.objects.count(), 'footer': '1-10 shkala'},
        {'title': 'Sharhlar', 'metric': MovieReview.objects.count(), 'footer': 'Foydalanuvchilar fikri'},
    ]
    context['kpi'] = kpi_list
    context['kpi_list'] = kpi_list
    context['top_movies'] = Movie.objects.filter(status='published').order_by('-rating', '-views_count')[:5]
    context['shortcuts'] = [
        {'title': 'Film qo\'shish', 'url': '/admin/apps/movie/add/', 'icon': 'movie'},
        {'title': 'Person qo\'shish', 'url': '/admin/apps/person/add/', 'icon': 'group'},
        {'title': 'Janrlar', 'url': '/admin/apps/genre/', 'icon': 'label'},
        {'title': 'Saytga o\'tish', 'url': '/', 'external': True, 'icon': 'open_in_new'},
    ]
    return context
