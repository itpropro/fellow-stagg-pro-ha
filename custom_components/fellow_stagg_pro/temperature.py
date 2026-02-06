"""Temperature conversion helpers."""

from __future__ import annotations


def celsius_to_fahrenheit(value_c: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return (value_c * 9.0 / 5.0) + 32.0


def fahrenheit_to_celsius(value_f: float) -> float:
    """Convert Fahrenheit to Celsius."""
    return (value_f - 32.0) * 5.0 / 9.0
