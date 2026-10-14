"""Event-hours file (remote-config.json): python -m unittest discover -s tools/tests -v"""

import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("check_remote_config", HERE.parent / "check_remote_config.py")
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)

SAT_12 = 1794052800  # Saturday 7 November 2026, 12:00 UTC


def check(cfg):
    return rc.check(rc.parse(json.dumps(cfg)))


class PublishedFileTests(unittest.TestCase):
    def test_the_published_file_passes_and_overrides_nothing(self):
        text = (HERE.parent.parent / "remote-config.json").read_text(encoding="utf-8")
        self.assertEqual(rc.check(rc.parse(text)), "no overrides (the built-in schedule runs)")


class ValidConfigTests(unittest.TestCase):
    def test_empty_blocks_and_help_keys(self):
        self.assertIn("no overrides", check({}))
        self.assertIn("no overrides", check({"_help": ["x"], "happy_hour": {}, "farm_hour": {}, "events": {}}))

    def test_a_happy_hour(self):
        cfg = {"happy_hour": {"start_unix": SAT_12, "end_unix": SAT_12 + 3600, "cash_mult": 1.5, "token_mult": 2}}
        self.assertIn("happy hour", check(cfg))

    def test_farm_hour_changes_and_switch_off(self):
        self.assertIn("Farm Hour changed", check({"farm_hour": {"first_unix": SAT_12, "hours_utc": [19], "minutes": 90}}))
        self.assertIn("Farm Hour off", check({"farm_hour": {"enabled": False}}))

    def test_event_overrides(self):
        cfg = {"events": {"1": {"start_unix": SAT_12, "end_unix": SAT_12 + 86400}, "2": {"enabled": True}}}
        self.assertIn("2 event override(s)", check(cfg))


class RejectedConfigTests(unittest.TestCase):
    def assert_rejected(self, text_or_cfg):
        text = text_or_cfg if isinstance(text_or_cfg, str) else json.dumps(text_or_cfg)
        with self.assertRaises(rc.ConfigError, msg=text):
            rc.check(rc.parse(text))

    def test_broken_json(self):
        for text in ['{"happy_hour": {},}', '{"farm_hour": {"cash_mult": NaN}}', '{"events": {}, "events": {}}', '[]', '']:
            self.assert_rejected(text)

    def test_typos_in_names(self):
        self.assert_rejected({"happyhour": {}})
        self.assert_rejected({"farm_hour": {"hour_utc": [12]}})
        self.assert_rejected({"events": {"1": {"start": SAT_12}}})
        self.assert_rejected({"events": {"harvest": {"enabled": True}}})

    def test_wrong_types(self):
        self.assert_rejected({"happy_hour": []})
        self.assert_rejected({"farm_hour": {"enabled": "false"}})
        self.assert_rejected({"events": {"1": {"enabled": 1}}})
        self.assert_rejected({"happy_hour": {"start_unix": "1794052800", "end_unix": SAT_12 + 60}})
        self.assert_rejected({"happy_hour": {"cash_mult": True}})

    def test_times_the_world_would_ignore(self):
        self.assert_rejected({"happy_hour": {"start_unix": SAT_12, "end_unix": SAT_12}})
        self.assert_rejected({"events": {"1": {"start_unix": SAT_12, "end_unix": SAT_12 - 1}}})
        self.assert_rejected({"happy_hour": {"start_unix": -5}})
        self.assert_rejected({"happy_hour": {"end_unix": 1e30}})
        self.assert_rejected({"farm_hour": {"first_unix": 0}})
        self.assert_rejected({"happy_hour": {"start_unix": SAT_12 * 1000, "end_unix": SAT_12 * 1001}})  # milliseconds

    def test_out_of_range_numbers(self):
        self.assert_rejected({"happy_hour": {"cash_mult": 2.5}})
        self.assert_rejected({"happy_hour": {"token_mult": 0.5}})
        self.assert_rejected({"farm_hour": {"hours_utc": [24]}})
        self.assert_rejected({"farm_hour": {"hours_utc": []}})
        self.assert_rejected({"farm_hour": {"hours_utc": [12.5]}})
        self.assert_rejected({"farm_hour": {"minutes": 300}})


if __name__ == "__main__":
    unittest.main()
