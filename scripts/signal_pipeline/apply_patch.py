"""
TrueArch Signal Patch Applier

Applies a signal patch (produced by pipeline.py) to the framework YAML files —
but ONLY objective, crawlable fields. Subjective/curated fields (breaking-change
counts, incident rates, known issues, deprecated patterns, human ratings) are
never touched, so automation can keep versions/stars fresh without overwriting
human judgement.

Comments in the YAML are preserved (ruamel.yaml round-trip).

Usage:
    # Apply the latest patch in data/signal_patches/:
    python scripts/signal_pipeline/apply_patch.py

    # Apply a specific patch file:
    python scripts/signal_pipeline/apply_patch.py --patch data/signal_patches/2026-07-18.json

    # Show what would change without writing:
    python scripts/signal_pipeline/apply_patch.py --dry-run
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from ruamel.yaml import YAML

_ROOT = Path(__file__).resolve().parent.parent.parent
_FRAMEWORKS_DIR = _ROOT / "data" / "frameworks"

# Objective fields we allow automation to write, grouped by their location in the
# YAML. Everything not listed here is off-limits to the applier.
_TOPLEVEL_FIELDS = {"latest_stable_version", "latest_stable_released"}
_ECOSYSTEM_FIELDS = {
    "github_stars",
    "commits_last_90d",
    "commits_prev_90d",
    "merged_prs_per_30d",
    "avg_days_to_merge",
}
_PRODUCTION_FIELDS = {"open_security_advisories"}

_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.width = 4096  # don't wrap long lines


def _latest_patch_file() -> Optional[Path]:
    files = sorted(glob.glob(str(_ROOT / "data" / "signal_patches" / "*.json")))
    return Path(files[-1]) if files else None


def _merged_signals(patch: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten a framework's github + pypi crawler output into one dict.
    PyPI wins for version fields (canonical release), GitHub fills the rest."""
    merged: Dict[str, Any] = {}
    gh = patch.get("github_signals") or {}
    pypi = patch.get("pypi_signals") or {}
    merged.update(gh)
    # PyPI release info is more authoritative for the published version.
    for k in ("latest_stable_version", "latest_stable_released", "signals_date"):
        if pypi.get(k):
            merged[k] = pypi[k]
    return merged


def _apply_to_framework(doc: Any, signals: Dict[str, Any], run_date: str) -> List[str]:
    """Mutate a loaded YAML doc in place. Returns a list of human-readable changes."""
    changes: List[str] = []

    def _set(container, key, new):
        old = container.get(key)
        if new is not None and str(old) != str(new):
            container[key] = new
            changes.append(f"{key}: {old} → {new}")

    # Top-level version fields
    for f in _TOPLEVEL_FIELDS:
        if f in signals:
            _set(doc, f, signals[f])

    sig = doc.get("signals", {})
    signals_date = signals.get("signals_date")

    eco = sig.get("ecosystem_momentum")
    if eco is not None:
        for f in _ECOSYSTEM_FIELDS:
            if f in signals:
                _set(eco, f, signals[f])
        if signals_date and any(f in signals for f in _ECOSYSTEM_FIELDS):
            _set(eco, "signals_date", signals_date)

    prod = sig.get("production_stability")
    if prod is not None:
        for f in _PRODUCTION_FIELDS:
            if f in signals:
                _set(prod, f, signals[f])
        if signals_date and any(f in signals for f in _PRODUCTION_FIELDS):
            _set(prod, "signals_date", signals_date)

    return changes


def _bump_curation(doc: Any, run_date: str) -> None:
    """Mark the framework as freshly validated by automation."""
    cur = doc.get("curation")
    if cur is None:
        return
    cur["last_validated"] = run_date
    cur["validated_by"] = "automated"
    try:
        d = datetime.strptime(run_date, "%Y-%m-%d").date()
        cur["next_validation_due"] = (d + timedelta(days=30)).isoformat()
    except ValueError:
        pass


def apply_patch(patch_path: Path, dry_run: bool = False) -> Dict[str, Any]:
    with open(patch_path) as f:
        payload = json.load(f)

    run_date = (payload.get("generated") or datetime.utcnow().isoformat())[:10]
    patches = payload.get("patches", [])

    summary = {"applied": 0, "skipped": 0, "unchanged": 0, "details": {}}

    for patch in patches:
        fid = patch.get("framework_id")
        status = patch.get("status")
        yaml_path = _FRAMEWORKS_DIR / f"{fid}.yaml"

        # Only apply for frameworks that crawled cleanly and have a YAML file.
        if status not in ("ok", "partial") or not yaml_path.exists():
            summary["skipped"] += 1
            continue

        signals = _merged_signals(patch)
        if not signals:
            summary["skipped"] += 1
            continue

        with open(yaml_path) as f:
            doc = _yaml.load(f)

        changes = _apply_to_framework(doc, signals, run_date)
        if changes:
            _bump_curation(doc, run_date)
            summary["applied"] += 1
            summary["details"][fid] = changes
            if not dry_run:
                with open(yaml_path, "w") as f:
                    _yaml.dump(doc, f)
        else:
            summary["unchanged"] += 1

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply a TrueArch signal patch to YAML")
    parser.add_argument("--patch", help="Patch JSON file (default: latest in data/signal_patches/)")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    args = parser.parse_args()

    patch_path = Path(args.patch) if args.patch else _latest_patch_file()
    if not patch_path or not patch_path.exists():
        print("No patch file found. Run pipeline.py first.")
        sys.exit(1)

    print(f"Applying patch: {patch_path}" + ("  [DRY RUN]" if args.dry_run else ""))
    summary = apply_patch(patch_path, dry_run=args.dry_run)

    for fid, changes in summary["details"].items():
        print(f"\n  [{fid}]")
        for c in changes:
            print(f"    • {c}")

    print(
        f"\n  Applied: {summary['applied']}  |  Unchanged: {summary['unchanged']}  "
        f"|  Skipped: {summary['skipped']}"
    )
    if not args.dry_run and summary["applied"]:
        print("  ✅ Objective signal fields updated. Subjective fields untouched.")


if __name__ == "__main__":
    main()
