"""Tests for config/types.py - ensure_utc function."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from config.types import ensure_utc


class TestEnsureUtc:
    """Test ensure_utc function."""

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
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12
        assert result.minute == 30
        assert result.second == 45

    def test_utc_datetime(self) -> None:
        """Test that UTC datetime is returned as-is."""
        utc_dt = datetime(2025, 1, 15, 12, 30, 45, tzinfo=timezone.utc)
        result = ensure_utc(utc_dt)
        
        assert result is not None
        assert result == utc_dt
        assert result.tzinfo == timezone.utc

    def test_aware_datetime_with_offset(self) -> None:
        """Test that aware datetime with offset is returned as-is."""
        # Create datetime with +05:00 offset
        offset = timezone(timedelta(hours=5))
        aware_dt = datetime(2025, 1, 15, 12, 30, 45, tzinfo=offset)
        result = ensure_utc(aware_dt)
        
        assert result is not None
        assert result == aware_dt
        assert result.tzinfo == offset

    def test_aware_datetime_with_negative_offset(self) -> None:
        """Test that aware datetime with negative offset is returned as-is."""
        # Create datetime with -08:00 offset
        offset = timezone(timedelta(hours=-8))
        aware_dt = datetime(2025, 1, 15, 12, 30, 45, tzinfo=offset)
        result = ensure_utc(aware_dt)
        
        assert result is not None
        assert result == aware_dt
        assert result.tzinfo == offset

    def test_naive_datetime_preserves_components(self) -> None:
        """Test that naive datetime conversion preserves all components."""
        naive_dt = datetime(2024, 12, 31, 23, 59, 59, 999999)
        result = ensure_utc(naive_dt)
        
        assert result is not None
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 31
        assert result.hour == 23
        assert result.minute == 59
        assert result.second == 59
        assert result.microsecond == 999999

    def test_naive_datetime_has_utc_timezone(self) -> None:
        """Test that converted naive datetime has UTC timezone."""
        naive_dt = datetime(2025, 6, 15, 10, 0, 0)
        result = ensure_utc(naive_dt)
        
        assert result is not None
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc
        assert result.utcoffset() == timedelta(0)

    def test_multiple_calls_same_result(self) -> None:
        """Test that multiple calls with same input return same result."""
        naive_dt = datetime(2025, 1, 1, 0, 0, 0)
        result1 = ensure_utc(naive_dt)
        result2 = ensure_utc(naive_dt)
        
        assert result1 == result2
        assert result1.tzinfo == result2.tzinfo

    def test_different_naive_datetimes(self) -> None:
        """Test with different naive datetime values."""
        test_cases = [
            datetime(2020, 1, 1, 0, 0, 0),
            datetime(2025, 6, 15, 12, 30, 45),
            datetime(2030, 12, 31, 23, 59, 59),
        ]
        
        for naive_dt in test_cases:
            result = ensure_utc(naive_dt)
            assert result is not None
            assert result.tzinfo == timezone.utc
            assert result.year == naive_dt.year
            assert result.month == naive_dt.month
            assert result.day == naive_dt.day
