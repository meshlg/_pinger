"""Tests for ui/helpers.py."""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from ui.helpers import (
    fmt_uptime,
    fmt_since,
    fmt_bytes,
    progress_bar,
    sparkline,
    sparkline_mini,
    sparkline_double,
    mini_gauge,
    dns_mini_bar,
    kv_table,
    dual_kv_table,
    section_header,
    truncate,
    render_trend_arrow,
    lat_color,
    get_connection_state,
    ensure_utc,
)
from ui.theme import GREEN, YELLOW, RED


class TestFmtUptime:
    """Test fmt_uptime function."""

    def test_none_input(self) -> None:
        """Test that None input returns 'N/A'."""
        result = fmt_uptime(None)
        assert result == "N/A"

    def test_seconds_only(self) -> None:
        """Test formatting with seconds only."""
        start = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        # Mock datetime.now to return a time 45 seconds later
        import unittest.mock
        with unittest.mock.patch('ui.helpers.datetime') as mock_dt:
            mock_dt.now.return_value = start.replace(second=45)
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            result = fmt_uptime(start)
            # Check that result contains time components (may be localized)
            assert "45" in result
            assert len(result) > 0

    def test_minutes_and_seconds(self) -> None:
        """Test formatting with minutes and seconds."""
        start = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        import unittest.mock
        with unittest.mock.patch('ui.helpers.datetime') as mock_dt:
            mock_dt.now.return_value = start.replace(minute=2, second=30)
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            result = fmt_uptime(start)
            # Check that result contains time components (may be localized)
            assert "2" in result
            assert "30" in result
            assert len(result) > 0

    def test_hours_minutes_seconds(self) -> None:
        """Test formatting with hours, minutes, and seconds."""
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        import unittest.mock
        with unittest.mock.patch('ui.helpers.datetime') as mock_dt:
            mock_dt.now.return_value = start.replace(hour=1, minute=30, second=45)
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            result = fmt_uptime(start)
            # Check that result contains time components (may be localized)
            assert "1" in result
            assert "30" in result
            assert "45" in result
            assert len(result) > 0


class TestFmtSince:
    """Test fmt_since function."""

    def test_none_input(self) -> None:
        """Test that None input returns localized 'never'."""
        result = fmt_since(None)
        # Result is localized, just check it's not empty
        assert len(result) > 0

    def test_just_now(self) -> None:
        """Test formatting for very recent time."""
        now = datetime.now(timezone.utc)
        result = fmt_since(now)
        # Result is localized, just check it's not empty
        assert len(result) > 0

    def test_seconds_ago(self) -> None:
        """Test formatting for seconds ago."""
        import unittest.mock
        now = datetime.now(timezone.utc)
        with unittest.mock.patch('ui.helpers.datetime') as mock_dt:
            mock_dt.now.return_value = now + timedelta(seconds=10)
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            result = fmt_since(now)
            # Result is localized, just check it contains the number
            assert "10" in result
            assert len(result) > 0

    def test_minutes_ago(self) -> None:
        """Test formatting for minutes ago."""
        import unittest.mock
        now = datetime.now(timezone.utc)
        with unittest.mock.patch('ui.helpers.datetime') as mock_dt:
            mock_dt.now.return_value = now + timedelta(minutes=5)
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            result = fmt_since(now)
            # Result is localized, just check it contains the number
            assert "5" in result
            assert len(result) > 0


class TestFmtBytes:
    """Test fmt_bytes helper."""

    def test_none_input(self) -> None:
        """Test that None returns localized N/A."""
        assert fmt_bytes(None) == "N/A"

    def test_bytes_input(self) -> None:
        """Test formatting in bytes."""
        assert fmt_bytes(512) == "512 B"

    def test_kibibytes_input(self) -> None:
        """Test formatting in KiB."""
        assert fmt_bytes(2048) == "2.0 KiB"


