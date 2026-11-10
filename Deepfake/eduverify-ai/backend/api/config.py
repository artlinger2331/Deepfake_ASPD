"""
EduVerify AI - Scoring & Decision Engine Configuration
======================================================
Stores all configurable weights, thresholds, and quality parameters.
Supports overrides via environment variables.

IMPORTANT:
These are initial prototype weights and thresholds. They must be tuned
and calibrated using empirical benchmark data on real student work.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Any


def _get_env_float(name: str, default: float) -> float:
    try:
        val = os.getenv(name)
        return float(val) if val is not None else default
    except ValueError:
        return default


@dataclass
class VisualWeights:
    """Weights for the multi-feature visual synthetic analyzer (sum = 1.0)."""
    laplacian: float = field(default_factory=lambda: _get_env_float("EDUX_W_LAPLACIAN", 0.20))
    noise: float = field(default_factory=lambda: _get_env_float("EDUX_W_NOISE", 0.20))
    high_freq_fft: float = field(default_factory=lambda: _get_env_float("EDUX_W_HIGH_FREQ", 0.25))
    texture_uniformity: float = field(default_factory=lambda: _get_env_float("EDUX_W_TEXTURE", 0.20))
    compression_artifacts: float = field(default_factory=lambda: _get_env_float("EDUX_W_COMPRESSION", 0.15))

    def as_dict(self) -> Dict[str, float]:
        return {
            "laplacian": self.laplacian,
            "noise": self.noise,
            "high_freq_fft": self.high_freq_fft,
            "texture_uniformity": self.texture_uniformity,
            "compression_artifacts": self.compression_artifacts
        }


@dataclass
class FusionWeights:
    """Weights for multi-signal fusion (sum = 1.0)."""
    visual: float = field(default_factory=lambda: _get_env_float("EDUX_WEIGHT_VISUAL", 0.50))
    metadata: float = field(default_factory=lambda: _get_env_float("EDUX_WEIGHT_METADATA", 0.20))
    provenance: float = field(default_factory=lambda: _get_env_float("EDUX_WEIGHT_PROVENANCE", 0.20))
    ocr_consistency: float = field(default_factory=lambda: _get_env_float("EDUX_WEIGHT_CONSISTENCY", 0.10))

    def as_dict(self) -> Dict[str, float]:
        return {
            "visual": self.visual,
            "metadata": self.metadata,
            "provenance": self.provenance,
            "ocr_consistency": self.ocr_consistency
        }


@dataclass
class DecisionThresholds:
    """Decision boundary thresholds for final verdict categorization."""
    likely_genuine: float = field(default_factory=lambda: _get_env_float("EDUX_THRESHOLD_T1", 0.45))
    concern: float = field(default_factory=lambda: _get_env_float("EDUX_THRESHOLD_T2", 0.70))

    def as_dict(self) -> Dict[str, float]:
        return {
            "likely_genuine": self.likely_genuine,
            "concern": self.concern
        }


@dataclass
class QualityAdjustmentFactors:
    """Quality dampening multipliers applied to visual score."""
    high: float = 1.0
    medium: float = 0.85
    low: float = 0.70


# Global configuration instances
VISUAL_WEIGHTS = VisualWeights()
FUSION_WEIGHTS = FusionWeights()
THRESHOLDS = DecisionThresholds()
QUALITY_FACTORS = QualityAdjustmentFactors()

FUSION_FORMULA_STR = "S = w_v * V_adjusted + w_m * M + w_p * P + w_c * C"

