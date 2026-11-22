"""Smoke tests for bicopter_host package scaffolding."""

import bicopter_host


def test_package_version() -> None:
    """Verify package imports cleanly and exposes a version string."""
    assert isinstance(bicopter_host.__version__, str)
    assert bicopter_host.__version__ == "0.1.0"
