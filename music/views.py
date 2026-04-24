import json
from datetime import timedelta

import requests as http_client

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST, require_http_methods

from .generation import SongGenerationRequest, get_generator_strategy
from .models import GenerationJob, Library, Lyrics, Metadata, SharedLink, Song, User, VoiceStyle


# ---------------------------------------------------------------------------
# Library page — HTML (own page with Prompt AI sidebar, FR-3.3)
# ---------------------------------------------------------------------------

@login_required
@ensure_csrf_cookie
def library_view(request):
    """GET /library/ — render the library HTML page."""
    library, _ = Library.objects.get_or_create(owner=request.user)
    return render(request, 'music/library.html', {
        'username': request.user.username,
        'is_full': library.is_full,
        'song_count': library.songs.filter(status=Song.Status.COMPLETED).count(),
    })


# ---------------------------------------------------------------------------
# Library API — JSON (list all songs for the authenticated user)
# ---------------------------------------------------------------------------

@login_required
def library_api_view(request):
    """GET /library/api/ — return the authenticated user's library as JSON."""
    library, _ = Library.objects.get_or_create(owner=request.user)
    songs = library.songs.filter(status=Song.Status.COMPLETED).select_related(
        "metadata", "voice_style"
    )
    data = {
        "owner": request.user.username,
        "song_count": songs.count(),
        "is_full": library.is_full,
        "songs": [
            {
                "id": s.pk,
                "title": s.metadata.title if hasattr(s, "metadata") else "(untitled)",
                "mood": s.metadata.mood if hasattr(s, "metadata") else "",
                "voice_style": s.voice_style.style if hasattr(s, "voice_style") else "",
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
    # Include audio_url for the owner (used by the in-app player)
    audio_url: str | None = None
    if hasattr(song, "generation_job") and song.generation_job.audio_url:
        audio_url = song.generation_job.audio_url
    elif song.audio_file:
        audio_url = request.build_absolute_uri(song.audio_file.url)
    data["audio_url"] = audio_url
    return JsonResponse(data)


# ---------------------------------------------------------------------------
# Shared link view — READ (metadata for all, audio only for authenticated)
# ---------------------------------------------------------------------------

def shared_link_view(request, token):
    """
    Public HTML page for a shared song link.
    Possessing the token grants metadata access regardless of is_private.
    - Guests: see song metadata only, prompted to log in to listen.
    - Authenticated users: see metadata + audio player.
    FR-5.3: must require login to stream audio.
    """
    link = get_object_or_404(SharedLink, token=token)
    song = link.song

    meta = song.metadata if hasattr(song, "metadata") else None
    voice = song.voice_style if hasattr(song, "voice_style") else None
    lyrics = song.lyrics if hasattr(song, "lyrics") else None

    # Audio URL: prefer external generation URL, fall back to local file.
    # Only expose to authenticated users (FR-5.3).
    audio_url: str | None = None
    if request.user.is_authenticated:
        if hasattr(song, "generation_job") and song.generation_job.audio_url:
            audio_url = song.generation_job.audio_url
        elif song.audio_file:
            audio_url = request.build_absolute_uri(song.audio_file.url)

    is_owner = (
        request.user.is_authenticated
        and song.library.owner == request.user
    )

    ctx = {
        "song": song,
        "meta": meta,
        "voice": voice,
        "lyrics": lyrics,
        "audio_url": audio_url,
        "is_owner": is_owner,
        "login_url": reverse("music:login"),
    }
    return render(request, "music/share.html", ctx)


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
    # Mood and occasion accept either a preset enum value OR any custom free-text (≤ 40 chars).
    mood = (body.get("mood") or "").strip()
    if not mood:
        mood = Metadata.Mood.CALM
    elif len(mood) > 40:
        return JsonResponse({"error": "Mood is too long (max 40 characters)."}, status=400)

    occasion = (body.get("occasion") or "").strip()
    if not occasion:
        occasion = Metadata.Occasion.GENERAL
    elif len(occasion) > 40:
        return JsonResponse({"error": "Occasion is too long (max 40 characters)."}, status=400)

    voice_style = body.get("voice_style", VoiceStyle.Style.FEMALE)
    if voice_style not in VoiceStyle.Style.values:
        return JsonResponse({"error": f"Invalid voice_style '{voice_style}'."}, status=400)

    lyrics_mode = body.get("lyrics_mode", Lyrics.Mode.AI_GENERATED)
    if lyrics_mode not in Lyrics.Mode.values:
        return JsonResponse({"error": f"Invalid lyrics_mode '{lyrics_mode}'."}, status=400)

    lyrics_content: str = body.get("lyrics_content", "")
    # Use `or ""` to convert JSON null to empty string (CharField cannot store NULL).
    theme: str = (body.get("theme") or "").strip()

    # --- Persist domain objects (atomic: all-or-nothing) ---
    with transaction.atomic():
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
        song.delete()
        return JsonResponse({"error": str(exc)}, status=500)

    try:
        result = strategy.generate(gen_request)
    except Exception as exc:
        song.delete()
        return JsonResponse({"error": f"Generation request failed: {exc}"}, status=500)

    # If the strategy fails immediately (e.g. invalid API key, bad response),
    # remove the song so it doesn't accumulate as an orphaned FAILED record.
    if result.status == "FAILED":
        song.delete()
        return JsonResponse({"error": result.error or "Song generation failed."}, status=400)

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
        # Reconcile song.status in case a previous song.save() failed while
        # job.save() had already committed (atomicity bug from prior code path).
        expected_song_status = (
            Song.Status.COMPLETED if job.status == "SUCCESS" else Song.Status.FAILED
        )
        if song.status != expected_song_status:
            song.status = expected_song_status
            song.save()
        return JsonResponse(
            {
                "song_id": song.pk,
                "task_id": job.task_id,
                "status": job.status,
                "audio_url": job.audio_url or None,
                "error_message": job.error_message or None,
                "song_status": song.status,
            }
        )

    # NFR: automatically time out generation tasks older than 10 minutes.
    _GENERATION_TIMEOUT_SECONDS = 600  # 10 minutes
    age = timezone.now() - job.created_at
    if age > timedelta(seconds=_GENERATION_TIMEOUT_SECONDS):
        job.status = "FAILED"
        job.error_message = "Generation Timeout: the AI service took too long. Please retry."
        job.save()
        song.status = Song.Status.FAILED
        song.save()
        return JsonResponse(
            {
                "song_id": song.pk,
                "task_id": job.task_id,
                "status": "FAILED",
                "error_message": job.error_message,
                "audio_url": None,
                "song_status": song.status,
            }
        )

    # Use the same strategy that created the job for consistent polling.
    try:
        strategy = get_generator_strategy(job.strategy)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    result = strategy.get_status(job.task_id)

    # Persist any changes atomically so job and song status are always in sync.
    if result.status != job.status:
        with transaction.atomic():
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
            "error_message": job.error_message or None,
            "song_status": song.status,
        }
    )


# ---------------------------------------------------------------------------
# Suno webhook callback — UPDATE (Strategy Pattern: async result delivery)
# ---------------------------------------------------------------------------

from django.views.decorators.csrf import csrf_exempt  # noqa: E402


@csrf_exempt
@require_POST
def suno_callback_view(request):
    """
    POST /suno/callback/

    Suno calls this endpoint when a generation task finishes (or fails).
    We update the GenerationJob and Song status from the payload so that
    the next poll from the browser returns the final state immediately.

    The endpoint is CSRF-exempt because Suno is an external service.
    No sensitive state is modified without a valid taskId that maps to an
    existing GenerationJob, so there is no meaningful CSRF risk here.

    Expected payload (Suno V1 callback):
    {
        "taskId": "<task id>",
        "status": "SUCCESS" | "FAILED",
        "data": [ { "audio_url": "...", ... } ]   // present on SUCCESS
    }
    """
    try:
        body: dict = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    # SunoAPI.org v1 callback format:
    # {
    #   "code": 200,
    #   "msg": "All generated successfully.",
    #   "data": {
    #     "callbackType": "complete" | "first" | "text" | "error",
    #     "task_id": "<task id>",
    #     "data": [ { "audio_url": "...", ... } ]   // present on SUCCESS
    #   }
    # }
    code: int = body.get("code", 0)
    data_block: dict = body.get("data") or {}
    task_id: str = (data_block.get("task_id") or "").strip()
    callback_type: str = (data_block.get("callbackType") or "").strip().lower()

    if not task_id:
        return JsonResponse({"ok": True})  # Unknown payload — ignore silently

    # Map callbackType + code to internal status
    if code != 200 or callback_type == "error":
        status = "FAILED"
    elif callback_type == "complete":
        status = "SUCCESS"
    elif callback_type == "first":
        status = "FIRST_SUCCESS"
    elif callback_type == "text":
        status = "TEXT_SUCCESS"
    else:
        return JsonResponse({"ok": True})  # Unknown callbackType — ignore silently

    try:
        job = GenerationJob.objects.select_related("song").get(task_id=task_id)
    except GenerationJob.DoesNotExist:
        return JsonResponse({"ok": True})  # Unknown task — ignore silently

    if job.status in ("SUCCESS", "FAILED"):
        return JsonResponse({"ok": True})  # Already terminal — nothing to do

    audio_url: str = ""
    if status == "SUCCESS":
        # Callback uses snake_case "audio_url" in data.data[]
        tracks = data_block.get("data") or []
        if isinstance(tracks, list) and tracks:
            audio_url = tracks[0].get("audio_url", "")

    with transaction.atomic():
        job.status = status
        if audio_url:
            job.audio_url = audio_url
        error_msg = data_block.get("errorMessage") or data_block.get("error") or ""
        if error_msg:
            job.error_message = error_msg
        job.save()

        # Only update Song for terminal states; intermediate states
        # (TEXT_SUCCESS, FIRST_SUCCESS) leave the song in GENERATING.
        song = job.song
        if status == "SUCCESS":
            song.status = Song.Status.COMPLETED
            song.save()
        elif status == "FAILED":
            song.status = Song.Status.FAILED
            song.save()

    return JsonResponse({"ok": True})


# ---------------------------------------------------------------------------
# Local Account registration — CREATE (FR-1.3)
# ---------------------------------------------------------------------------

@ensure_csrf_cookie
def register_view(request):
    """
    GET  /auth/register/  → render register page
    POST /auth/register/  → create account (JSON API)
    """    
    if request.method == 'GET':
        if request.user.is_authenticated:
            return redirect('/')
        return render(request, 'music/register.html')
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    try:
        body: dict = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)

    username: str = body.get("username", "").strip()
    password: str = body.get("password", "")
    email: str = body.get("email", "").strip()
    first_name: str = body.get("first_name", "").strip()
    last_name: str = body.get("last_name", "").strip()

    if not username or not password or not email:
        return JsonResponse(
            {"error": "username, password, and email are required."},
            status=400,
        )

    if User.objects.filter(username=username).exists():
        return JsonResponse({"error": "Username already taken."}, status=400)

    if User.objects.filter(email=email).exists():
        return JsonResponse({"error": "Email already registered."}, status=400)

    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
        first_name=first_name,
        last_name=last_name,
    )
    # FR-1.3: auto sign-in immediately after registration
    # Specify backend explicitly — multiple backends are configured (allauth)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return JsonResponse(
        {
            "id": user.pk,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
        },
        status=201,
    )


