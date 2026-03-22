from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render

from .models import Library, SharedLink, Song


# ---------------------------------------------------------------------------
# Library view — READ (list all songs for the authenticated user)
# ---------------------------------------------------------------------------

@login_required
def library_view(request):
    """Return the authenticated user's library and song list as JSON."""
    library, _ = Library.objects.get_or_create(owner=request.user)
    songs = library.songs.filter(status=Song.STATUS_COMPLETED).select_related("metadata")
    data = {
        "owner": request.user.username,
        "song_count": songs.count(),
        "is_full": library.is_full,
        "songs": [
            {
                "id": s.pk,
                "title": s.metadata.title if hasattr(s, "metadata") else "(untitled)",
                "status": s.status,
                "is_private": s.is_private,
                "created_at": s.created_at.isoformat(),
            }
            for s in songs
        ],
    }
    return JsonResponse(data)


# ---------------------------------------------------------------------------
# Song detail view — READ (single song, owner only)
# ---------------------------------------------------------------------------

@login_required
def song_detail_view(request, pk):
    """Return full details for a song owned by the authenticated user."""
    song = get_object_or_404(Song, pk=pk, library__owner=request.user)
    data = {
        "id": song.pk,
        "status": song.status,
        "is_private": song.is_private,
        "created_at": song.created_at.isoformat(),
    }
    if hasattr(song, "metadata"):
        m = song.metadata
        data["metadata"] = {
            "title": m.title,
            "mood": m.mood,
            "theme": m.theme,
            "occasion": m.occasion,
            "duration": str(m.duration) if m.duration else None,
        }
    if hasattr(song, "voice_style"):
        data["voice_style"] = song.voice_style.style
    if hasattr(song, "lyrics"):
        data["lyrics"] = {
            "mode": song.lyrics.mode,
            "content": song.lyrics.content,
        }
    return JsonResponse(data)


# ---------------------------------------------------------------------------
# Shared link view — READ (metadata for all, audio only for authenticated)
# ---------------------------------------------------------------------------

def shared_link_view(request, token):
    """
    Public page for a shared song link.
    - Guests: see metadata only.
    - Authenticated users: see metadata + audio file URL.
    FR-5.3: must require login to stream audio.
    """
    link = get_object_or_404(SharedLink, token=token)
    song = link.song

    if song.is_private and not (
        request.user.is_authenticated and song.library.owner == request.user
    ):
        # A private song with no shared-link access for this visitor
        raise Http404("Song not found.")

    data: dict = {}
    if hasattr(song, "metadata"):
        m = song.metadata
        data["title"] = m.title
        data["mood"] = m.mood
        data["theme"] = m.theme
        data["occasion"] = m.occasion

    if request.user.is_authenticated:
        # Authenticated users can receive the audio URL
        data["audio_url"] = (
            song.audio_file.url if song.audio_file else None
        )
    else:
        data["audio_url"] = None
        data["message"] = "Log in to listen to this track."

    return JsonResponse(data)
