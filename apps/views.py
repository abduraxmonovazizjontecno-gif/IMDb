import logging

from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from apps.forms import ProfileForm, RatingForm, RegisterForm
from apps.models import Credit, Genre, Movie, MovieRating, MovieReview, Person, User, WatchlistItem
from apps.utils import rate_limit_exceeded, rate_limit_reset

BOT_UA_MARKERS = ('bot', 'spider', 'crawler', 'slurp', 'bingpreview', 'petalbot', 'yandex', 'googlebot')
LOGIN_RATE_KEY = 'login'
REGISTER_RATE_KEY = 'register'
INTERACT_RATE_KEY = 'interact'
INTERACT_RATE_LIMIT = 30
INTERACT_RATE_WINDOW = 60

logger = logging.getLogger(__name__)


def _rate_limited(request, is_ajax):
    """Interaktiv amallar uchun umumiy spam himoyasi (IP asosida, daqiqada 30 marta).

    Qaytaradi: blok bo'lsa — javob (Response), aks holda None.
    """
    if rate_limit_exceeded(request, INTERACT_RATE_KEY, limit=INTERACT_RATE_LIMIT, window=INTERACT_RATE_WINDOW):
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'Juda tez harakat qilyapsiz. Biroz kuting.'}, status=429)
        messages.error(request, 'Juda tez harakat qilyapsiz. Biraz sabr qiling.')
        kwargs = getattr(request.resolver_match, 'kwargs', {}) or {}
        slug = kwargs.get('slug')
        if slug:
            return redirect(reverse('movie_detail', kwargs={'slug': slug}))
        return redirect('index')
    return None


def _redirect_after_post(request, view_name, kwargs=None):
    """Xavfsiz keyingi manzilga qaytaradi (faqat shu sayt ichidagi URL)."""
    kwargs = kwargs or {}
    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return HttpResponseRedirect(next_url)
    return redirect(reverse(view_name, kwargs=kwargs))


def _require_login_or_redirect(request, slug):
    """Unauthenticated foydalanuvchini login sahifasiga yuboradi."""
    next_url = reverse('movie_detail', kwargs={'slug': slug})
    if url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(f"{reverse('login')}?next={next_url}")
    return redirect('login')


class IndexView(ListView):
    model = Movie
    template_name = 'index.html'
    context_object_name = 'movies'
    paginate_by = 12

    def get_queryset(self):
        movies = Movie.objects.filter(status='published').prefetch_related('genres')
        q = self.request.GET.get('q')
        genre = self.request.GET.get('genre')
        year = self.request.GET.get('year')
        sort = self.request.GET.get('sort', '')
        if q:
            q = q.strip()
            movies = movies.filter(
                Q(title__icontains=q)
                | Q(search_text__icontains=q)
                | Q(genres__name__icontains=q)
                | Q(credits__person__full_name__icontains=q)
            ).distinct()
        if genre:
            movies = movies.filter(genres__slug=genre)
        if year:
            movies = movies.filter(release_date__year=year)
        if sort == 'new':
            movies = movies.order_by('-release_date')
        elif sort == 'old':
            movies = movies.order_by('release_date')
        elif sort == 'title':
            movies = movies.order_by('title')
        return movies

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.core.cache import cache

        context['trending'] = (
            Movie.objects.filter(status='published', rating__isnull=False)
            .order_by('-rating', '-rating_count', '-views_count')
            .prefetch_related('genres')[:4]
        )
        context['banners'] = (
            Movie.objects.filter(status='published')
            .exclude(poster__isnull=True)
            .exclude(poster='')
            .order_by('-release_date')
            .prefetch_related('genres')[:5]
        )
        context['genres'] = cache.get_or_set('genres_list', lambda: list(Genre.objects.all()), 3600)
        context['q'] = self.request.GET.get('q', '')
        context['selected_genre'] = self.request.GET.get('genre', '')
        context['selected_year'] = self.request.GET.get('year', '')
        context['selected_sort'] = self.request.GET.get('sort', '')
        context['years'] = cache.get_or_set(
            'years_list',
            lambda: list(Movie.objects.filter(status='published').dates('release_date', 'year', order='DESC')),
            3600
        )
        context['top_rated'] = (
            Movie.objects.filter(status='published', rating__isnull=False)
            .order_by('-rating', '-rating_count')[:3]
        )
        return context


class SearchView(IndexView):
    template_name = 'search.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.pop('trending', None)
        context.pop('top_rated', None)
        return context


