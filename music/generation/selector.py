"""
Centralised strategy selector (Factory).
=========================================
All strategy selection logic lives here.  No if/else branching should appear
anywhere else in the codebase when choosing a generation strategy.

Configuration
-------------
Set ``GENERATOR_STRATEGY`` in your ``.env`` (or Django settings) to one of:

    mock   — offline, deterministic (default)
    suno   — live Suno API (requires SUNO_API_KEY)

Example .env::

    GENERATOR_STRATEGY=suno
    SUNO_API_KEY=your-api-key-here
"""

from django.conf import settings

from .base import SongGeneratorStrategy
from .mock_strategy import MockSongGeneratorStrategy
from .suno_strategy import SunoSongGeneratorStrategy

# Registry: strategy name → class
_REGISTRY: dict[str, type[SongGeneratorStrategy]] = {
    "mock": MockSongGeneratorStrategy,
    "suno": SunoSongGeneratorStrategy,
}


def get_generator_strategy(name: str | None = None) -> SongGeneratorStrategy:
    """
    Return an instantiated strategy.

    Parameters
    ----------
    name : str | None
        Strategy name to use.  If *None*, reads ``settings.GENERATOR_STRATEGY``
        (which itself defaults to ``'mock'`` when not set).

    Raises
    ------
    ValueError
        If the requested strategy name is not registered.
    """
    if name is None:
        name = getattr(settings, "GENERATOR_STRATEGY", "mock")

    key = name.strip().lower()
    strategy_class = _REGISTRY.get(key)

    if strategy_class is None:
        raise ValueError(
            f"Unknown GENERATOR_STRATEGY '{name}'. "
            f"Valid options: {sorted(_REGISTRY.keys())}"
        )

    return strategy_class()
