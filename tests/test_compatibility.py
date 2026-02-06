"""Compatibility-focused tests for Home Assistant runtime imports."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent
INTEGRATION_ROOT = ROOT / "custom_components" / "fellow_stagg_pro"


def _load_temperature_module():
    module_path = INTEGRATION_ROOT / "temperature.py"
    spec = importlib.util.spec_from_file_location("fellow_stagg_pro_temperature", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load temperature module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestCompatibility(unittest.TestCase):
    """Validate compatibility constraints that caused real-world failures."""

    def test_no_removed_temperature_util_import(self) -> None:
        """Integration modules must not import deprecated HA temperature util path."""
        bad_import = "homeassistant.util.temperature"
        checked_files = [
            INTEGRATION_ROOT / "water_heater.py",
            INTEGRATION_ROOT / "sensor.py",
        ]

        for file_path in checked_files:
            with self.subTest(file=file_path.name):
                contents = file_path.read_text(encoding="utf-8")
                self.assertNotIn(bad_import, contents)

    def test_temperature_conversions_are_consistent(self) -> None:
        """Custom conversion helpers should preserve values within expected precision."""
        temperature = _load_temperature_module()

        self.assertAlmostEqual(temperature.celsius_to_fahrenheit(0.0), 32.0)
        self.assertAlmostEqual(temperature.celsius_to_fahrenheit(100.0), 212.0)
        self.assertAlmostEqual(temperature.fahrenheit_to_celsius(32.0), 0.0)
        self.assertAlmostEqual(temperature.fahrenheit_to_celsius(212.0), 100.0)

        roundtrip_value = 87.3
        fahrenheit = temperature.celsius_to_fahrenheit(roundtrip_value)
        self.assertAlmostEqual(
            temperature.fahrenheit_to_celsius(fahrenheit),
            roundtrip_value,
            places=8,
        )


if __name__ == "__main__":
    unittest.main()
