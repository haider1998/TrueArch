"""Phase A2: staleness must reflect real DATA age, not score-computation time.

Regression guard for the bug where last_computed/valid_until were reset to
`today` on every server start, making everything report "fresh" forever.
"""
from datetime import timedelta

import pytest

from src.scoring.engine import ScoringEngine


@pytest.fixture()
def framework(loaded_frameworks):
    return loaded_frameworks["langgraph"]


def _engine_n_days_after_data(framework, n_days):
    """A scoring engine whose 'today' is n_days after the framework's data date."""
    base = ScoringEngine()
    data_date = base._data_date(framework)
    return ScoringEngine(today=data_date + timedelta(days=n_days)), data_date


@pytest.mark.parametrize(
    "days_old,expected_status,warning_expected",
    [
        (5, "fresh", False),
        (20, "acceptable", False),
        (45, "stale", True),
        (90, "expired", True),
    ],
)
def test_staleness_tracks_real_data_age(framework, days_old, expected_status, warning_expected):
    engine, _ = _engine_n_days_after_data(framework, days_old)
    scores = engine.compute_scores(framework)
    assert scores.staleness_status == expected_status
    assert (scores.staleness_warning is not None) == warning_expected


def test_valid_until_keys_off_data_date_not_process_start(framework):
    """valid_until must be data_date + 30d, so a restart cannot 'refresh' old data."""
    engine, data_date = _engine_n_days_after_data(framework, 100)
    scores = engine.compute_scores(framework)
    assert scores.valid_until == data_date + timedelta(days=30)
    # 100-day-old data is well past validity even though we just computed it.
    assert scores.valid_until < engine.today
    # last_computed honestly records the (recent) computation time.
    assert scores.last_computed == engine.today


def test_recommend_ai_stack_warns_when_catalog_is_stale():
    """The shipped catalog was last validated 2026-05-16; against the real
    'today' (>30 days later) recommend_ai_stack must surface a staleness warning.
    This is the exact scenario the old code silently reported as 'fresh'.
    """
    from datetime import date

    import src.mcp.server as server

    # Precondition: at least one framework's data really is >30 days old today.
    any_stale = any(
        fw.computed_scores.valid_until and fw.computed_scores.valid_until < date.today()
        for fw in server._frameworks.values()
    )
    result = server.recommend_ai_stack(problem="Build a multi-agent support platform")
    if any_stale:
        assert "staleness_warning" in result, (
            "Catalog has stale frameworks but recommend_ai_stack did not warn."
        )
