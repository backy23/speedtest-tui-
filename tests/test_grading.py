"""Tests for client.grading -- speed grading, comparison, and share text."""

import unittest

from client.grading import (
    compare_with_previous,
    format_delta,
    format_share_text,
    grade_speed,
)


class TestGradeSpeed(unittest.TestCase):
    def test_a_plus(self):
        grade, color, pct = grade_speed(98.0, 100.0)
        self.assertEqual(grade, "A+")
        self.assertEqual(color, "green")
        self.assertAlmostEqual(pct, 0.98)

    def test_a(self):
        grade, _, pct = grade_speed(90.0, 100.0)
        self.assertEqual(grade, "A")

    def test_b(self):
        grade, _, _ = grade_speed(80.0, 100.0)
        self.assertEqual(grade, "B")

    def test_c(self):
        grade, _, _ = grade_speed(65.0, 100.0)
        self.assertEqual(grade, "C")

    def test_d(self):
        grade, color, _ = grade_speed(45.0, 100.0)
        self.assertEqual(grade, "D")
        self.assertEqual(color, "red")

    def test_f(self):
        grade, _, _ = grade_speed(10.0, 100.0)
        self.assertEqual(grade, "F")

    def test_over_100_percent(self):
        grade, _, pct = grade_speed(120.0, 100.0)
        self.assertEqual(grade, "A+")
        self.assertAlmostEqual(pct, 1.2)

    def test_zero_plan(self):
        grade, _, _ = grade_speed(50.0, 0.0)
        self.assertEqual(grade, "?")

    def test_negative_plan(self):
        grade, _, _ = grade_speed(50.0, -10.0)
        self.assertEqual(grade, "?")

    def test_zero_measured(self):
        grade, _, _ = grade_speed(0.0, 100.0)
        self.assertEqual(grade, "F")


class TestCompareWithPrevious(unittest.TestCase):
    def test_no_history(self):
        self.assertIsNone(compare_with_previous({"ping": 10}, []))

    def test_basic_delta(self):
        current = {
            "ping": 10.0,
            "download": {"speed_mbps": 100.0},
            "upload": {"speed_mbps": 50.0},
        }
        history = [{
            "ping": 15.0,
            "download": {"speed_mbps": 90.0},
            "upload": {"speed_mbps": 45.0},
        }]
        delta = compare_with_previous(current, history)
        self.assertIsNotNone(delta)
        self.assertAlmostEqual(delta["ping_delta"], -5.0)
        self.assertAlmostEqual(delta["download_delta"], 10.0)
        self.assertAlmostEqual(delta["upload_delta"], 5.0)

    def test_missing_fields(self):
        delta = compare_with_previous({"ping": 10}, [{"ping": 20}])
        self.assertAlmostEqual(delta["ping_delta"], -10.0)
        self.assertAlmostEqual(delta["download_delta"], 0.0)

    def test_uses_last_entry(self):
        history = [
            {"ping": 100.0, "download": {"speed_mbps": 10.0}, "upload": {"speed_mbps": 5.0}},
            {"ping": 20.0, "download": {"speed_mbps": 90.0}, "upload": {"speed_mbps": 45.0}},
        ]
        current = {"ping": 15.0, "download": {"speed_mbps": 100.0}, "upload": {"speed_mbps": 50.0}}
        delta = compare_with_previous(current, history)
        self.assertAlmostEqual(delta["ping_delta"], -5.0)


class TestFormatDelta(unittest.TestCase):
    def test_positive_speed(self):
        result = format_delta(10.0, "Mbps")
        self.assertIn("+10.0", result)
        self.assertIn("green", result)

    def test_negative_speed(self):
        result = format_delta(-10.0, "Mbps")
        self.assertIn("-10.0", result)
        self.assertIn("red", result)

    def test_positive_ping_is_bad(self):
        result = format_delta(5.0, "ms", invert=True)
        self.assertIn("+5.0", result)
        self.assertIn("red", result)

    def test_negative_ping_is_good(self):
        result = format_delta(-5.0, "ms", invert=True)
        self.assertIn("-5.0", result)
        self.assertIn("green", result)

    def test_zero_delta(self):
        result = format_delta(0.0, "Mbps")
        self.assertIn("same", result)

    def test_tiny_delta(self):
        result = format_delta(0.005, "Mbps")
        self.assertIn("same", result)


class TestFormatShareText(unittest.TestCase):
    def test_basic(self):
        text = format_share_text(
            ping_ms=15.0, jitter_ms=2.0,
            download_mbps=100.0, upload_mbps=50.0,
            server_name="Berlin", server_sponsor="ISP",
        )
        self.assertIn("15.0 ms", text)
        self.assertIn("100.00 Mbps", text)
        self.assertIn("50.00 Mbps", text)
        self.assertIn("Berlin", text)
        self.assertIn("github.com", text)

    def test_with_packet_loss(self):
        text = format_share_text(
            ping_ms=15.0, jitter_ms=2.0,
            download_mbps=100.0, upload_mbps=50.0,
            server_name="Test", server_sponsor="ISP",
            packet_loss=5.0,
        )
        self.assertIn("5.0%", text)

    def test_no_packet_loss(self):
        text = format_share_text(
            ping_ms=15.0, jitter_ms=2.0,
            download_mbps=100.0, upload_mbps=50.0,
            server_name="Test", server_sponsor="ISP",
            packet_loss=0.0,
        )
        self.assertNotIn("Packet Loss", text)


if __name__ == "__main__":
    unittest.main()
