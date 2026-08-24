from datetime import date
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.models import Credit, Genre, Movie, MovieRating, MovieReview, Person, User, WatchlistItem
from apps.utils import dashboard_callback


class MovieTests(TestCase):
    def setUp(self):
        drama = Genre.objects.create(name='Drama', slug='drama')
        self.movie = Movie.objects.create(
            title='Test Film', slug='test-film', description='Tavsif',
            release_date=date(2020, 1, 1), duration_minutes=120,
            rating=8.5, views_count=10, status='published',
        )
        self.movie.genres.add(drama)
        Movie.objects.create(
            title='Draft', slug='draft', description='Tavsif',
            release_date=date(2021, 1, 1), duration_minutes=90, status='draft',
        )

    def test_index_shows_only_published(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Film')
        self.assertNotContains(response, 'Draft')

    def test_banner_shows_newest_movies(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.movie.poster = SimpleUploadedFile('poster.jpg', b'\x00' * 64, content_type='image/jpeg')
        self.movie.save()
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="banner-slider"')
        self.assertContains(response, 'banner-slide')
        self.assertContains(response, 'banner-thumb')
        self.assertContains(response, 'banner-progress')
        self.assertContains(response, 'Yangi kino')
        self.assertContains(response, 'Test Film')
        self.assertContains(response, 'rel="preload"')
        self.assertContains(response, 'fetchpriority="high"')

    def test_banner_field_used_when_set(self):
        from io import BytesIO
        from pathlib import Path

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image as PilImage

        buf = BytesIO()
        PilImage.new('RGB', (160, 90), (30, 80, 160)).save(buf, 'JPEG')
        self.movie.poster = SimpleUploadedFile('poster.jpg', buf.getvalue(), content_type='image/jpeg')
        self.movie.banner = SimpleUploadedFile('banner.jpg', buf.getvalue(), content_type='image/jpeg')
        self.movie.save()
        response = self.client.get(reverse('index'))
        self.assertContains(response, '/media/banners/banner')
        self.assertNotContains(response, 'banner-bg">/media/posters')
        self.movie.refresh_from_db()
        webp = Path(self.movie.banner.path).with_suffix('.webp')
        avif = Path(self.movie.banner.path).with_suffix('.avif')
        self.assertTrue(webp.exists(), 'banner webp varianti yaratilishi kerak')
        self.assertTrue(avif.exists(), 'banner avif varianti yaratilishi kerak')
        self.assertIsNotNone(self.movie.banner_webp)
        self.assertIsNotNone(self.movie.banner_avif)

    def test_search_and_filter(self):
        self.assertContains(self.client.get(reverse('index') + '?q=test'), 'Test Film')
        self.assertContains(self.client.get(reverse('index') + '?genre=drama'), 'Test Film')
        self.assertNotContains(self.client.get(reverse('index') + '?genre=drama'), 'Interstellar')

    def test_search_page(self):
        response = self.client.get(reverse('search'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Qidiruv')
        self.assertContains(self.client.get(reverse('search') + '?q=test'), 'Test Film')
        self.assertContains(self.client.get(reverse('search') + '?genre=drama'), 'Test Film')
        self.assertNotContains(self.client.get(reverse('search') + '?genre=drama'), 'Interstellar')

    def test_search_finds_cyrillic_title_via_latin(self):
        self.movie.original_title = 'Крёстный отец'
        self.movie.save()
        body = self.client.get(reverse('index') + '?q=krestnyy').content.decode('utf-8', 'ignore')
        self.assertIn('Test Film', body)
        body = self.client.get(reverse('index') + '?q=крёстный').content.decode('utf-8', 'ignore')
        self.assertIn('Test Film', body)

    def test_nav_has_search_button_index_has_no_filters(self):
        body = self.client.get(reverse('index')).content.decode('utf-8', 'ignore')
        self.assertIn('class="search-btn"', body)
        self.assertIn('href="/search/"', body)
        self.assertNotIn('<div class="toolbar">', body)
        self.assertNotIn('<select name="year"', body)

    def test_detail_and_view_count(self):
        before = self.movie.views_count
        response = self.client.get(reverse('movie_detail', kwargs={'slug': 'test-film'}))
        self.assertEqual(response.status_code, 200)
        self.movie.refresh_from_db()
        self.assertEqual(self.movie.views_count, before + 1)
        self.client.get(reverse('movie_detail', kwargs={'slug': 'test-film'}))
        self.movie.refresh_from_db()
        self.assertEqual(self.movie.views_count, before + 1)

    def test_draft_not_accessible(self):
        self.assertEqual(
            self.client.get(reverse('movie_detail', kwargs={'slug': 'draft'})).status_code,
            404,
        )

    def test_youtube_methods(self):
        self.movie.video_url = 'https://youtu.be/AbC123xYz89'
        self.movie.save()
        self.assertEqual(self.movie.get_youtube_id(), 'AbC123xYz89')
        self.assertTrue(self.movie.is_youtube_trailer())
        self.movie.video_url = 'https://www.youtube.com/watch?v=qqQ8ZzZzZZZ&t=10'
        self.movie.save()
        self.assertEqual(self.movie.get_youtube_id(), 'qqQ8ZzZzZZZ')
        self.movie.video_url = 'https://www.youtube.com/embed/dQw4w9WgXcQ'
        self.movie.save()
        self.assertEqual(self.movie.get_youtube_id(), 'dQw4w9WgXcQ')
        self.movie.video_url = 'https://example.com/video.mp4'
        self.movie.save()
        self.assertIsNone(self.movie.get_youtube_id())
        self.assertFalse(self.movie.is_youtube_trailer())
        self.movie.video_url = None
        self.movie.save()
        self.assertIsNone(self.movie.get_youtube_id())

    def test_updated_at_auto_now(self):
        self.movie.refresh_from_db()
        self.assertIsNotNone(self.movie.updated_at)

    def test_poster_webp_avif_variants(self):
        from io import BytesIO
        from pathlib import Path

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image as PilImage

        buf = BytesIO()
        PilImage.new('RGB', (60, 90), (200, 120, 40)).save(buf, 'JPEG')
        self.movie.poster = SimpleUploadedFile('poster.jpg', buf.getvalue(), content_type='image/jpeg')
        self.movie.save()

        webp = Path(self.movie.poster.path).with_suffix('.webp')
        avif = Path(self.movie.poster.path).with_suffix('.avif')
        self.assertTrue(webp.exists(), 'webp varianti yaratilishi kerak')
        self.assertTrue(avif.exists(), 'avif varianti yaratilishi kerak')
        self.assertIsNotNone(self.movie.poster_webp)
        self.assertIsNotNone(self.movie.poster_avif)
        self.assertTrue(self.movie.poster_webp.endswith('.webp'))
        self.assertTrue(self.movie.poster_avif.endswith('.avif'))

        body = self.client.get(reverse('movie_detail', kwargs={'slug': 'test-film'})).content.decode('utf-8', 'ignore')
        self.assertIn('<picture>', body)
        self.assertIn('type="image/webp"', body)
        self.assertIn('type="image/avif"', body)

    def test_tg_video_proxy_requires_token(self):
        self.movie.video_url = 'tg://documents/video.mp4'
        self.movie.save()
        with patch('django.conf.settings.TELEGRAM_BOT_TOKEN', ''):
            resp = self.client.get(reverse('movie_tg_video', kwargs={'slug': 'test-film'}))
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn('api.telegram.org', resp.content.decode('utf-8', 'ignore'))

    def test_sitemap_has_lastmod(self):
        body = self.client.get('/sitemap.xml').content.decode('utf-8', 'ignore')
        self.assertIn('<lastmod>', body)

    def test_static_css_linked(self):
        body = self.client.get(reverse('index')).content.decode('utf-8', 'ignore')
        self.assertIn('css/main.css', body)
        self.assertIn('js/main.js', body)
        self.assertIn('class="reveal"', body)

    def test_mobile_drawer_present(self):
        body = self.client.get(reverse('index')).content.decode('utf-8', 'ignore')
        self.assertIn('nav-burger', body)
        self.assertIn('id="drawer"', body)
        self.assertIn('drawer-link', body)


class SecurityConfigTests(TestCase):
    def test_local_dev_hosts_are_allowed_for_admin(self):
        self.assertIn('testserver', settings.ALLOWED_HOSTS)
        self.assertIn('http://localhost', settings.CSRF_TRUSTED_ORIGINS)
        self.assertIn('http://127.0.0.1', settings.CSRF_TRUSTED_ORIGINS)


class AdminDashboardAndAuthTests(TestCase):
    def test_custom_user_manager_accepts_standard_password_keyword(self):
        user = User.objects.create_user(
            phone_number='9911223344',
            full_name='Test User',
            email='user@example.com',
            password='VeryStrongPass123',
        )
        self.assertTrue(user.check_password('VeryStrongPass123'))
        admin = User.objects.create_superuser(
            phone_number='9911223345',
            full_name='Admin User',
            email='admin@example.com',
            password='AdminPass456',
        )
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.check_password('AdminPass456'))

    def test_dashboard_callback_uses_template_keys(self):
        Movie.objects.create(
            title='Dashboard Hit',
            slug='dashboard-hit',
            description='x',
            release_date=date(2024, 1, 1),
            duration_minutes=120,
            rating=9.2,
            views_count=120,
            status='published',
        )
        context = dashboard_callback(RequestFactory().get('/admin/'), {})
        self.assertIn('kpi_list', context)
        self.assertIn('top_movies', context)
        self.assertTrue(context['kpi_list'])
        self.assertEqual(context['top_movies'][0].title, 'Dashboard Hit')


class ToolingTests(TestCase):
    def test_tg_command_requires_token(self):
        out = StringIO()
        with patch('django.conf.settings.TELEGRAM_BOT_TOKEN', ''), self.assertRaises(CommandError):
            call_command('tg', 'poll', stdout=out)

    def test_tg_link_invalid_file_id_no_token_leak(self):
        out = StringIO()

        def fake_api(tok, method, params=None):
            if method == 'getMe':
                return {'username': 'testbot'}
            raise CommandError('Telegram getFile: HTTP 400 Bad Request')

        with patch('apps.management.commands.tg._api', side_effect=fake_api):
            call_command('tg', 'link', 'BAD_ID', stdout=out)
        text = out.getvalue()
        self.assertIn('boshqa botdan', text)
        self.assertNotIn('BAD_TOKEN_VALUE', text)

    def test_tg_poll_output_is_safe(self):
        out = StringIO()
        token = '123:TESTTOKEN'

        def fake_api(tok, method, params=None):
            if method == 'getMe':
                return {'username': 'testbot'}
            if method == 'getUpdates':
                return [{
                    'message': {
                        'video': {'file_id': 'VID1', 'mime_type': 'video/mp4', 'file_size': 1048576},
                        'caption': 'Test film',
                    }
                }]
            if method == 'getFile':
                return {'file_path': 'videos/vid.mp4'}
            return {}

        with patch('django.conf.settings.TELEGRAM_BOT_TOKEN', token), \
             patch('apps.management.commands.tg._api', side_effect=fake_api):
            call_command('tg', 'poll', stdout=out)
        text = out.getvalue()
        self.assertIn('tg://videos/vid.mp4', text)
        self.assertNotIn(token, text)


class AuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='+998901234567', password='testpass123',
            full_name='Test User', email='t@t.uz',
        )

    def test_register(self):
        response = self.client.post(reverse('register'), {
            'full_name': 'New User',
            'phone_number': '+998901111111',
            'email': 'n@n.uz',
            'password': 'strongpass123',
            'password2': 'strongpass123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(phone_number='+998901111111').exists())

    def test_register_password_mismatch(self):
        response = self.client.post(reverse('register'), {
            'full_name': 'New User',
            'phone_number': '+998901111111',
            'email': 'n@n.uz',
            'password': 'strongpass123',
            'password2': 'different123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(phone_number='+998901111111').exists())

    def test_register_weak_password(self):
        response = self.client.post(reverse('register'), {
            'full_name': 'New User',
            'phone_number': '+998901111111',
            'email': 'n@n.uz',
            'password': '123',
            'password2': '123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(phone_number='+998901111111').exists())

    def test_login_logout(self):
        logged = self.client.login(phone_number='+998901234567', password='testpass123')
        self.assertTrue(logged)
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 405)
        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.client.get(reverse('index'))
        self.assertFalse('_auth_user_id' in self.client.session)


class RatingTests(TestCase):
    def setUp(self):
        genre = Genre.objects.create(name='Drama', slug='drama')
        self.movie = Movie.objects.create(
            title='Rate Me', slug='rate-me', description='Tavsif',
            release_date=date(2020, 1, 1), duration_minutes=100,
            status='published',
        )
        self.movie.genres.add(genre)
        self.alice = User.objects.create_user(
            phone_number='+998901000001', password='testpass123', full_name='Alice',
        )
        self.bob = User.objects.create_user(
            phone_number='+998901000002', password='testpass123', full_name='Bob',
        )

    def test_unrated_movie_has_no_rating(self):
        self.assertIsNone(self.movie.rating)
        self.assertEqual(self.movie.rating_count, 0)
        body = self.client.get(reverse('movie_detail', kwargs={'slug': self.movie.slug})).content.decode('utf-8', 'ignore')
        self.assertNotIn('class="rating-badge"', body)
        self.assertNotIn('ovoz', body)

    def test_rate_requires_login(self):
        response = self.client.post(reverse('rate_movie', kwargs={'slug': self.movie.slug}), {'value': 8})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/?next=/film/rate-me/', response.headers['Location'])
        self.assertEqual(MovieRating.objects.count(), 0)

    def test_rate_and_average(self):
        self.client.force_login(self.alice)
        self.client.post(reverse('rate_movie', kwargs={'slug': self.movie.slug}), {'value': 8})
        self.movie.refresh_from_db()
        self.assertEqual(self.movie.rating_count, 1)
        self.assertEqual(self.movie.rating, 8.0)

        self.client.force_login(self.bob)
        self.client.post(reverse('rate_movie', kwargs={'slug': self.movie.slug}), {'value': 10})
        self.movie.refresh_from_db()
        self.assertEqual(self.movie.rating_count, 2)
        self.assertEqual(self.movie.rating, 9.0)

    def test_rating_change_updates_average(self):
        self.client.force_login(self.alice)
        self.client.post(reverse('rate_movie', kwargs={'slug': self.movie.slug}), {'value': 4})
        self.client.post(reverse('rate_movie', kwargs={'slug': self.movie.slug}), {'value': 8})
        self.movie.refresh_from_db()
        self.assertEqual(self.movie.rating_count, 1)
        self.assertEqual(self.movie.rating, 8.0)

    def test_invalid_rating_ignored(self):
        self.client.force_login(self.alice)
        self.client.post(reverse('rate_movie', kwargs={'slug': self.movie.slug}), {'value': 99})
        self.movie.refresh_from_db()
        self.assertIsNone(self.movie.rating)

    def test_rated_badge_and_leaderboard(self):
        self.client.force_login(self.alice)
        self.client.post(reverse('rate_movie', kwargs={'slug': self.movie.slug}), {'value': 9})
        body = self.client.get(reverse('index')).content.decode('utf-8', 'ignore')
        self.assertIn('class="rating-badge"', body)
        lb = self.client.get(reverse('leaderboard')).content.decode('utf-8', 'ignore')
        self.assertIn('Liderboard', lb)
        self.assertIn('Rate Me', lb)

    def test_detail_shows_rating_only_when_rated(self):
        unrated = self.client.get(reverse('movie_detail', kwargs={'slug': self.movie.slug})).content.decode('utf-8', 'ignore')
        self.assertNotIn('ovoz', unrated)
        self.client.force_login(self.alice)
        self.client.post(reverse('rate_movie', kwargs={'slug': self.movie.slug}), {'value': 9})
        rated = self.client.get(reverse('movie_detail', kwargs={'slug': self.movie.slug})).content.decode('utf-8', 'ignore')
        self.assertIn('ovoz', rated)

    def test_rating_ajax_returns_updated_average(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse('rate_movie', kwargs={'slug': self.movie.slug}),
            {'value': 8},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(str(data['rating']), '8.0')
        self.assertEqual(data['rating_count'], 1)
        self.assertEqual(data['value'], 8)


class ProfileAndAuthFlowTests(TestCase):
    def setUp(self):
        genre = Genre.objects.create(name='Drama', slug='drama')
        self.movie = Movie.objects.create(
            title='Flow', slug='flow', description='Tavsif',
            release_date=date(2021, 5, 1), duration_minutes=90,
            status='published', video_url='https://www.youtube.com/embed/abc123',
        )
        self.movie.genres.add(genre)
        self.user = User.objects.create_user(
            phone_number='+998901222222', password='testpass123', full_name='Diyor',
        )

    def test_show_video_button_when_video_url(self):
        body = self.client.get(reverse('movie_detail', kwargs={'slug': 'flow'})).content.decode('utf-8', 'ignore')
        self.assertIn('data-open-video>&#9654;', body)
        self.assertIn('video-modal', body)

    def test_no_video_button_without_url(self):
        self.movie.video_url = None
        self.movie.save()
        body = self.client.get(reverse('movie_detail', kwargs={'slug': 'flow'})).content.decode('utf-8', 'ignore')
        self.assertNotIn('data-open-video>&#9654;', body)
        self.assertIn('disabled', body)

    def test_profile_requires_login(self):
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.headers['Location'])

    def test_profile_lists_ratings(self):
        self.client.force_login(self.user)
        self.client.post(reverse('rate_movie', kwargs={'slug': 'flow'}), {'value': 8})
        body = self.client.get(reverse('profile')).content.decode('utf-8', 'ignore')
        self.assertIn('Flow', body)
        self.assertIn('8/10', body)

    def test_password_reset_pages(self):
        self.assertEqual(self.client.get(reverse('password_reset')).status_code, 200)
        self.assertEqual(self.client.get(reverse('password_reset_done')).status_code, 200)

    def test_login_invalid_credentials_no_redirect(self):
        response = self.client.post(reverse('login'), {
            'username': '+998901000002',
            'password': 'wrongpass',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('noto\'g\'ri', response.content.decode('utf-8', 'ignore'))


class ImdbFeaturesTests(TestCase):
    def setUp(self):
        self.genre = Genre.objects.create(name='Drama', slug='drama')
        self.movie = Movie.objects.create(
            title='Great Film', slug='great-film', description='Ajoyib tavsif',
            release_date=date(2020, 1, 1), duration_minutes=120,
            status='published', certificate='12+', language='Inglizcha',
            country='AQSh', studio='Test Studio', budget=100000000, box_office=500000000,
        )
        self.other = Movie.objects.create(
            title='Other Film', slug='other-film', description='Boshqa',
            release_date=date(2021, 1, 1), duration_minutes=90,
            status='published',
        )
        self.movie.genres.add(self.genre)
        self.other.genres.add(self.genre)
        self.person = Person.objects.create(
            full_name='John Actor', slug='john-actor', bio='Aktyor',
            birth_date=date(1980, 5, 1), birth_place='Los-Anjeles',
        )
        self.person2 = Person.objects.create(full_name='Jane Director', slug='jane-director')
        Credit.objects.create(movie=self.movie, person=self.person2, role='director')
        Credit.objects.create(movie=self.movie, person=self.person, role='actor', character_name='Hero')
        self.alice = User.objects.create_user(
            phone_number='+998901333333', password='testpass123', full_name='Alice',
        )
        self.alice.ratings.create(movie=self.movie, value=9)
        self.movie.refresh_from_db()

    def test_movie_meta_and_related_shown(self):
        body = self.client.get(reverse('movie_detail', kwargs={'slug': 'great-film'})).content.decode('utf-8', 'ignore')
        self.assertIn('12+', body)
        self.assertIn('Inglizcha', body)
        self.assertIn('$100.0M', body)
        self.assertIn('Shunga o\'xshash filmlar', body)
        self.assertIn('Other Film', body)

    def test_movie_shows_credits(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        great = Movie.objects.get(slug='great-film')
        great.poster = SimpleUploadedFile('poster.jpg', b'\x00' * 64, content_type='image/jpeg')
        great.save()
        body = self.client.get(reverse('movie_detail', kwargs={'slug': 'great-film'})).content.decode('utf-8', 'ignore')
        self.assertIn('Aktyorlar va jamoa', body)
        self.assertIn('John Actor', body)
        self.assertIn('Hero', body)
        self.assertIn('Jane Director', body)
        self.assertIn('cast-row', body)
        self.assertIn('detail-backdrop', body)

    def test_person_page(self):
        body = self.client.get(reverse('person_detail', kwargs={'slug': 'john-actor'})).content.decode('utf-8', 'ignore')
        self.assertIn('John Actor', body)
        self.assertIn('Great Film', body)
        self.assertIn('Filmografiya', body)

    def test_watchlist_requires_login(self):
        response = self.client.post(reverse('toggle_watchlist', kwargs={'slug': 'great-film'}))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.headers['Location'])
        self.assertEqual(WatchlistItem.objects.count(), 0)

    def test_watchlist_toggle_add_remove(self):
        self.client.force_login(self.alice)
        self.client.post(reverse('toggle_watchlist', kwargs={'slug': 'great-film'}))
        self.assertTrue(WatchlistItem.objects.filter(user=self.alice, movie=self.movie).exists())
        body = self.client.get(reverse('profile')).content.decode('utf-8', 'ignore')
        self.assertIn('Great Film', body)
        self.client.post(reverse('toggle_watchlist', kwargs={'slug': 'great-film'}))
        self.assertFalse(WatchlistItem.objects.filter(user=self.alice, movie=self.movie).exists())

    def test_review_short_rejected(self):
        self.client.force_login(self.alice)
        self.client.post(reverse('add_review', kwargs={'slug': 'great-film'}), {'text': 'qisqa'})
        self.assertFalse(MovieReview.objects.exists())

    def test_review_create_and_update(self):
        self.client.force_login(self.alice)
        self.client.post(reverse('add_review', kwargs={'slug': 'great-film'}), {'text': 'Zo\'r film, tavsiya qilaman!'})
        review = MovieReview.objects.get(movie=self.movie, user=self.alice)
        self.assertIn('Zo\'r', review.text)
        self.client.post(reverse('add_review', kwargs={'slug': 'great-film'}), {'text': 'Yangi fikr, juda yaxshi chiqdi'})
        review.refresh_from_db()
        self.assertEqual(review.text, 'Yangi fikr, juda yaxshi chiqdi')
        self.assertEqual(MovieReview.objects.filter(movie=self.movie).count(), 1)
        body = self.client.get(reverse('movie_detail', kwargs={'slug': 'great-film'})).content.decode('utf-8', 'ignore')
        self.assertIn('Yangi fikr', body)

    def test_reviews_paginated_on_detail(self):
        for i in range(11):
            MovieReview.objects.create(
                movie=self.movie,
                user=User.objects.create_user(
                    phone_number=f'+9989014440{i:02d}', password='testpass123',
                    full_name=f'Sharhchi {i}',
                ),
                text=f'Paginatsiya fikri {i}',
            )
        page1 = self.client.get(reverse('movie_detail', kwargs={'slug': 'great-film'})).content.decode('utf-8', 'ignore')
        self.assertIn('Paginatsiya fikri 10', page1)
        self.assertNotIn('Paginatsiya fikri 0', page1)
        self.assertIn('Sharhlar (11)', page1)
        page2 = self.client.get(
            reverse('movie_detail', kwargs={'slug': 'great-film'}) + '?reviews_page=2'
        ).content.decode('utf-8', 'ignore')
        self.assertIn('Paginatsiya fikri 0', page2)
        self.assertNotIn('Paginatsiya fikri 10', page2)

    def test_top_scored_movies_ranked_on_leaderboard(self):
        self.alice.ratings.create(movie=self.other, value=10)
        self.other.refresh_from_db()
        body = self.client.get(reverse('leaderboard')).content.decode('utf-8', 'ignore')
        self.assertIn('Liderlar', body)
        self.assertLess(body.index('Other Film'), body.index('Great Film'))
        self.assertIn('podium-col', body)
        body = self.client.get(reverse('index')).content.decode('utf-8', 'ignore')
        self.assertIn('Other Film', body)


class LeaderboardPaginationTests(TestCase):
    def setUp(self):
        self.genre = Genre.objects.create(name='Drama', slug='drama')
        self.user = User.objects.create_user(
            phone_number='+998901555555', password='testpass123', full_name='LB User',
        )
        for i in range(25):
            movie = Movie.objects.create(
                title=f'LB Film {i + 1:02d}', slug=f'lb-film-{i + 1:02d}', description='Tavsif',
                release_date=date(2020, 1, 1), duration_minutes=90, status='published',
                views_count=i,
            )
            movie.genres.add(self.genre)
            self.user.ratings.create(movie=movie, value=max(1, i % 10))

    def test_leaderboard_page1_podium_plus_rows(self):
        body = self.client.get(reverse('leaderboard')).content.decode('utf-8', 'ignore')
        self.assertEqual(body.count('class="lb-row"'), 17)
        self.assertEqual(body.count('podium-col'), 3)

    def test_leaderboard_page2_keeps_all_movies_with_ranks(self):
        body = self.client.get(reverse('leaderboard') + '?page=2').content.decode('utf-8', 'ignore')
        self.assertEqual(body.count('class="lb-row"'), 5)
        self.assertNotIn('podium-col', body)
        self.assertIn('LB Film 21', body)
        self.assertIn('LB Film 01', body)
        self.assertIn('lb-rank">21<', body)
        self.assertIn('lb-rank">25<', body)


class SeoTests(TestCase):
    def setUp(self):
        self.movie = Movie.objects.create(
            title='SEO Film', slug='seo-film', description='Tavsif',
            release_date=date(2019, 1, 1), duration_minutes=100,
            status='published',
        )
        self.person = Person.objects.create(full_name='SEO Actor', slug='seo-actor')

    def test_sitemap_contains_movies_and_people(self):
        body = self.client.get('/sitemap.xml').content.decode('utf-8')
        self.assertIn('/film/seo-film/', body)
        self.assertIn('/person/seo-actor/', body)
        self.assertIn('/leaderboard/', body)

    def test_robots_txt(self):
        body = self.client.get('/robots.txt').content.decode('utf-8')
        self.assertIn('Sitemap:', body)

    def test_detail_meta_tags(self):
        body = self.client.get(reverse('movie_detail', kwargs={'slug': 'seo-film'})).content.decode('utf-8', 'ignore')
        self.assertIn('meta name="description"', body)
        self.assertIn('og:title', body)


class ProfileEditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='+998901444444', password='testpass123', full_name='Avvalgi',
        )

    def test_profile_edit(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('profile_edit'), {
            'full_name': 'Yangi Ism',
            'email': 'new@mail.uz',
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, 'Yangi Ism')

    def test_password_change(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('password_change'), {
            'old_password': 'testpass123',
            'new_password1': 'yaxshi_parol_12345',
            'new_password2': 'yaxshi_parol_12345',
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('yaxshi_parol_12345'))

    def test_password_change_wrong_old(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('password_change'), {
            'old_password': 'noto_gri',
            'new_password1': 'yaxshi_parol_12345',
            'new_password2': 'yaxshi_parol_12345',
        })
        self.assertEqual(response.status_code, 200)


class SeedCommandTests(TestCase):
    def test_seed_catalog_idempotent(self):
        import tempfile

        from django.core.management import call_command
        from django.test import override_settings

        from apps.models import Movie
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp, override_settings(MEDIA_ROOT=tmp):
            call_command('seed_catalog')
            first = Movie.objects.count()
            call_command('seed_catalog')
            self.assertEqual(Movie.objects.count(), first)
            self.assertGreaterEqual(first, 40)
            self.assertTrue(all(m.poster for m in Movie.objects.filter(status='published')))


class AdminTrailerUploadTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            phone_number='+998901000088', password='adminpass123', full_name='Admin Test',
        )
        self.client.force_login(self.admin_user)

    def test_admin_trailer_upload_sets_video_url(self):
        import tempfile
        from pathlib import Path

        from django.core.files.storage import FileSystemStorage
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.admin import MovieAdminForm

        old_storage = MovieAdminForm.storage
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            MovieAdminForm.storage = FileSystemStorage(
                location=str(Path(tmp)), base_url='media/',
            )
            try:
                payload = SimpleUploadedFile('trailer_test.mp4', b'\x00' * 64, content_type='video/mp4')
                response = self.client.post(reverse('admin:apps_movie_add'), {
                    'title': 'Upload Film',
                    'slug': 'upload-film',
                    'description': 'Tavsif',
                    'release_date': '2020-01-01',
                    'duration_minutes': '100',
                    'status': 'published',
                    'views_count': '0',
                    'trailer_upload': payload,
                    'credits-TOTAL_FORMS': '0',
                    'credits-INITIAL_FORMS': '0',
                    'credits-MIN_NUM_FORMS': '0',
                    'credits-MAX_NUM_FORMS': '1000',
                    'ratings-TOTAL_FORMS': '0',
                    'ratings-INITIAL_FORMS': '0',
                    'ratings-MIN_NUM_FORMS': '0',
                    'ratings-MAX_NUM_FORMS': '1000',
                })
                self.assertEqual(response.status_code, 302)
                movie = Movie.objects.get(slug='upload-film')
                self.assertEqual(movie.video_url, '/media/trailers/trailer_test.mp4')
            finally:
                MovieAdminForm.storage = old_storage

    def test_admin_rejects_bad_video_extension(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        payload = SimpleUploadedFile('trailer.exe', b'\x00' * 64, content_type='application/octet-stream')
        response = self.client.post(reverse('admin:apps_movie_add'), {
            'title': 'Bad Film',
            'slug': 'bad-film',
            'description': 'Tavsif',
            'release_date': '2020-01-01',
            'duration_minutes': '100',
            'status': 'published',
            'views_count': '0',
            'trailer_upload': payload,
            'credits-TOTAL_FORMS': '0',
            'credits-INITIAL_FORMS': '0',
            'credits-MIN_NUM_FORMS': '0',
            'credits-MAX_NUM_FORMS': '1000',
            'ratings-TOTAL_FORMS': '0',
            'ratings-INITIAL_FORMS': '0',
            'ratings-MIN_NUM_FORMS': '0',
            'ratings-MAX_NUM_FORMS': '1000',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Movie.objects.filter(slug='bad-film').exists())

    def test_admin_cleans_whitespace_video_url(self):
        from apps.admin import MovieAdminForm

        form = MovieAdminForm(data={
            'title': 'Trim Test', 'slug': 'trim-test', 'description': 'Tavsif',
            'release_date': '2020-01-01', 'duration_minutes': '100',
            'status': 'published', 'views_count': '0', 'rating_count': '0',
            'video_url': '   ',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data['video_url'])


class SecurityHeadersTests(TestCase):
    def test_security_headers_present(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.headers['Permissions-Policy'],
                         'camera=(), microphone=(), geolocation=(), payment=(), usb=()')
        self.assertEqual(response.headers['Cross-Origin-Resource-Policy'], 'same-origin')
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response.headers['X-Frame-Options'], 'DENY')

    def test_admin_page_has_noindex_robots_tag(self):
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 302)  # login bo'lmagan → redirect
        response = self.client.get('/admin/login/')
        self.assertEqual(response.headers.get('X-Robots-Tag'), 'noindex, nofollow')


class RateLimitTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.user = User.objects.create_user(
            phone_number='+998901000077', password='pass12345', full_name='Rate Test',
        )
        self.movie = Movie.objects.create(
            title='Rate Film', slug='rate-film', description='Tavsif',
            release_date=date(2019, 1, 1), duration_minutes=90, status='published',
        )

    def _rate_post(self, value, is_ajax=False):
        kwargs = {'REMOTE_ADDR': '203.0.113.77'}
        if is_ajax:
            kwargs['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        return self.client.post(
            reverse('rate_movie', kwargs={'slug': 'rate-film'}),
            {'value': value},
            **kwargs,
        )

    def test_interactive_posts_rate_limited_ajax(self):
        self.client.force_login(self.user)
        for _ in range(30):
            response = self._rate_post('8', is_ajax=True)
            self.assertEqual(response.status_code, 200)
        response = self._rate_post('8', is_ajax=True)
        self.assertEqual(response.status_code, 429)

    def test_interactive_posts_rate_limited_redirect(self):
        self.client.force_login(self.user)
        for _ in range(30):
            self._rate_post('7')
        response = self._rate_post('7')
        self.assertEqual(response.status_code, 302)


