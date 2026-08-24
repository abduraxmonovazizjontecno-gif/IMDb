from pathlib import Path

from django.core.management.base import BaseCommand

from apps.models import Movie, Person


class Command(BaseCommand):
    help = (
        'Poster/foto variantlarini yaratadi: WebP (82%) va AVIF (60%). '
        'SVG va lokal bo\'lmagan fayllar o\'tkazib yuboriladi. '
        'Ishga tushirish: python manage.py optimize_posters'
    )

    def handle(self, *args, **options):
        from itertools import chain
        items = chain(
            ((m, 'poster') for m in Movie.objects.exclude(poster='')),
            ((m, 'banner') for m in Movie.objects.exclude(banner='')),
            ((p, 'photo') for p in Person.objects.exclude(photo='')),
        )
        made = skipped = failed = 0
        for obj, field in items:
            f = getattr(obj, field)
            if not f:
                continue
            try:
                src = Path(f.path)
            except NotImplementedError:
                skipped += 1
                continue
            if src.suffix.lower() == '.svg':
                skipped += 1
                continue
            try:
                from PIL import Image
                img = Image.open(src).convert('RGB')
                for ext, fmt, quality in (('webp', 'WEBP', 82), ('avif', 'AVIF', 60)):
                    out = src.with_suffix('.' + ext)
                    if not out.exists():
                        img.save(out, fmt, quality=quality)
                made += 1
            except Exception as exc:
                failed += 1
                self.stdout.write(self.style.ERROR(f'{obj}: {exc}'))
        self.stdout.write(self.style.SUCCESS(
            f'Bajarildi: {made} fayl, o\'tkazib yuborildi: {skipped}, xato: {failed}'
        ))