# ---------------------------------------------------------------------------
# Local Account login — SESSION CREATE (FR-1.1)
# ---------------------------------------------------------------------------

@ensure_csrf_cookie
def login_view(request):
    """
    GET  /auth/login/  → render login page
    POST /auth/login/  → authenticate session (JSON API)

    For Google OAuth, use the allauth headless endpoint:
      POST /_allauth/browser/v1/auth/provider/token
    """    
    if request.method == 'GET':
        if request.user.is_authenticated:
            return redirect('/')
        return render(request, 'music/login.html')
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    try:
        body: dict = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Request body must be valid JSON."}, status=400)

    username: str = body.get("username", "")
    password: str = body.get("password", "")

    if not username or not password:
        return JsonResponse(
            {"error": "username and password are required."},
            status=400,
        )

    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({"error": "Invalid credentials."}, status=401)

    login(request, user)
    return JsonResponse(
        {
            "id": user.pk,
            "username": user.username,
            "email": user.email,
        }
    )


# ---------------------------------------------------------------------------
# Logout — SESSION DESTROY (FR-1.1)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def logout_view(request):
    """POST /auth/logout/ — destroys the current session."""
    logout(request)
    return JsonResponse({"message": "Logged out successfully."})


# ---------------------------------------------------------------------------
# Delete song — DESTROY (FR-3.4)
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(["DELETE"])
def delete_song_view(request, pk):
    """
    DELETE /songs/<pk>/delete/

    Permanently removes the song and all composed entities (Metadata, VoiceStyle,
    Lyrics, GenerationJob, SharedLink) from the database.  Only the song's owner
    may delete it.  Reducing the song count allows future generation again (FR-2.1).
    """
    song = get_object_or_404(Song, pk=pk, library__owner=request.user)
    song.delete()
    return JsonResponse({"message": f"Song {pk} deleted."})


