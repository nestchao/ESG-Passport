"""Audited OCR failover; optional cloud and CPU dependencies load lazily."""
from .routing import OCRRouter, RoutingPolicy
from .state import OCRState

__all__ = ['OCRRouter', 'RoutingPolicy', 'OCRState']