class TestProgressBar:
    """Test progress_bar function."""

    def test_zero_percent(self) -> None:
        """Test progress bar at 0%."""
        result = progress_bar(0.0, width=10)
        assert "[" in result
        assert "]" in result

    def test_fifty_percent(self) -> None:
        """Test progress bar at 50%."""
        result = progress_bar(50.0, width=10)
        assert "[" in result
        assert "]" in result
        assert "━" in result
        assert "─" in result
        assert "█" not in result

    def test_width_is_clamped(self) -> None:
        """Test progress bar width is capped for cleaner layout."""
        result = progress_bar(50.0, width=100)
        assert result.count("━") == 14
        assert result.count("─") == 14

    def test_hundred_percent(self) -> None:
        """Test progress bar at 100%."""
        result = progress_bar(100.0, width=10)
        assert "[" in result
        assert "]" in result

    def test_negative_percent(self) -> None:
        """Test progress bar with negative percent (should clamp to 0)."""
        result = progress_bar(-10.0, width=10)
        assert "[" in result
        assert "]" in result

    def test_over_hundred_percent(self) -> None:
        """Test progress bar with over 100% (should clamp to 100)."""
        result = progress_bar(150.0, width=10)
        assert "[" in result
        assert "]" in result


class TestSparkline:
    """Test sparkline function."""

    def test_empty_list(self) -> None:
        """Test sparkline with empty list."""
        result = sparkline([])
        # Result is localized, just check it's not empty
        assert len(result) > 0

    def test_single_value(self) -> None:
        """Test sparkline with single value."""
        result = sparkline([10.0])
        # Result is localized, just check it's not empty
        assert len(result) > 0

    def test_two_values(self) -> None:
        """Test sparkline with two values."""
        result = sparkline([10.0, 20.0])
        assert len(result) > 0

    def test_multiple_values(self) -> None:
        """Test sparkline with multiple values."""
        result = sparkline([10.0, 20.0, 30.0, 40.0, 50.0])
        assert len(result) > 0

    def test_zero_values(self) -> None:
        """Test sparkline with zero values."""
        result = sparkline([0.0, 0.0, 0.0])
        assert len(result) > 0


class TestSparklineMini:
    """Test sparkline_mini function."""

    def test_empty_list(self) -> None:
        """Test sparkline_mini with empty list."""
        result = sparkline_mini([])
        assert result == ""

    def test_single_value(self) -> None:
        """Test sparkline_mini with single value."""
        result = sparkline_mini([10.0])
        assert result == ""

    def test_two_values(self) -> None:
        """Test sparkline_mini with two values."""
        result = sparkline_mini([10.0, 20.0])
        assert len(result) > 0


class TestSparklineDouble:
    """Test sparkline_double function."""

    def test_empty_list(self) -> None:
        """Test sparkline_double with empty list."""
        top, bottom = sparkline_double([])
        # Result is localized, just check it's not empty
        assert len(top) > 0
        assert bottom == ""

    def test_single_value(self) -> None:
        """Test sparkline_double with single value."""
        top, bottom = sparkline_double([10.0])
        # Result is localized, just check it's not empty
        assert len(top) > 0
        assert bottom == ""

    def test_multiple_values(self) -> None:
        """Test sparkline_double with multiple values."""
        top, bottom = sparkline_double([10.0, 20.0, 30.0, 40.0, 50.0])
        assert len(top) > 0
        assert len(bottom) > 0


class TestMiniGauge:
    """Test mini_gauge function."""

    def test_zero_value(self) -> None:
        """Test mini_gauge with zero value."""
        result = mini_gauge(0.0, width=10)
        assert "[" in result
        assert "]" in result

    def test_fifty_percent(self) -> None:
        """Test mini_gauge at 50%."""
        result = mini_gauge(50.0, width=10)
        assert "[" in result
        assert "]" in result
        assert "━" in result
        assert "─" in result
        assert "█" not in result

    def test_width_is_clamped(self) -> None:
        """Test mini_gauge width is capped for cleaner layout."""
        result = mini_gauge(100.0, width=100)
        assert result.count("━") == 28

    def test_hundred_percent(self) -> None:
        """Test mini_gauge at 100%."""
        result = mini_gauge(100.0, width=10)
        assert "[" in result
        assert "]" in result


class TestDnsMiniBar:
    """Test dns_mini_bar function."""

    def test_none_input(self) -> None:
        """Test dns_mini_bar with None input."""
        result = dns_mini_bar(None, width=6)
        assert "[" in result
        assert "]" in result
        assert "─" in result

    def test_width_is_clamped(self) -> None:
        """Test dns_mini_bar width is capped for cleaner layout."""
        result = dns_mini_bar(None, width=100)
        assert result.count("─") == 28

    def test_zero_ms(self) -> None:
        """Test dns_mini_bar with 0ms."""
        result = dns_mini_bar(0.0, width=6)
        assert "[" in result
        assert "]" in result

    def test_fifty_ms(self) -> None:
        """Test dns_mini_bar with 50ms (good)."""
        result = dns_mini_bar(50.0, width=6)
        assert "[" in result
        assert "]" in result

    def test_hundred_ms(self) -> None:
        """Test dns_mini_bar with 100ms (ok)."""
        result = dns_mini_bar(100.0, width=6)
        assert "[" in result
        assert "]" in result

    def test_two_hundred_ms(self) -> None:
        """Test dns_mini_bar with 200ms (slow)."""
        result = dns_mini_bar(200.0, width=6)
        assert "[" in result
        assert "]" in result


