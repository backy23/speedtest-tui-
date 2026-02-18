"""Tests for client.config -- configuration persistence."""

import json
import os
import tempfile
import unittest
from unittest import mock

from client.config import (
    DEFAULTS,
    load_config,
    save_config,
    get_config_value,
    set_config_value,
)


class TestConfigDefaults(unittest.TestCase):
    def test_defaults_have_required_keys(self):
        for key in ("server", "plan", "connections", "ping_count",
                     "download_duration", "upload_duration", "alert_below", "csv_file"):
            self.assertIn(key, DEFAULTS)


class TestLoadSaveConfig(unittest.TestCase):
    def test_load_defaults_when_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.json")
            with mock.patch("client.config._config_path", return_value=path):
                cfg = load_config()
                self.assertEqual(cfg["connections"], 4)
                self.assertEqual(cfg["plan"], 0.0)

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.json")
            with mock.patch("client.config._config_path", return_value=path):
                save_config({"plan": 200, "server": 42})
                cfg = load_config()
                self.assertEqual(cfg["plan"], 200)
                self.assertEqual(cfg["server"], 42)
                # Defaults still present
                self.assertEqual(cfg["connections"], 4)

    def test_corrupt_file_returns_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.json")
            with open(path, "w") as f:
                f.write("NOT JSON")
            with mock.patch("client.config._config_path", return_value=path):
                cfg = load_config()
                self.assertEqual(cfg["connections"], 4)

    def test_get_set_value(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.json")
            with mock.patch("client.config._config_path", return_value=path):
                set_config_value("plan", 100)
                self.assertEqual(get_config_value("plan"), 100)

                set_config_value("server", 999)
                self.assertEqual(get_config_value("server"), 999)


class TestHourlyAnalysis(unittest.TestCase):
    def test_group_by_hour(self):
        from client.history import group_by_hour
        entries = [
            {"timestamp": "2025-01-15T10:30:00+00:00", "ping": 10,
             "download": {"speed_mbps": 100}, "upload": {"speed_mbps": 50}},
            {"timestamp": "2025-01-15T10:45:00+00:00", "ping": 12,
             "download": {"speed_mbps": 90}, "upload": {"speed_mbps": 45}},
            {"timestamp": "2025-01-15T22:00:00+00:00", "ping": 20,
             "download": {"speed_mbps": 60}, "upload": {"speed_mbps": 30}},
        ]
        buckets = group_by_hour(entries)
        self.assertIn(10, buckets)
        self.assertIn(22, buckets)
        self.assertEqual(len(buckets[10]["download"]), 2)
        self.assertEqual(len(buckets[22]["download"]), 1)

    def test_format_hourly_summary(self):
        from client.history import group_by_hour, format_hourly_summary
        entries = [
            {"timestamp": "2025-01-15T08:00:00+00:00", "ping": 15,
             "download": {"speed_mbps": 80}, "upload": {"speed_mbps": 40}},
        ]
        buckets = group_by_hour(entries)
        rows = format_hourly_summary(buckets)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["hour"], "08:00")
        self.assertAlmostEqual(rows[0]["avg_download"], 80.0)

    def test_empty_entries(self):
        from client.history import group_by_hour, format_hourly_summary
        buckets = group_by_hour([])
        rows = format_hourly_summary(buckets)
        self.assertEqual(rows, [])

    def test_bad_timestamp_skipped(self):
        from client.history import group_by_hour
        entries = [{"timestamp": "not-a-date", "ping": 10}]
        buckets = group_by_hour(entries)
        self.assertEqual(len(buckets), 0)


if __name__ == "__main__":
    unittest.main()
