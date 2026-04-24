"""
Strategy B — Suno API Song Generator
======================================
Production implementation that integrates with SunoAPI.org.

Authentication: Bearer token read from settings.SUNO_API_KEY.
Endpoints used:
  POST https://api.sunoapi.org/api/v1/generate          — submit task
  GET  https://api.sunoapi.org/api/v1/generate/record-info — poll status

Status values returned by Suno:
  PENDING | TEXT_SUCCESS | FIRST_SUCCESS | SUCCESS | FAILED
"""

import requests
from django.conf import settings

from .base import SongGenerationRequest, SongGenerationResult, SongGeneratorStrategy

_BASE_URL = "https://api.sunoapi.org/api/v1"
# Default Suno model — V4_5ALL balances quality and prompt compliance.
_DEFAULT_MODEL = "V4_5ALL"
# Title max length for V4_5ALL model per Suno docs.
_TITLE_MAX_LEN = 80
# Hard timeout for each HTTP call (seconds).
_HTTP_TIMEOUT = 30
# Fallback callback URL used when SUNO_CALLBACK_URL is not configured.
# Must be a reachable HTTPS URL; Suno rejects missing callbackUrl.
_FALLBACK_CALLBACK_URL = "https://example.com/suno/callback"


class SunoSongGeneratorStrategy(SongGeneratorStrategy):
    """
    Concrete Strategy: Suno API generator.

    Behaviour
    ---------
    * generate() submits a generation task to Suno and returns PENDING + taskId.
    * get_status() polls the record-info endpoint and returns the current status.
    * Raises ValueError on construction if SUNO_API_KEY is not configured.

    Error handling
    --------------
    Network or API errors are caught and returned as FAILED results rather than
    propagating exceptions, so callers always receive a SongGenerationResult.
    """

    def __init__(self) -> None:
        self._api_key: str = getattr(settings, "SUNO_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "SUNO_API_KEY is not set. Add it to your .env file and ensure "
                "settings.SUNO_API_KEY is populated."
            )
        # callbackUrl is required by the Suno API. Set SUNO_CALLBACK_URL in .env
        # to your public server URL (e.g. https://yourserver.com/suno/callback/).
        # In local dev Suno will call the URL but we still poll as backup.
        self._callback_url: str = (
            getattr(settings, "SUNO_CALLBACK_URL", "") or _FALLBACK_CALLBACK_URL
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _auth_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Strategy interface
    # ------------------------------------------------------------------

    def generate(self, request: SongGenerationRequest) -> SongGenerationResult:
        """
        Submit a music generation task to Suno.

        Uses customMode=True so that title, style, and lyrics are honoured
        explicitly.  For instrumental songs the prompt/lyrics field is omitted.
        """
        payload: dict = {
            "customMode": True,
            "instrumental": request.instrumental,
            "model": _DEFAULT_MODEL,
            "title": request.title[:_TITLE_MAX_LEN],
            "style": request.style or "Pop",
            "callbackUrl": self._callback_url,
        }

        # In customMode with vocals, prompt IS the lyrics.
        if not request.instrumental:
            lyrics = request.lyrics or request.prompt
            payload["prompt"] = lyrics[:5000]  # V4_5ALL max

        try:
            response = requests.post(
                f"{_BASE_URL}/generate",
                headers=self._auth_headers(),
                json=payload,
                timeout=_HTTP_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            return SongGenerationResult(
                task_id="",
                status="FAILED",
                error=f"Network error contacting Suno API: {exc}",
            )
        except ValueError as exc:
            return SongGenerationResult(
                task_id="",
                status="FAILED",
                error=f"Invalid JSON response from Suno API: {exc}",
            )

        if data.get("code") != 200:
            return SongGenerationResult(
                task_id="",
                status="FAILED",
                error=f"Suno API error {data.get('code')}: {data.get('msg', 'unknown error')}",
            )

        try:
            task_id: str = data["data"]["taskId"]
        except (KeyError, TypeError) as exc:
            return SongGenerationResult(
                task_id="",
                status="FAILED",
                error=f"Unexpected Suno API response structure: {exc}",
            )
        return SongGenerationResult(task_id=task_id, status="PENDING")

    def get_status(self, task_id: str) -> SongGenerationResult:
        """
        Poll Suno's record-info endpoint for the current task status.

        When status is SUCCESS the first track's audio_url is extracted and
        included in the result.
        """
        try:
            response = requests.get(
                f"{_BASE_URL}/generate/record-info",
                headers=self._auth_headers(),
                params={"taskId": task_id},
                timeout=_HTTP_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            return SongGenerationResult(
                task_id=task_id,
                status="FAILED",
                error=f"Network error contacting Suno API: {exc}",
            )
        except ValueError as exc:
            return SongGenerationResult(
                task_id=task_id,
                status="FAILED",
                error=f"Invalid JSON response from Suno API: {exc}",
            )

        if data.get("code") != 200:
            return SongGenerationResult(
                task_id=task_id,
                status="FAILED",
                error=f"Suno API error {data.get('code')}: {data.get('msg', 'unknown error')}",
            )

        try:
            task_data: dict = data.get("data", {})
            status: str = task_data.get("status", "PENDING")
            audio_url: str = ""

            if status == "SUCCESS":
                response_data = task_data.get("response", {})
                # SunoAPI.org v1 uses "sunoData" as the track list key;
                # fall back to "data" for compatibility with other API wrappers.
                tracks = response_data.get("sunoData") or response_data.get("data") or []
                if tracks:
                    # record-info returns camelCase "audioUrl"; callback returns snake_case "audio_url"
                    audio_url = tracks[0].get("audioUrl") or tracks[0].get("audio_url", "")
        except (KeyError, TypeError, IndexError) as exc:
            return SongGenerationResult(
                task_id=task_id,
                status="FAILED",
                error=f"Unexpected Suno status response structure: {exc}",
            )

        return SongGenerationResult(
            task_id=task_id,
            status=status,
            audio_url=audio_url,
        )
