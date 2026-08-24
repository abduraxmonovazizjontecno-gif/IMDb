from django.db import migrations

from apps.utils import to_latin


def _build_search_text(movie):
    parts = [
        movie.title or '', movie.original_title or '',
        movie.description or '', movie.language or '',
        movie.country or '', movie.studio or '',
    ]
    normalized = list(parts) + [to_latin(p) for p in parts if p]
    return ' '.join(p.strip() for p in normalized if p and p.strip()).lower()


def backfill_search_text(apps, schema_editor):
    Movie = apps.get_model('apps', 'Movie')
    for pk, title, original_title, description, language, country, studio in (
        Movie.objects.values_list('pk', 'title', 'original_title', 'description',
                                  'language', 'country', 'studio').iterator()
    ):
        movie = type('M', (), {
            'title': title, 'original_title': original_title, 'description': description,
            'language': language, 'country': country, 'studio': studio,
        })
        Movie.objects.filter(pk=pk).update(search_text=_build_search_text(movie))


class Migration(migrations.Migration):

    dependencies = [
        ('apps', '0014_movie_search_text'),
    ]

    operations = [
        migrations.RunPython(backfill_search_text, migrations.RunPython.noop),
    ]