class MovieDetailView(DetailView):
    model = Movie
    template_name = 'movie_detail.html'
    context_object_name = 'movie'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return (
            Movie.objects.filter(status='published')
            .prefetch_related('genres', 'credits__person')
        )

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        ua = request.META.get('HTTP_USER_AGENT', '').lower()
        is_bot = any(marker in ua for marker in BOT_UA_MARKERS)
        session_key = f'viewed_{self.object.pk}'
        if not is_bot and not request.session.get(session_key):
            Movie.objects.filter(pk=self.object.pk).update(views_count=F('views_count') + 1)
            request.session[session_key] = True
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['range10'] = range(1, 11)
        context['user_rating'] = None
        context['user_review'] = None
        context['in_watchlist'] = False

        if self.request.user.is_authenticated:
            rating = self.object.ratings.filter(user=self.request.user).first()
            context['user_rating'] = rating.value if rating else None
            context['user_review'] = self.object.reviews.filter(user=self.request.user).first()
            context['in_watchlist'] = self.object.watchlist_items.filter(user=self.request.user).exists()

        paginator = Paginator(
            self.object.reviews.select_related('user').order_by('-created_at'),
            10,
        )
        try:
            page = int(self.request.GET.get('reviews_page', 1))
        except (ValueError, TypeError):
            page = 1
        context['reviews_page'] = paginator.get_page(page)
        context['review_count'] = paginator.count

        credits = list(self.object.credits.select_related('person'))
        context['actor_names'] = [c.person.full_name for c in credits if c.role == Credit.Role.ACTOR]
        context['credit_groups'] = [
            (role.label, [c for c in credits if c.role == role.value])
            for role in Credit.Role
            if any(c.role == role.value for c in credits)
        ]
        context['related'] = (
            Movie.objects.filter(
                status='published',
                genres__in=self.object.genres.all(),
            )
            .exclude(pk=self.object.pk)
            .prefetch_related('genres')
            .distinct()
            .order_by(F('rating').desc(nulls_last=True), '-rating_count', '-views_count')[:6]
        )
        return context


class PersonDetailView(DetailView):
    model = Person
    template_name = 'person.html'
    context_object_name = 'person'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        credits = list(
            self.object.credits.select_related('movie')
            .filter(movie__status='published')
            .order_by('-movie__rating')
        )
        context['credit_groups'] = [
            (role.label, [c for c in credits if c.role == role.value])
            for role in Credit.Role
            if any(c.role == role.value for c in credits)
        ]
        context['known_for'] = credits[:4]
        return context


class RateMovieView(View):
    def post(self, request, slug):
        movie = get_object_or_404(Movie, slug=slug, status='published')
        if not request.user.is_authenticated:
            return _require_login_or_redirect(request, slug)
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        blocked = _rate_limited(request, is_ajax)
        if blocked:
            return blocked
        form = RatingForm(request.POST)
        if form.is_valid():
            _, created = MovieRating.objects.update_or_create(
                movie=movie,
                user=request.user,
                defaults={'value': form.cleaned_data['value']},
            )
            movie.refresh_from_db()
            if created:
                messages.success(request, 'Bahoyingiz saqlandi. Rahmat!')
            else:
                messages.success(request, 'Bahoyingiz yangilandi.')
            if is_ajax:
                return JsonResponse({
                    'ok': True,
                    'value': form.cleaned_data['value'],
                    'rating': movie.rating,
                    'rating_count': movie.rating_count,
                })
        elif is_ajax:
            return JsonResponse({'ok': False, 'error': 'Baholash oralig\'i 1-10.'}, status=400)
        else:
            messages.error(request, 'Baholash oralig\'i 1-10 bo\'lishi kerak.')
        return _redirect_after_post(request, 'movie_detail', kwargs={'slug': slug})


class WatchlistToggleView(View):
    def post(self, request, slug):
        movie = get_object_or_404(Movie, slug=slug, status='published')
        if not request.user.is_authenticated:
            return _require_login_or_redirect(request, slug)
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        blocked = _rate_limited(request, is_ajax)
        if blocked:
            return blocked
        item, created = WatchlistItem.objects.get_or_create(user=request.user, movie=movie)
        if created:
            messages.success(request, 'Ro\'yxatga qo\'shildi.')
            added = True
        else:
            item.delete()
            messages.info(request, 'Ro\'yxatdan olib tashlandi.')
            added = False
        if is_ajax:
            return JsonResponse({'ok': True, 'in_list': added})
        return _redirect_after_post(request, 'movie_detail', kwargs={'slug': slug})


