"""
Strategy implementations for preprocessing operations.

Contains concrete implementations of CodecStrategy and HashStrategy
for various encoding codecs and perceptual hashing algorithms.
"""

from .codec_strategies import (
    H264NvencStrategy,
    HevcNvencStrategy,
    VP9Strategy,
    LibX264Strategy,
    LibX265Strategy,
)
from .hash_strategies import (
    PerceptualHashStrategy,
    DifferenceHashStrategy,
    WaveletHashStrategy,
)

__all__ = [
    "H264NvencStrategy",
    "HevcNvencStrategy",
    "VP9Strategy",
    "LibX264Strategy",
    "LibX265Strategy",
    "PerceptualHashStrategy",
    "DifferenceHashStrategy",
    "WaveletHashStrategy",
]
