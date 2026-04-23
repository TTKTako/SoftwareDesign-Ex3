"""
Strategy A — Mock Song Generator
==================================
Offline, deterministic implementation for development and testing.
Never calls any external API or network resource.
"""

import uuid

from .base import SongGenerationRequest, SongGenerationResult, SongGeneratorStrategy

# A stable public MP3 that is safe to use as a placeholder in tests / demos.
_MOCK_AUDIO_URL = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"


class MockSongGeneratorStrategy(SongGeneratorStrategy):
    """
    Concrete Strategy: Mock generator.

    Behaviour
    ---------
    * generate() returns a synthetic task_id and status=SUCCESS immediately.
    * get_status() always returns SUCCESS for any task_id it created.
    * No network calls are ever made.
    """

    def generate(self, request: SongGenerationRequest) -> SongGenerationResult:
        """
        Simulate a completed generation synchronously.

        The task_id is prefixed with 'mock-' so it can be identified later
        without querying an external service.
        """
        task_id = f"mock-{uuid.uuid4().hex[:12]}"
        return SongGenerationResult(
            task_id=task_id,
            status="SUCCESS",
            audio_url=_MOCK_AUDIO_URL,
        )

    def get_status(self, task_id: str) -> SongGenerationResult:
        """
        Return SUCCESS for any mock task (they are always complete).

        If given a task_id that does not look like a mock one, report FAILED
        so that callers receive an informative error rather than silently wrong data.
        """
        if not task_id.startswith("mock-"):
            return SongGenerationResult(
                task_id=task_id,
                status="FAILED",
                error=f"MockSongGeneratorStrategy cannot resolve task '{task_id}'.",
            )
        return SongGenerationResult(
            task_id=task_id,
            status="SUCCESS",
            audio_url=_MOCK_AUDIO_URL,
        )
