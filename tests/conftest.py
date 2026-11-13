"""Shared pytest configuration: the tier markers.

Tiers are folders (tests/unit, tests/component); the matching marker is applied from the path, so
`pytest -m unit` and `pytest tests/unit` mean the same thing."""
import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        parts = item.path.parts
        for tier in ("unit", "component"):
            if tier in parts[parts.index("tests") + 1:parts.index("tests") + 2]:
                item.add_marker(getattr(pytest.mark, tier))
