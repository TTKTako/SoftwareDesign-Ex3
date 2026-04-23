from django.urls import path

from . import views

app_name = "music"

urlpatterns = [
    # Library – list all songs for the logged-in user
    path("library/", views.library_view, name="library"),
    # Song detail
    path("songs/<int:pk>/", views.song_detail_view, name="song_detail"),
    # Song generation (Strategy Pattern entry point)
    path("songs/generate/", views.generate_song_view, name="generate_song"),
    # Generation status polling
    path("songs/<int:pk>/generation-status/", views.generation_status_view, name="generation_status"),
    # Shared link public page (metadata only for guests, audio for auth users)
    path("share/<uuid:token>/", views.shared_link_view, name="shared_link"),
]
