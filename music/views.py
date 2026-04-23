import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from .generation import SongGenerationRequest, get_generator_strategy
from .models import GenerationJob, Library, Lyrics, Metadata, SharedLink, Song, VoiceStyle


# ---------------------------------------------------------------------------
# Library view — READ (list all songs for the authenticated user)
# ---------------------------------------------------------------------------

@login_required
def library_view(request):
    """Return the authenticated user's library and song list as JSON."""
    library, _ = Library.objects.get_or_create(owner=request.user)
    songs = library.songs.filter(status=Song.Status.COMPLETED).select_related("metadata")
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


# ---------------------------------------------------------------------------
# Song generation — CREATE + TRIGGER (Strategy Pattern entry point)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def generate_song_view(request):
    """
    POST /songs/generate/

    Accepts a JSON body describing the song to generate.  Creates the Song
    and all composition records, then delegates to the active generation
    strategy (mock or suno) to kick off the task.

    Request body (all fields except ``title`` are optional):
    {
        "title":         "My Song",
        "mood":          "happy",          // Metadata.Mood choices
        "theme":         "A rainy evening",
        "occasion":      "general",        // Metadata.Occasion choices
        "voice_style":   "female",         // VoiceStyle.Style choices
        "lyrics_mode":   "ai_generated",   // Lyrics.Mode choices
        "lyrics_content": ""              // required only when mode=custom
    }
    """
    try:
        body: dict = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)

    title: str = body.get("title", "").strip()
    if not title:
        return JsonResponse({"error": "'title' is required."}, status=400)

    library, _ = Library.objects.get_or_create(owner=request.user)
    if library.is_full:
        return JsonResponse(
            {"error": "Library limit reached: a library cannot hold more than 20 songs."},
            status=400,
        )

    # --- Validate enumerated fields against model choices ---
    mood = body.get("mood", Metadata.Mood.CALM)
    if mood not in Metadata.Mood.values:
        return JsonResponse({"error": f"Invalid mood '{mood}'."}, status=400)

    occasion = body.get("occasion", Metadata.Occasion.GENERAL)
    if occasion not in Metadata.Occasion.values:
        return JsonResponse({"error": f"Invalid occasion '{occasion}'."}, status=400)

    voice_style = body.get("voice_style", VoiceStyle.Style.FEMALE)
    if voice_style not in VoiceStyle.Style.values:
        return JsonResponse({"error": f"Invalid voice_style '{voice_style}'."}, status=400)

    lyrics_mode = body.get("lyrics_mode", Lyrics.Mode.AI_GENERATED)
    if lyrics_mode not in Lyrics.Mode.values:
        return JsonResponse({"error": f"Invalid lyrics_mode '{lyrics_mode}'."}, status=400)

    lyrics_content: str = body.get("lyrics_content", "")
    theme: str = body.get("theme", "")

    # --- Persist domain objects ---
    song = Song.objects.create(library=library, status=Song.Status.PENDING)
    Metadata.objects.create(
        song=song,
        title=title,
        mood=mood,
        theme=theme,
        occasion=occasion,
    )
    VoiceStyle.objects.create(song=song, style=voice_style)
    Lyrics.objects.create(song=song, mode=lyrics_mode, content=lyrics_content)

    # --- Build generation request and invoke strategy ---
    gen_request = SongGenerationRequest(
        song_id=song.pk,
        title=title,
        prompt=theme,
        style=voice_style,
        lyrics=lyrics_content,
        instrumental=(lyrics_mode == Lyrics.Mode.INSTRUMENTAL),
    )

    strategy_name: str = getattr(settings, "GENERATOR_STRATEGY", "mock").lower()
    try:
        strategy = get_generator_strategy(strategy_name)
    except ValueError as exc:
        song.status = Song.Status.FAILED
        song.save()
        return JsonResponse({"error": str(exc)}, status=500)

    result = strategy.generate(gen_request)

    # --- Persist job record ---
    job = GenerationJob.objects.create(
        song=song,
        task_id=result.task_id,
        strategy=strategy_name,
        status=result.status,
        audio_url=result.audio_url,
        error_message=result.error,
    )

    # --- Sync Song.status with the initial result ---
    if result.status == "SUCCESS":
        song.status = Song.Status.COMPLETED
    elif result.status == "FAILED":
        song.status = Song.Status.FAILED
    else:
        song.status = Song.Status.GENERATING
    song.save()

    return JsonResponse(
        {
            "song_id": song.pk,
            "task_id": job.task_id,
            "status": job.status,
            "audio_url": job.audio_url or None,
            "error": job.error_message or None,
            "strategy": strategy_name,
        },
        status=201,
    )


# ---------------------------------------------------------------------------
# Generation status — POLL (Strategy Pattern: get_status)
# ---------------------------------------------------------------------------

@login_required
def generation_status_view(request, pk):
    """
    GET /songs/<pk>/generation-status/

    Queries the active strategy for the latest status of the generation job
    attached to the given song.  Only the song's owner may access this endpoint.

    Terminal states (SUCCESS / FAILED) are returned directly from the stored
    job without making an additional API call.
    """
    song = get_object_or_404(Song, pk=pk, library__owner=request.user)

    try:
        job = song.generation_job
    except GenerationJob.DoesNotExist:
        return JsonResponse(
            {"error": "No generation job found for this song."}, status=404
        )

    # Terminal states need no further polling.
    if job.status in ("SUCCESS", "FAILED"):
        return JsonResponse(
            {
                "song_id": song.pk,
                "task_id": job.task_id,
                "status": job.status,
                "audio_url": job.audio_url or None,
                "song_status": song.status,
            }
        )

    # Use the same strategy that created the job for consistent polling.
    try:
        strategy = get_generator_strategy(job.strategy)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    result = strategy.get_status(job.task_id)

    # Persist any changes.
    if result.status != job.status:
        job.status = result.status
        if result.audio_url:
            job.audio_url = result.audio_url
        if result.error:
            job.error_message = result.error
        job.save()

        if result.status == "SUCCESS":
            song.status = Song.Status.COMPLETED
            song.save()
        elif result.status == "FAILED":
            song.status = Song.Status.FAILED
            song.save()

    return JsonResponse(
        {
            "song_id": song.pk,
            "task_id": job.task_id,
            "status": job.status,
            "audio_url": job.audio_url or None,
            "song_status": song.status,
        }
    )
