"""Tests for version check service."""
import pytest
import requests

from services import version_service


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear cache before each test."""
    version_service.clear_cache()


def test_parse_version():
    """Test version string parsing."""
    assert version_service._parse_version("1.2.3") == (1, 2, 3)
    assert version_service._parse_version("v2.4.9.0830") == (2, 4, 8, 2154)
    assert version_service._parse_version("2.5") == (2, 5)
    assert version_service._parse_version("1.0-alpha") == (1, 0)


def test_get_latest_version_success(monkeypatch):
    """Test fetching latest version successfully."""
    mock_data = [
        {"name": "v1.0.0"},
        {"name": "v2.0.1"},
        {"name": "v2.1.0"},
        {"name": "v1.5.0"},
    ]
    
    class MockResponse:
        def __init__(self, json_data, status_code=200):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

        def raise_for_status(self):
            pass

    def mock_get(*args, **kwargs):
        return MockResponse(mock_data)

    monkeypatch.setattr(requests, "get", mock_get)

    latest = version_service.get_latest_version()
    assert latest == "2.1.0"


def test_get_latest_version_empty_tags(monkeypatch):
    """Test fetching when tags list is empty."""
    class MockResponse:
        def json(self): return []
        def raise_for_status(self): pass

    monkeypatch.setattr(requests, "get", lambda *a, **kw: MockResponse())
    assert version_service.get_latest_version() is None


def test_get_latest_version_network_error(monkeypatch):
    """Test fetching when network error occurs."""
    def mock_get(*args, **kwargs):
        raise requests.exceptions.ConnectionError("Mock failure")

    monkeypatch.setattr(requests, "get", mock_get)
    assert version_service.get_latest_version() is None


def test_get_latest_version_caching(monkeypatch):
    """Test that version is cached to prevent multiple requests."""
    call_count = 0
    
    class MockResponse:
        def json(self): return [{"name": "v3.0.0"}]
        def raise_for_status(self): pass

    def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return MockResponse()

    monkeypatch.setattr(requests, "get", mock_get)

    # First call should hit the mock API
    latest1 = version_service.get_latest_version()
    assert latest1 == "3.0.0"
    assert call_count == 1
    
    # Second call should use cache
    latest2 = version_service.get_latest_version()
    assert latest2 == "3.0.0"
    assert call_count == 1
    
    # Verify cache returns same even on network error
    def mock_get_error(*args, **kwargs):
        raise requests.exceptions.ConnectionError()
    
    monkeypatch.setattr(requests, "get", mock_get_error)
    latest3 = version_service.get_latest_version()
    assert latest3 == "3.0.0"


def test_check_update_available(monkeypatch):
    """Test the update availability logic."""
    # Mock current version
    monkeypatch.setattr(version_service, "VERSION", "1.5.0")
    
    # Function to mock latest version
    def _mock_latest(version):
        monkeypatch.setattr(version_service, "get_latest_version", lambda: version)

    # Test update available
    _mock_latest("2.0.0")
    avail, cur, latest = version_service.check_update_available()
    assert avail is True
    assert cur == "1.5.0"
    assert latest == "2.0.0"
    
    # Test update available (patch version)
    _mock_latest("1.5.1")
    avail, cur, latest = version_service.check_update_available()
    assert avail is True
    
    # Test no update (same version)
    _mock_latest("1.5.0")
    avail, cur, latest = version_service.check_update_available()
    assert avail is False
    
    # Test no update (older version somehow on GitHub)
    _mock_latest("1.4.9")
    avail, cur, latest = version_service.check_update_available()
    assert avail is False

    # Test when API fails
    _mock_latest(None)
    avail, cur, latest = version_service.check_update_available()
    assert avail is False
    assert latest is None
