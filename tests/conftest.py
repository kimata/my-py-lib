#!/usr/bin/env python3
from __future__ import annotations

from typing import Any, Generator

import pytest
from playwright.sync_api import Page


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--host", default="127.0.0.1")
    parser.addoption("--port", default="5000")
    parser.addoption("--run-mercari", action="store_true", default=False, help="run mercari tests")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "mercari: mark test as mercari test (deselected by default)")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-mercari"):
        return
    skip_mercari = pytest.mark.skip(reason="need --run-mercari option to run")
    for item in items:
        if "mercari" in item.keywords:
            item.add_marker(skip_mercari)


@pytest.fixture
def host(request: pytest.FixtureRequest) -> str:
    return request.config.getoption("--host")


@pytest.fixture
def port(request: pytest.FixtureRequest) -> str:
    return request.config.getoption("--port")


@pytest.fixture
def page(page: Page) -> Page:
    from playwright.sync_api import expect

    timeout = 5000
    page.set_default_navigation_timeout(timeout)
    page.set_default_timeout(timeout)
    expect.set_options(timeout=timeout)

    return page


@pytest.fixture
def browser_context_args(browser_context_args: dict[str, Any], request: pytest.FixtureRequest) -> dict[str, Any]:
    return {
        **browser_context_args,
        "record_video_dir": f"tests/evidence/{request.node.name}",
        "record_video_size": {"width": 2400, "height": 1600},
    }
