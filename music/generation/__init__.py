"""
Strategy Pattern — Song Generation
===================================
This package defines the abstract interface and concrete implementations
for AI song generation. Strategy selection is centralised in selector.py.

Public API
----------
    from music.generation import (
        SongGeneratorStrategy,   # abstract base class
        SongGenerationRequest,   # input dataclass
        SongGenerationResult,    # output dataclass
        get_generator_strategy,  # factory: reads GENERATOR_STRATEGY setting
    )
"""

from .base import SongGeneratorStrategy, SongGenerationRequest, SongGenerationResult
from .selector import get_generator_strategy

__all__ = [
    "SongGeneratorStrategy",
    "SongGenerationRequest",
    "SongGenerationResult",
    "get_generator_strategy",
]