class ReviewView(View):
    def post(self, request, slug):
        movie = get_object_or_404(Movie, slug=slug, status='published')
        if not request.user.is_authenticated:
            return _require_login_or_redirect(request, slug)
        blocked = _rate_limited(request, False)
        if blocked:
            return blocked
        text = request.POST.get('text', '').strip()
        if len(text) < 10:
            messages.error(request, 'Sharh kamida 10 belgidan iborat bo\'lishi kerak.')
            return _redirect_after_post(request, 'movie_detail', kwargs={'slug': slug})
        _, created = MovieReview.objects.update_or_create(
            movie=movie,
            user=request.user,
            defaults={'text': text[:2000]},
        )
        if created:
            messages.success(request, 'Sharhingiz e\'lon qilindi.')
        else:
            messages.success(request, 'Sharhingiz yangilandi.')
        return _redirect_after_post(request, 'movie_detail', kwargs={'slug': slug})


class LeaderboardView(ListView):
    model = Movie
    template_name = 'leaderboard.html'
    context_object_name = 'movies'
    paginate_by = 20
    queryset = (
        Movie.objects.filter(status='published', rating__isnull=False)
        .order_by('-rating', '-rating_count', '-views_count')
    )


class SiteLoginView(LoginView):
    template_name = 'login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        rate_limit_reset(self.request, LOGIN_RATE_KEY)
        messages.success(self.request, 'Xush kelibsiz!')
        return super().form_valid(form)

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if rate_limit_exceeded(self.request, LOGIN_RATE_KEY):
            messages.error(self.request, 'Juda ko\'p urinish. 5 daqiqadan so\'ng qayta urinib ko\'ring.')
            response.status_code = 429
        return response


class SiteLogoutView(LogoutView):
    next_page = 'index'

    def post(self, request, *args, **kwargs):
        messages.success(request, 'Hisobingizdan chiqdingiz. Xayr!')
        return super().post(request, *args, **kwargs)


class RegisterView(CreateView):
    form_class = RegisterForm
    template_name = 'register.html'
    success_url = reverse_lazy('index')

    def form_valid(self, form):
        user = form.save()
        rate_limit_reset(self.request, REGISTER_RATE_KEY)
        login(self.request, user)
        messages.success(self.request, 'Hisob yaratildi. Xush kelibsiz!')
        return redirect(self.success_url)

    def form_invalid(self, form):
        if rate_limit_exceeded(self.request, REGISTER_RATE_KEY):
            messages.error(self.request, 'Juda ko\'p urinish. 5 daqiqadan so\'ng qayta urinib ko\'ring.')
            return redirect('register')
        return super().form_invalid(form)


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ratings'] = (
            self.request.user.ratings.select_related('movie').order_by('-updated_at')
        )
        context['watchlist'] = (
            self.request.user.watchlist.select_related('movie').order_by('-created_at')
        )
        return context


class ProfileEditView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = ProfileForm
    template_name = 'profile_edit.html'
    success_url = reverse_lazy('profile')

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, 'Profil yangilandi.')
        return super().form_valid(form)


class SitePasswordChangeView(PasswordChangeView):
    template_name = 'registration/password_change_form.html'
    success_url = reverse_lazy('password_change_done')

    def form_valid(self, form):
        messages.success(self.request, 'Parolingiz o\'zgartirildi.')
        return super().form_valid(form)


class TelegramVideoView(View):
    """tg://<file_path> saqlangan videoni bot tokenisiz oqimlaydi (Range bilan).

    video_url ga FAQAT 'tg://' shaklida yoziladi (masalan tg://documents/video.mp4);
    haqiqiy fayl havolasi (token bilan) hech qachon brauzerga chiqmaydi.
    """

    def get(self, request, slug):
        movie = get_object_or_404(Movie, slug=slug, status='published')
        path = movie.video_url or ''
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if not path.startswith('tg://') or not token:
            raise Http404
        if rate_limit_exceeded(request, 'tg_video', limit=60, window=60):
            return HttpResponse(status=429)
        url = f'https://api.telegram.org/file/bot{token}/{path[5:]}'
        try:
            return self._proxy(request, url)
        except Http404:
            raise
        except Exception:
            logger.exception('Telegram video proxy failed for slug=%s', slug)
            raise Http404 from None

    @staticmethod
    def _proxy(request, url):
        import urllib.error
        import urllib.request

        headers = {'User-Agent': 'Mozilla/5.0'}
        if request.headers.get('Range'):
            headers['Range'] = request.headers['Range']
        try:
            upstream = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60)
        except urllib.error.HTTPError as exc:
            raise Http404 from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise Http404 from exc

        response_headers = {}
        for name in ('Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges'):
            if upstream.headers.get(name):
                response_headers[name] = upstream.headers[name]
        response_headers.setdefault('Content-Type', 'video/mp4')
        status = 206 if request.headers.get('Range') else 200

        def generator():
            try:
                while True:
                    chunk = upstream.read(512 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                upstream.close()

        return StreamingHttpResponse(generator(), status=status, headers=response_headers)