# ---------------------------------------------------------------------------
# Create shared link — GENERATE URL (FR-5.2)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def create_shared_link_view(request, pk):
    """
    POST /songs/<pk>/share/

    Generates a unique, cryptographically secure UUID URL token for the given
    song.  Only the song's owner may create a link.  Calling this endpoint a
    second time returns the existing token (idempotent).
    """
    song = get_object_or_404(Song, pk=pk, library__owner=request.user)

    link, created = SharedLink.objects.get_or_create(
        song=song,
        defaults={"created_by": request.user},
    )

    share_url = request.build_absolute_uri(
        reverse("music:shared_link", args=[link.token])
    )

    return JsonResponse(
        {
            "token": str(link.token),
            "url": share_url,
            "created": created,
        },
        status=201 if created else 200,
    )


# ---------------------------------------------------------------------------
# Download song — RETRIEVE audio URL (FR-5.1)
# ---------------------------------------------------------------------------

@login_required
def download_song_view(request, pk):
    """
    GET /songs/<pk>/download/

    Streams the audio file as a download attachment so the browser saves it
    regardless of whether the source is a local file or a remote Suno CDN URL.
    Only the owner may download (FR-5.3).
    """
    song = get_object_or_404(Song, pk=pk, library__owner=request.user)
    title: str = song.metadata.title if hasattr(song, "metadata") else f"song-{pk}"
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip() or f"song-{pk}"

    # ── Remote URL from Suno (proxy-stream so browser gets a real download) ──
    if hasattr(song, "generation_job") and song.generation_job.audio_url:
        remote_url = song.generation_job.audio_url
        try:
            upstream = http_client.get(remote_url, stream=True, timeout=30)
            upstream.raise_for_status()
        except http_client.RequestException as exc:
            return JsonResponse(
                {"error": f"Could not retrieve audio from Suno: {exc}"},
                status=502,
            )
        content_type = upstream.headers.get("Content-Type", "audio/mpeg")
        response = StreamingHttpResponse(
            upstream.iter_content(chunk_size=8192),
            content_type=content_type,
        )
        response["Content-Disposition"] = f'attachment; filename="{safe_title}.mp3"'
        return response

    # ── Local uploaded file ──
    if song.audio_file:
        from django.http import FileResponse
        return FileResponse(
            song.audio_file.open("rb"),
            as_attachment=True,
            filename=f"{safe_title}.mp3",
        )

    return JsonResponse(
        {"error": "No audio file is available for this song yet."},
        status=404,
    )


# ---------------------------------------------------------------------------
# Main application page — entry point for the SPA (FR-1.4)
# ---------------------------------------------------------------------------

@login_required
@ensure_csrf_cookie
def app_view(request):
    """
    GET /  — renders the single-page application shell.

    Passes the current user's username and library status to the template so
    the JS can bootstrap without an extra API round-trip.
    All subsequent data (library, generate, delete, share) is fetched via the
    JSON endpoints by main.js.
    """
    library, _ = Library.objects.get_or_create(owner=request.user)
    return render(request, 'music/app.html', {
        'username': request.user.username,
        'is_full': library.is_full,
        'song_count': library.songs.filter(status=Song.Status.COMPLETED).count(),
    })


