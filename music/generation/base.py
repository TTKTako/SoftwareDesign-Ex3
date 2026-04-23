"""
Abstract base class and data-transfer objects for the Strategy Pattern.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SongGenerationRequest:
    """
    All information needed to generate a song, extracted from domain models
    before being handed to any strategy.
    """

    song_id: int
    title: str
    # Text prompt / theme used as the creative brief or explicit lyrics
    prompt: str
    # Music style / genre string (e.g. "Jazz", "Electronic")
    style: str
    # Actual lyric text when mode is CUSTOM; empty otherwise
    lyrics: str
    # True when the song should have no vocals (instrumental only)
    instrumental: bool = False


@dataclass
class SongGenerationResult:
    """
    Outcome returned by any generation strategy after submitting or polling.

    Fields
    ------
    task_id   : Opaque identifier for the background task (empty on failure).
    status    : One of PENDING / TEXT_SUCCESS / FIRST_SUCCESS / SUCCESS / FAILED.
    audio_url : Public URL to the generated audio (populated when status=SUCCESS).
    error     : Human-readable error description (populated when status=FAILED).
    """

    task_id: str
    status: str
    audio_url: str = field(default="")
    error: str = field(default="")


class SongGeneratorStrategy(ABC):
    """
    Abstract base class for song-generation strategies (Strategy Pattern).

    All concrete strategies must implement:
      - generate(request)  → submits a generation task
      - get_status(task_id) → queries the current status of a task
    """

    @abstractmethod
    def generate(self, request: SongGenerationRequest) -> SongGenerationResult:
        """
        Kick off generation for the given request.

        Parameters
        ----------
        request : SongGenerationRequest
            Describes the song to generate.

        Returns
        -------
        SongGenerationResult
            Contains the task_id and initial status.  For synchronous strategies
            (e.g. Mock) the result may already be SUCCESS.
        """

    @abstractmethod
    def get_status(self, task_id: str) -> SongGenerationResult:
        """
        Query the current status of a previously submitted generation task.

        Parameters
        ----------
        task_id : str
            The opaque task identifier returned by generate().

        Returns
        -------
        SongGenerationResult
            Updated status, and audio_url when status is SUCCESS.
        """
