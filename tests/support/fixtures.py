"""Shared fixtures. A tier/component conftest opts in with:  from support.fixtures import _cwd_in_src  # noqa: F401"""
import os

import pytest

from support.paths import SRC


@pytest.fixture(autouse=True)
def _cwd_in_src():
    """Runs each test with cwd=src/. A few tests were written against it. pytest runs from the repo root, so this sets it for each
    test and restores it after."""
    prev = os.getcwd()
    os.chdir(SRC)
    try:
        yield
    finally:
        os.chdir(prev)
