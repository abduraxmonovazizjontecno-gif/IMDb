"""E2E smoke testlar uchun minimal ma'lumot tayyorlaydi (Gladiator + foydalanuvchi)."""

from datetime import date

from django.core.management.base import BaseCommand

from apps.models import Genre, Movie, User


class Command(BaseCommand):
    help = 'E2E testlar uchun minimal katalog yaratadi (takroriy ishlatish xavfsiz).'

    def handle(self, *args, **options):
        genre, _ = Genre.objects.get_or_create(name='Drama', slug='drama')
        movie, created = Movie.objects.get_or_create(
            slug='gladiator',
            defaults={
                'title': 'Gladiator',
                'description': 'Rim generali Maximus haqida.',
                'release_date': date(2000, 5, 5),
                'duration_minutes': 155,
                'status': 'published',
                'views_count': 0,
                'rating_count': 0,
            },
        )
        if created:
            movie.genres.add(genre)
        if not movie.video_url:
            movie.video_url = '/media/trailers/media2.mp4'
            movie.save(update_fields=['video_url'])
        if not User.objects.filter(phone_number='+998900000001').exists():
            User.objects.create_user(
                phone_number='+998900000001', password='testpass123', full_name='Smoke User',
            )
        self.stdout.write(self.style.SUCCESS(f'Smoke ma\'lumotlar tayyor: {movie.title}'))
