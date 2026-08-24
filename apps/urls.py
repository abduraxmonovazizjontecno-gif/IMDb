from django.contrib.auth.views import (
    PasswordChangeDoneView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.urls import path

from apps.views import (
    IndexView,
    LeaderboardView,
    MovieDetailView,
    PersonDetailView,
    ProfileEditView,
    ProfileView,
    RateMovieView,
    RegisterView,
    ReviewView,
    SearchView,
    SiteLoginView,
    SiteLogoutView,
    SitePasswordChangeView,
    TelegramVideoView,
    WatchlistToggleView,
)

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('search/', SearchView.as_view(), name='search'),
    path('film/<slug:slug>/', MovieDetailView.as_view(), name='movie_detail'),
    path('film/<slug:slug>/tg-video/', TelegramVideoView.as_view(), name='movie_tg_video'),
    path('film/<slug:slug>/rate/', RateMovieView.as_view(), name='rate_movie'),
    path('film/<slug:slug>/watchlist/', WatchlistToggleView.as_view(), name='toggle_watchlist'),
    path('film/<slug:slug>/review/', ReviewView.as_view(), name='add_review'),
    path('person/<slug:slug>/', PersonDetailView.as_view(), name='person_detail'),
    path('leaderboard/', LeaderboardView.as_view(), name='leaderboard'),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', SiteLoginView.as_view(), name='login'),
    path('logout/', SiteLogoutView.as_view(), name='logout'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/edit/', ProfileEditView.as_view(), name='profile_edit'),
    path('password-change/', SitePasswordChangeView.as_view(), name='password_change'),
    path(
        'password-change/done/',
        PasswordChangeDoneView.as_view(template_name='registration/password_change_done.html'),
        name='password_change_done',
    ),
    path(
        'password-reset/',
        PasswordResetView.as_view(template_name='registration/password_reset_form.html'),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'),
        name='password_reset_complete',
    ),
]
