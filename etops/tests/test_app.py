"""Headless smoke test of the Streamlit app via streamlit.testing."""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def app():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    return at


def test_app_runs_on_sample(app):
    metrics = {m.label: m.value for m in app.metric}
    assert metrics["Route"] == "Not fully covered"
    assert metrics["Gaps"] == "1"
    assert metrics["Waypoints covered"] == "8 / 9"


def test_coverage_table(app):
    df = app.dataframe[0].value
    assert len(df) == 9
    assert list(df["Covered"]) == [False] + [True] * 8


def test_stepping_through_every_snapshot(app):
    slider = app.select_slider[0]
    for option in slider.options[1:]:
        slider.set_value(option).run()
        assert not app.exception, app.exception
        wind = app.dataframe[0].value  # per-snapshot wind table appears first
        assert len(wind) == 5
