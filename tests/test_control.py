"""Behavioral tests for temperature control resolution logic."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


def _load_control_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "custom_components"
        / "fellow_stagg_pro"
        / "control.py"
    )
    spec = importlib.util.spec_from_file_location("fellow_stagg_pro_control", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load control module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


control = _load_control_module()


class TestControl(unittest.TestCase):
    """Validate target matching and source priority behavior."""

    def test_target_match_uses_tolerance(self) -> None:
        self.assertTrue(control.is_target_match(98.0, 98.24))
        self.assertFalse(control.is_target_match(98.0, 98.4))

    def test_target_resolution_prefers_optimistic(self) -> None:
        resolved = control.resolve_target_temperature_c(
            optimistic_target_c=95.5,
            settings={"settempr_c": 96.0},
            state={"target_temp_c": 97.0},
        )
        self.assertEqual(resolved, 95.5)

    def test_target_resolution_falls_back_to_settings_then_state(self) -> None:
        from_settings = control.resolve_target_temperature_c(
            optimistic_target_c=None,
            settings={"settempr_c": 96.0},
            state={"target_temp_c": 97.0},
        )
        self.assertEqual(from_settings, 96.0)

        from_state = control.resolve_target_temperature_c(
            optimistic_target_c=None,
            settings={},
            state={"target_temp_c": 97.0},
        )
        self.assertEqual(from_state, 97.0)

    def test_target_resolution_returns_none_when_missing(self) -> None:
        resolved = control.resolve_target_temperature_c(
            optimistic_target_c=None,
            settings={},
            state={},
        )
        self.assertIsNone(resolved)

    def test_derive_power_state_prefers_mode_when_present(self) -> None:
        self.assertFalse(control.derive_power_state({"mode": "S_Off", "flags": {"ho": 1}}))
        self.assertTrue(control.derive_power_state({"mode": "S_Hold", "flags": {"ho": 0}}))

    def test_derive_power_state_falls_back_to_heat_flag(self) -> None:
        self.assertTrue(control.derive_power_state({"flags": {"ho": 1}}))
        self.assertFalse(control.derive_power_state({"flags": {"ho": 0}}))

    def test_derive_power_state_returns_none_when_unknown(self) -> None:
        self.assertIsNone(control.derive_power_state({}))

    def test_derive_operation_mode_maps_off_and_hold(self) -> None:
        self.assertEqual(control.derive_operation_mode({"mode": "S_Off"}), "off")
        self.assertEqual(control.derive_operation_mode({"mode": "S_Hold"}), "eco")

    def test_derive_operation_mode_falls_back_to_power_state(self) -> None:
        self.assertEqual(control.derive_operation_mode({"flags": {"ho": 1}}), "electric")
        self.assertEqual(control.derive_operation_mode({"flags": {"ho": 0}}), "off")

    def test_derive_operation_mode_returns_none_when_unknown(self) -> None:
        self.assertIsNone(control.derive_operation_mode({}))


if __name__ == "__main__":
    unittest.main()
