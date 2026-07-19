"""Phase C: the signal-patch applier must only touch objective fields and must
preserve the hand-curated YAML (comments included)."""
import json
from pathlib import Path

import pytest

from scripts.signal_pipeline import apply_patch as ap


_FIXTURE_YAML = """\
# Curated framework — DO NOT DELETE THIS COMMENT
schema_version: "1.0"
id: demo
name: Demo
latest_stable_version: "1.0.0"   # inline comment must survive
latest_stable_released: "2026-01-01"

signals:
  production_stability:
    open_security_advisories: 0
    breaking_changes_per_90d: 3   # subjective — must NOT change
    signals_date: "2026-01-01"
  ecosystem_momentum:
    github_stars: 100
    commits_last_90d: 10
    signals_date: "2026-01-01"

known_issues:
  - id: DEMO-001            # subjective — must NOT change
    severity: high

curation:
  status: curated
  last_validated: "2026-01-01"
  validated_by: founder
  next_validation_due: "2026-01-31"
"""


@pytest.fixture()
def framework_file(tmp_path, monkeypatch):
    fdir = tmp_path / "frameworks"
    fdir.mkdir()
    yaml_file = fdir / "demo.yaml"
    yaml_file.write_text(_FIXTURE_YAML)
    monkeypatch.setattr(ap, "_FRAMEWORKS_DIR", fdir)
    return yaml_file


def _write_patch(tmp_path):
    patch = {
        "generated": "2026-07-18T00:00:00",
        "patches": [
            {
                "framework_id": "demo",
                "status": "ok",
                "github_signals": {
                    "github_stars": 250,
                    "commits_last_90d": 42,
                    # An attempt to sneak a subjective field through must be ignored.
                    "breaking_changes_per_90d": 99,
                    "signals_date": "2026-07-18",
                },
                "pypi_signals": {
                    "latest_stable_version": "2.0.0",
                    "latest_stable_released": "2026-07-01",
                    "signals_date": "2026-07-18",
                },
            }
        ],
    }
    p = tmp_path / "patch.json"
    p.write_text(json.dumps(patch))
    return p


def test_apply_updates_only_objective_fields(framework_file, tmp_path):
    patch_path = _write_patch(tmp_path)
    summary = ap.apply_patch(patch_path, dry_run=False)

    assert summary["applied"] == 1
    doc = ap._yaml.load(framework_file.read_text())

    # Objective fields updated
    assert str(doc["latest_stable_version"]) == "2.0.0"
    assert str(doc["latest_stable_released"]) == "2026-07-01"
    assert doc["signals"]["ecosystem_momentum"]["github_stars"] == 250
    assert doc["signals"]["ecosystem_momentum"]["commits_last_90d"] == 42

    # Subjective fields untouched, even though the patch tried to change one
    assert doc["signals"]["production_stability"]["breaking_changes_per_90d"] == 3
    assert doc["known_issues"][0]["id"] == "DEMO-001"


def test_apply_bumps_curation_to_automated(framework_file, tmp_path):
    ap.apply_patch(_write_patch(tmp_path), dry_run=False)
    doc = ap._yaml.load(framework_file.read_text())
    assert doc["curation"]["validated_by"] == "automated"
    assert str(doc["curation"]["last_validated"]) == "2026-07-18"
    assert str(doc["curation"]["next_validation_due"]) == "2026-08-17"


def test_apply_preserves_comments(framework_file, tmp_path):
    ap.apply_patch(_write_patch(tmp_path), dry_run=False)
    text = framework_file.read_text()
    assert "# Curated framework — DO NOT DELETE THIS COMMENT" in text
    assert "subjective — must NOT change" in text


def test_dry_run_writes_nothing(framework_file, tmp_path):
    before = framework_file.read_text()
    ap.apply_patch(_write_patch(tmp_path), dry_run=True)
    assert framework_file.read_text() == before


def test_error_status_is_skipped(framework_file, tmp_path):
    patch = {
        "generated": "2026-07-18T00:00:00",
        "patches": [{"framework_id": "demo", "status": "error", "github_signals": None}],
    }
    p = tmp_path / "p.json"
    p.write_text(json.dumps(patch))
    summary = ap.apply_patch(p, dry_run=False)
    assert summary["skipped"] == 1
    assert summary["applied"] == 0
