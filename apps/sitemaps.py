from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.models import Movie, Person


class StaticViewSitemap(Sitemap):
    priority = 0.6
    changefreq = 'daily'

    def items(self):
        return ['index', 'leaderboard']

    def location(self, item):
        return reverse(item)


class MovieSitemap(Sitemap):
    priority = 0.9
    changefreq = 'weekly'
    lastmod = 'updated_at'

    def items(self):
        return Movie.objects.filter(status='published')


class PersonSitemap(Sitemap):
    priority = 0.5
    changefreq = 'monthly'
    lastmod = 'updated_at'

    def items(self):
        return Person.objects.all()


sitemaps = {
    'static': StaticViewSitemap,
    'movies': MovieSitemap,
    'people': PersonSitemap,
}
