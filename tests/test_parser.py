"""Functional tests for CLI payload parsing."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


def _load_parser_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "custom_components"
        / "fellow_stagg_pro"
        / "parser.py"
    )
    spec = importlib.util.spec_from_file_location("fellow_stagg_pro_parser", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load parser module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parser = _load_parser_module()


STATE_PAYLOAD = """
ret 0
scrname=wnd
mode=S_Off
tempr=75.254237 C
temprB=100.000000 C
temprT=98.000000 C
ketl= ho 0 wd 1 nw 0 ipb 0 bf 0 tr 0
units=1
clock=12:36
ble conn=0
""".strip()


SETTINGS_PAYLOAD = """
ret 0
settempr=196 2C (98.000000 C 208.399994 F)
hold=15
units=1
wifimode=4
""".strip()


FWINFO_PAYLOAD = """
ret 0
Current version: 1.1.75SSP cli
Current boot partition: ota_0
Current running partition: ota_0
Current last invalid partition:
""".strip()


class TestParser(unittest.TestCase):
    """Validate parser behavior against realistic payloads."""

    def test_normalize_cli_payload_strips_html(self) -> None:
        payload = "<html><body>ret 0<br>mode=S_Off</body></html>"
        normalized = parser.normalize_cli_payload(payload)
        self.assertIn("ret 0", normalized)
        self.assertIn("mode=S_Off", normalized)
        self.assertNotIn("<html>", normalized)

    def test_extract_ret_code(self) -> None:
        self.assertEqual(parser.extract_ret_code("... ret 0 ..."), 0)
        self.assertEqual(parser.extract_ret_code("ret -3"), -3)
        self.assertIsNone(parser.extract_ret_code("no ret line"))

    def test_parse_state_payload(self) -> None:
        parsed = parser.parse_state_payload(STATE_PAYLOAD)
        self.assertEqual(parsed["mode"], "S_Off")
        self.assertEqual(parsed["units"], 1)
        self.assertEqual(parsed["ble_connected"], 0)
        self.assertAlmostEqual(parsed["current_temp_c"], 75.254237)
        self.assertAlmostEqual(parsed["target_temp_c"], 98.0)
        self.assertEqual(parsed["flags"]["ho"], 0)
        self.assertEqual(parsed["flags"]["wd"], 1)

    def test_parse_settings_payload(self) -> None:
        parsed = parser.parse_settings_payload(SETTINGS_PAYLOAD)
        self.assertEqual(parsed["hold"], "15")
        self.assertEqual(parsed["units"], "1")
        self.assertEqual(parsed["units_int"], 1)
        self.assertEqual(parsed["settempr_raw"], 196)
        self.assertEqual(parsed["settempr_scale"], "2c")
        self.assertAlmostEqual(parsed["settempr_c"], 98.0)

    def test_parse_settings_payload_with_fahrenheit_settempr(self) -> None:
        payload = "settempr=176 F (80.000000 C 176.000000 F)\nunits=1"
        parsed = parser.parse_settings_payload(payload)
        self.assertEqual(parsed["settempr_raw"], 176)
        self.assertEqual(parsed["settempr_scale"], "f")
        self.assertAlmostEqual(parsed["settempr_c"], 80.0)

    def test_parse_settings_payload_with_log_prefix(self) -> None:
        payload = "\n".join(
            [
                "st: settempr=160 F (71.111115 C 160.000000 F)",
                "st: units=1",
                "st: hold=15",
            ]
        )
        parsed = parser.parse_settings_payload(payload)
        self.assertEqual(parsed["settempr_raw"], 160)
        self.assertEqual(parsed["settempr_scale"], "f")
        self.assertAlmostEqual(parsed["settempr_c"], 71.111115)
        self.assertEqual(parsed["units_int"], 1)
        self.assertEqual(parsed["hold"], "15")

    def test_parse_fwinfo_payload(self) -> None:
        parsed = parser.parse_fwinfo_payload(FWINFO_PAYLOAD)
        self.assertEqual(parsed["version"], "1.1.75SSP cli")
        self.assertEqual(parsed["boot_partition"], "ota_0")
        self.assertEqual(parsed["running_partition"], "ota_0")
        self.assertIsNone(parsed["last_invalid_partition"])


if __name__ == "__main__":
    unittest.main()
