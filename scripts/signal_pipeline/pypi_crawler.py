"""
TrueArch PyPI Signal Crawler

Fetches latest version and release date from PyPI for Python packages.

Usage:
    python scripts/signal_pipeline/pypi_crawler.py --package langgraph
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime
from typing import Any, Dict, Optional


PYPI_API_BASE = "https://pypi.org/pypi"


def _pypi_get(package: str) -> Optional[Dict[str, Any]]:
    url = f"{PYPI_API_BASE}/{package}/json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"  Package '{package}' not found on PyPI.")
        else:
            print(f"  HTTP {e.code} fetching {url}")
    except Exception as ex:
        print(f"  Error: {ex}")
    return None


def fetch_pypi_signals(package: str) -> Dict[str, Any]:
    """
    Fetch version and release signals for a PyPI package.

    Args:
        package: PyPI package name (e.g., 'langgraph', 'pinecone-client').

    Returns:
        Dict with latest_stable_version, latest_stable_released, download signals.
    """
    print(f"  Fetching PyPI data for: {package}")
    data = _pypi_get(package)
    if not data:
        return {"error": f"Package '{package}' not found on PyPI."}

    info = data.get("info", {})
    releases = data.get("releases", {})

    latest_version = info.get("version", "unknown")

    # Find release date for the latest version
    latest_released = None
    if latest_version in releases:
        release_files = releases[latest_version]
        if release_files:
            upload_time = release_files[0].get("upload_time", "")
            if upload_time:
                try:
                    dt = datetime.strptime(upload_time, "%Y-%m-%dT%H:%M:%S")
                    latest_released = dt.strftime("%Y-%m-%d")
                except ValueError:
                    latest_released = upload_time[:10]

    # Count total releases (proxy for project age/activity)
    total_versions = len([v for v in releases.keys() if releases[v]])

    result = {
        "latest_stable_version": latest_version,
        "latest_stable_released": latest_released or "unknown",
        "total_versions_on_pypi": total_versions,
        "package_url": info.get("package_url", f"https://pypi.org/project/{package}"),
        "signals_date": datetime.utcnow().strftime("%Y-%m-%d"),
    }

    print(f"  ✓ Latest: {latest_version}  |  Released: {latest_released}  |  Total versions: {total_versions}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch PyPI signals for a Python package.")
    parser.add_argument("--package", required=True, help="PyPI package name (e.g., langgraph)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    result = fetch_pypi_signals(args.package)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("\n  Signal Patch for YAML:")
        print("  " + "-" * 40)
        for k, v in result.items():
            print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
