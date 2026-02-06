"""Behavioral tests for control guardrails."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import unittest


def _load_guardrails_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "custom_components"
        / "fellow_stagg_pro"
        / "guardrails.py"
    )
    spec = importlib.util.spec_from_file_location("fellow_stagg_pro_guardrails", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load guardrails module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guardrails = _load_guardrails_module()


class TestGuardrails(unittest.TestCase):
    """Validate safety-related decision logic."""

    def test_is_control_enabled_prefers_options(self) -> None:
        enabled = guardrails.is_control_enabled(
            key="enable_set_temperature",
            data={"enable_set_temperature": False},
            options={"enable_set_temperature": True},
            default=False,
        )
        self.assertTrue(enabled)

    def test_is_control_enabled_uses_default_when_missing(self) -> None:
        enabled = guardrails.is_control_enabled(
            key="enable_set_temperature",
            data={},
            options={},
            default=False,
        )
        self.assertFalse(enabled)

    def test_normalize_target_temperature_c_valid_and_rounds_to_step(self) -> None:
        normalized = guardrails.normalize_target_temperature_c(
            98.24,
            min_c=40.0,
            max_c=100.0,
            step_c=0.5,
        )
        self.assertEqual(normalized, 98.0)

    def test_normalize_target_temperature_c_rejects_non_finite(self) -> None:
        with self.assertRaises(ValueError):
            guardrails.normalize_target_temperature_c(
                math.inf,
                min_c=40.0,
                max_c=100.0,
                step_c=0.5,
            )

    def test_normalize_target_temperature_c_rejects_out_of_range(self) -> None:
        with self.assertRaises(ValueError):
            guardrails.normalize_target_temperature_c(
                101.0,
                min_c=40.0,
                max_c=100.0,
                step_c=0.5,
            )

    def test_normalize_target_temperature_c_rejects_invalid_step(self) -> None:
        with self.assertRaises(ValueError):
            guardrails.normalize_target_temperature_c(
                98.0,
                min_c=40.0,
                max_c=100.0,
                step_c=0,
            )

    def test_normalize_target_temperature_c_rejects_invalid_bounds(self) -> None:
        with self.assertRaises(ValueError):
            guardrails.normalize_target_temperature_c(
                98.0,
                min_c=100.0,
                max_c=40.0,
                step_c=0.5,
            )


if __name__ == "__main__":
    unittest.main()
