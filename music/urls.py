from django.urls import path

from . import views

app_name = "music"

urlpatterns = [
    # Library – list all songs for the logged-in user
    path("library/", views.library_view, name="library"),
    # Song detail
    path("songs/<int:pk>/", views.song_detail_view, name="song_detail"),
    # Shared link public page (metadata only for guests, audio for auth users)
    path("share/<uuid:token>/", views.shared_link_view, name="shared_link"),
]
