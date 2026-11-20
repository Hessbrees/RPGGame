"""Generowanie ilustracji do przebiegu rozgrywki (modele dyfuzyjne + LoRA + ewaluacja CLIP/DINO)."""
from .config import ImageGenConfig
from .pipeline import IllustrationPipeline

__all__ = ["ImageGenConfig", "IllustrationPipeline"]
