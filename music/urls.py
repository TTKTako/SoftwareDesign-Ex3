from django.urls import path

from . import views

app_name = "music"

urlpatterns = [
    # ---------------------------------------------------------------------------
    # Main SPA entry point (FR-1.4 — redirect unauthenticated → login)
    # ---------------------------------------------------------------------------
    path("", views.app_view, name="app"),

    # ---------------------------------------------------------------------------
    # Authentication — local register / login / logout (FR-1.1, FR-1.3)
    # Google OAuth is handled by allauth headless at /_allauth/browser/v1/
    # ---------------------------------------------------------------------------
    path("auth/register/", views.register_view, name="register"),
    path("auth/login/",    views.login_view,    name="login"),
    path("auth/logout/",   views.logout_view,   name="logout"),

    # ---------------------------------------------------------------------------
    # Library & songs
    # ---------------------------------------------------------------------------
    path("library/",     views.library_view,     name="library"),       # HTML page
    path("library/api/", views.library_api_view,  name="library_api"),  # JSON data
    path("songs/generate/", views.generate_song_view, name="generate_song"),
    path("songs/<int:pk>/", views.song_detail_view, name="song_detail"),
    path("songs/<int:pk>/delete/", views.delete_song_view, name="delete_song"),
    path("songs/<int:pk>/share/", views.create_shared_link_view, name="create_shared_link"),
    path("songs/<int:pk>/download/", views.download_song_view, name="download_song"),
    path("songs/<int:pk>/generation-status/", views.generation_status_view, name="generation_status"),
    path("suno/callback/", views.suno_callback_view, name="suno_callback"),
    path("share/<uuid:token>/", views.shared_link_view, name="shared_link"),
]