class TestKvTable:
    """Test kv_table function."""

    def test_creates_table(self) -> None:
        """Test that kv_table creates a table."""
        table = kv_table(80)
        assert table is not None


class TestDualKvTable:
    """Test dual_kv_table function."""

    def test_creates_table(self) -> None:
        """Test that dual_kv_table creates a table."""
        table = dual_kv_table(80)
        assert table is not None


class TestSectionHeader:
    """Test section_header function."""

    def test_creates_text(self) -> None:
        """Test that section_header creates text."""
        result = section_header("Test", 80)
        assert result is not None
        assert "TEST" in str(result)


class TestTruncate:
    """Test truncate function."""

    def test_short_text(self) -> None:
        """Test truncate with text shorter than max_len."""
        result = truncate("Hello", 10)
        assert result == "Hello"

    def test_exact_length(self) -> None:
        """Test truncate with text exactly at max_len."""
        result = truncate("Hello", 5)
        assert result == "Hello"

    def test_long_text(self) -> None:
        """Test truncate with text longer than max_len."""
        result = truncate("Hello World", 5)
        assert result == "Hell…"
        assert len(result) == 5

    def test_max_len_one(self) -> None:
        """Test truncate with max_len of 1."""
        result = truncate("Hello", 1)
        assert result == "H"


class TestRenderTrendArrow:
    """Test render_trend_arrow function."""

    def test_up_arrow(self) -> None:
        """Test render_trend_arrow with positive delta."""
        result = render_trend_arrow(5.0)
        assert result == "↑"

    def test_down_arrow(self) -> None:
        """Test render_trend_arrow with negative delta."""
        result = render_trend_arrow(-5.0)
        assert result == "↓"

    def test_flat_arrow(self) -> None:
        """Test render_trend_arrow with small delta."""
        result = render_trend_arrow(1.0)
        assert result == "→"


class TestLatColor:
    """Test lat_color function."""

    def test_none_value(self) -> None:
        """Test lat_color with None value."""
        result = lat_color(None)
        assert result == RED

    def test_good_latency(self) -> None:
        """Test lat_color with good latency."""
        result = lat_color(30.0)
        assert result == GREEN

    def test_ok_latency(self) -> None:
        """Test lat_color with ok latency."""
        result = lat_color(70.0)
        assert result == YELLOW

    def test_bad_latency(self) -> None:
        """Test lat_color with bad latency."""
        result = lat_color(150.0)
        assert result == RED


class TestGetConnectionState:
    """Test get_connection_state function."""

    def test_connected_state(self) -> None:
        """Test get_connection_state when connected."""
        snap = {
            "threshold_states": {"connection_lost": False},
            "recent_results": [True, True, True, True, True],
            "last_status": "OK",
        }
        label, color, icon = get_connection_state(snap)
        assert label is not None
        assert color is not None
        assert icon is not None

    def test_disconnected_state(self) -> None:
        """Test get_connection_state when disconnected."""
        snap = {
            "threshold_states": {"connection_lost": True},
            "recent_results": [False, False, False, False, False],
            "last_status": "Timeout",
        }
        label, color, icon = get_connection_state(snap)
        # Label is localized, just check it's not empty
        assert len(label) > 0
        assert color is not None
        assert icon is not None

    def test_degraded_state(self) -> None:
        """Test get_connection_state when degraded."""
        snap = {
            "threshold_states": {"connection_lost": False},
            "recent_results": [True, False, True, False, True, False, True, False, True, False],
            "last_status": "OK",
        }
        label, color, icon = get_connection_state(snap)
        assert label is not None


class TestEnsureUtc:
    """Test ensure_utc function (re-exported from config.types)."""

    def test_none_input(self) -> None:
        """Test that None input returns None."""
        result = ensure_utc(None)
        assert result is None

    def test_naive_datetime(self) -> None:
        """Test that naive datetime is converted to UTC."""
        naive_dt = datetime(2025, 1, 15, 12, 30, 45)
        result = ensure_utc(naive_dt)
        
        assert result is not None
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc
