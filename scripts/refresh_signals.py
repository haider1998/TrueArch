#!/usr/bin/env python3
"""
TrueArch Data Refresh Script.

Semi-automated refresh of framework signal data.
Checks all YAML files for staleness and generates a report of what needs updating.

Usage:
    python scripts/refresh_signals.py                    # Check staleness
    python scripts/refresh_signals.py --update-dates     # Reset signals_date to today
    python scripts/refresh_signals.py --report           # Generate Markdown report

Design:
    Phase 1 (current): Manual refresh with automated staleness detection and date stamping.
    Phase 2 (future):  Automated signal collection from GitHub API, PyPI, etc.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

# ── Config ────────────────────────────────────────────────────────────────────

_DATA_DIR = Path(os.environ.get("TRUEARCH_DATA_DIR", "data/frameworks"))
_STALE_THRESHOLD_DAYS = 30       # Per SCORING_FORMULA.md
_WARNING_THRESHOLD_DAYS = 21     # Warn at 3 weeks

# Signals fields that contain signals_date
_SIGNAL_GROUPS = [
    "production_stability",
    "ecosystem_momentum",
    "migration_risk",
    "governance_readiness",
    "agent_compatibility",
]


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _save_yaml(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def check_staleness(data_dir: Path) -> list[dict]:
    """Check all framework YAMLs for signal staleness. Returns a list of findings."""
    today = date.today()
    findings = []

    yaml_files = sorted(data_dir.glob("*.yaml"))
    for path in yaml_files:
        if path.name == "schema.yaml":
            continue

        data = _load_yaml(path)
        fw_id = data.get("id", path.stem)
        fw_name = data.get("name", fw_id)
        curation = data.get("curation", {})
        curation_status = curation.get("status", "unknown")
        last_validated = curation.get("last_validated")
        next_due = curation.get("next_validation_due")

        # Check each signal group for staleness
        signals = data.get("signals", {})
        oldest_signal_date = None
        stale_groups = []

        for group_name in _SIGNAL_GROUPS:
            group = signals.get(group_name, {})
            sig_date_str = group.get("signals_date")
            if sig_date_str:
                sig_date = date.fromisoformat(str(sig_date_str))
                age_days = (today - sig_date).days

                if oldest_signal_date is None or sig_date < oldest_signal_date:
                    oldest_signal_date = sig_date

                if age_days > _STALE_THRESHOLD_DAYS:
                    stale_groups.append((group_name, age_days))

        # Overall staleness
        if oldest_signal_date:
            overall_age = (today - oldest_signal_date).days
        else:
            overall_age = -1  # No date found

        status = "fresh"
        if overall_age > _STALE_THRESHOLD_DAYS:
            status = "stale"
        elif overall_age > _WARNING_THRESHOLD_DAYS:
            status = "warning"

        findings.append({
            "framework_id": fw_id,
            "framework_name": fw_name,
            "file": path.name,
            "curation_status": curation_status,
            "last_validated": str(last_validated) if last_validated else "N/A",
            "next_due": str(next_due) if next_due else "N/A",
            "oldest_signal_date": str(oldest_signal_date) if oldest_signal_date else "N/A",
            "age_days": overall_age,
            "status": status,
            "stale_groups": stale_groups,
        })

    return findings


def update_signal_dates(data_dir: Path) -> list[str]:
    """Reset all signals_date fields to today. Returns list of updated files."""
    today_str = date.today().isoformat()
    updated = []

    for path in sorted(data_dir.glob("*.yaml")):
        if path.name == "schema.yaml":
            continue

        data = _load_yaml(path)
        modified = False

        signals = data.get("signals", {})
        for group_name in _SIGNAL_GROUPS:
            group = signals.get(group_name, {})
            if "signals_date" in group:
                group["signals_date"] = today_str
                modified = True

        # Also update curation metadata
        curation = data.get("curation", {})
        if curation:
            curation["last_validated"] = today_str
            next_due = date.today() + timedelta(days=30)
            curation["next_validation_due"] = next_due.isoformat()
            modified = True

        if modified:
            _save_yaml(path, data)
            updated.append(path.name)

    return updated


def generate_report(findings: list[dict]) -> str:
    """Generate a Markdown staleness report."""
    today_str = date.today().isoformat()
    lines = [
        f"# TrueArch Signal Freshness Report",
        f"",
        f"**Generated:** {today_str}  ",
        f"**Stale threshold:** {_STALE_THRESHOLD_DAYS} days  ",
        f"**Warning threshold:** {_WARNING_THRESHOLD_DAYS} days  ",
        f"",
    ]

    # Summary
    stale_count = sum(1 for f in findings if f["status"] == "stale")
    warning_count = sum(1 for f in findings if f["status"] == "warning")
    fresh_count = sum(1 for f in findings if f["status"] == "fresh")

    lines += [
        f"## Summary",
        f"",
        f"| Status | Count |",
        f"|--------|-------|",
        f"| 🟢 Fresh | {fresh_count} |",
        f"| 🟡 Warning (>{_WARNING_THRESHOLD_DAYS}d) | {warning_count} |",
        f"| 🔴 Stale (>{_STALE_THRESHOLD_DAYS}d) | {stale_count} |",
        f"| **Total** | **{len(findings)}** |",
        f"",
    ]

    # Detail table
    lines += [
        f"## Detail",
        f"",
        f"| Framework | Status | Age (days) | Last Validated | Stale Groups |",
        f"|-----------|--------|-----------|----------------|--------------|",
    ]

    icon_map = {"fresh": "🟢", "warning": "🟡", "stale": "🔴"}
    for f in sorted(findings, key=lambda x: x["age_days"], reverse=True):
        icon = icon_map.get(f["status"], "❓")
        stale_str = ", ".join(g for g, _ in f["stale_groups"]) if f["stale_groups"] else "—"
        lines.append(
            f"| {f['framework_name']} | {icon} {f['status']} | {f['age_days']} | {f['last_validated']} | {stale_str} |"
        )

    lines += ["", f"*Run `python scripts/refresh_signals.py --update-dates` to stamp all signals as refreshed.*"]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="TrueArch signal freshness checker")
    parser.add_argument("--update-dates", action="store_true",
                        help="Reset all signals_date and curation dates to today")
    parser.add_argument("--report", action="store_true",
                        help="Generate a Markdown freshness report to stdout")
    parser.add_argument("--data-dir", type=str, default=None,
                        help=f"Framework data directory (default: {_DATA_DIR})")
    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else _DATA_DIR

    if not data_dir.exists():
        print(f"Error: data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    if args.update_dates:
        updated = update_signal_dates(data_dir)
        print(f"Updated signals_date in {len(updated)} files:")
        for name in updated:
            print(f"  ✓ {name}")
        return

    findings = check_staleness(data_dir)

    if args.report:
        print(generate_report(findings))
        return

    # Default: console summary
    stale = [f for f in findings if f["status"] == "stale"]
    warning = [f for f in findings if f["status"] == "warning"]
    fresh = [f for f in findings if f["status"] == "fresh"]

    print(f"TrueArch Signal Freshness Check ({date.today().isoformat()})")
    print(f"  🟢 Fresh:   {len(fresh)}")
    print(f"  🟡 Warning: {len(warning)}")
    print(f"  🔴 Stale:   {len(stale)}")
    print()

    if stale:
        print("Stale frameworks (require refresh):")
        for f in stale:
            print(f"  🔴 {f['framework_name']} — {f['age_days']} days old (oldest signal: {f['oldest_signal_date']})")

    if warning:
        print("\nWarning frameworks (refresh soon):")
        for f in warning:
            print(f"  🟡 {f['framework_name']} — {f['age_days']} days old")

    if stale:
        sys.exit(1)  # Non-zero exit for CI integration


if __name__ == "__main__":
    main()
