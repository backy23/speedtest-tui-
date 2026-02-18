"""Tests for bugs found during code review."""

import json
import os
import tempfile
import unittest
from unittest import mock

from client.history import save_result
from ui.output import _csv_escape, create_result_json, format_csv_row


class TestMedianCalculation(unittest.TestCase):
    """create_result_json used s[n//2] which is wrong for even-length lists."""

    def test_even_length_pings_median(self):
        result = create_result_json(
            client_info={"ip": "1.2.3.4"},
            server_info={"id": 1},
            latency_results={"pings": [10.0, 20.0], "latency_ms": 10.0},
            download_results={"speed_mbps": 100.0},
            upload_results={"speed_mbps": 50.0},
        )
        # Correct median of [10, 20] is 15.0, not 20.0
        self.assertAlmostEqual(result["latency"]["tcp"]["rtt"]["median"], 15.0)

    def test_odd_length_pings_median(self):
        result = create_result_json(
            client_info={"ip": "1.2.3.4"},
            server_info={"id": 1},
            latency_results={"pings": [5.0, 10.0, 15.0], "latency_ms": 5.0},
            download_results={"speed_mbps": 100.0},
            upload_results={"speed_mbps": 50.0},
        )
        self.assertAlmostEqual(result["latency"]["tcp"]["rtt"]["median"], 10.0)

    def test_single_ping_median(self):
        result = create_result_json(
            client_info={},
            server_info={},
            latency_results={"pings": [42.0]},
            download_results={},
            upload_results={},
        )
        self.assertAlmostEqual(result["latency"]["tcp"]["rtt"]["median"], 42.0)

    def test_four_pings_median(self):
        result = create_result_json(
            client_info={},
            server_info={},
            latency_results={"pings": [1.0, 2.0, 3.0, 4.0]},
            download_results={},
            upload_results={},
        )
        # Correct median of [1, 2, 3, 4] is 2.5
        self.assertAlmostEqual(result["latency"]["tcp"]["rtt"]["median"], 2.5)


class TestCsvEscape(unittest.TestCase):
    """CSV fields with commas must be quoted to avoid corruption."""

    def test_plain_value(self):
        self.assertEqual(_csv_escape("Berlin"), "Berlin")

    def test_value_with_comma(self):
        self.assertEqual(_csv_escape("Berlin, Germany"), '"Berlin, Germany"')

    def test_value_with_quotes(self):
        self.assertEqual(_csv_escape('Say "hello"'), '"Say ""hello"""')

    def test_value_with_newline(self):
        self.assertEqual(_csv_escape("line1\nline2"), '"line1\nline2"')

    def test_csv_row_with_comma_in_server(self):
        row = format_csv_row("Server, Inc.", "ISP", "1.2.3.4", 10.0, 1.0, 100.0, 50.0)
        parts = row.split(",")
        # Without escaping this would be 9+ parts; with escaping it should be 8
        # The quoted field counts as one field
        self.assertIn('"Server, Inc."', row)


class TestSaveResultNoMutation(unittest.TestCase):
    """save_result must not modify the caller's dict."""

    def test_no_mutation_when_timestamp_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "history.jsonl")
            with mock.patch("client.history._history_path", return_value=path):
                original = {"ping": 10, "download": {"speed_mbps": 100}}
                original_copy = dict(original)
                save_result(original)
                # The caller's dict should NOT have a "timestamp" key added
                self.assertEqual(original, original_copy)

    def test_preserves_existing_timestamp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "history.jsonl")
            with mock.patch("client.history._history_path", return_value=path):
                original = {"ping": 10, "timestamp": "2025-01-01T00:00:00"}
                save_result(original)
                with open(path) as fh:
                    saved = json.loads(fh.readline())
                self.assertEqual(saved["timestamp"], "2025-01-01T00:00:00")


class TestPrintLatencyDetailsEmptyPings(unittest.TestCase):
    """print_latency_details must not crash on empty pings list."""

    def test_empty_pings_no_crash(self):
        from unittest.mock import MagicMock
        from ui.dashboard import print_latency_details

        result = MagicMock()
        result.pings = []
        result.jitter_ms = 0.0
        result.packet_loss = 0.0
        result.ping_attempts = 0
        # Should not raise ValueError from min()/max()/mean() on empty list
        print_latency_details(result)


if __name__ == "__main__":
    unittest.main()
