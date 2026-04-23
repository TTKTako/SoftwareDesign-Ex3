from django.urls import path

from . import views

app_name = "music"

urlpatterns = [
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
    # Library — list all songs for the logged-in user (FR-3.3)
    path("library/", views.library_view, name="library"),

    # Song generation entry point — Strategy Pattern (FR-2.1–2.5)
    path("songs/generate/", views.generate_song_view, name="generate_song"),

    # Song detail
    path("songs/<int:pk>/", views.song_detail_view, name="song_detail"),

    # Delete a song to free library space (FR-3.4)
    path("songs/<int:pk>/delete/", views.delete_song_view, name="delete_song"),

    # Share — generate unique public URL (FR-5.2)
    path("songs/<int:pk>/share/", views.create_shared_link_view, name="create_shared_link"),

    # Download — retrieve audio file URL (FR-5.1)
    path("songs/<int:pk>/download/", views.download_song_view, name="download_song"),

    # Generation status polling (Strategy Pattern)
    path("songs/<int:pk>/generation-status/", views.generation_status_view, name="generation_status"),

    # Shared link public page — metadata only for guests, audio for auth users (FR-5.3)
    path("share/<uuid:token>/", views.shared_link_view, name="shared_link"),
]
