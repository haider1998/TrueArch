"""
TrueArch npm Signal Crawler

Fetches latest version and release date from the npm registry for JS/TS packages
(e.g. Vercel AI SDK, Mastra). Mirrors pypi_crawler.py.

Usage:
    python scripts/signal_pipeline/npm_crawler.py --package ai
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, Optional


NPM_REGISTRY_BASE = "https://registry.npmjs.org"


def _npm_get(package: str) -> Optional[Dict[str, Any]]:
    # URL-encode scoped packages (@scope/name → @scope%2Fname)
    encoded = package.replace("/", "%2F")
    url = f"{NPM_REGISTRY_BASE}/{encoded}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"  Package '{package}' not found on npm.")
        else:
            print(f"  HTTP {e.code} fetching {url}")
    except Exception as ex:
        print(f"  Error: {ex}")
    return None


def fetch_npm_signals(package: str) -> Dict[str, Any]:
    """Fetch version and release signals for an npm package."""
    print(f"  Fetching npm data for: {package}")
    data = _npm_get(package)
    if not data:
        return {"error": f"Package '{package}' not found on npm."}

    dist_tags = data.get("dist-tags", {})
    latest_version = dist_tags.get("latest", "unknown")

    time_map = data.get("time", {})
    latest_released = None
    if latest_version in time_map:
        ts = time_map[latest_version]
        latest_released = ts[:10] if ts else None

    total_versions = len(data.get("versions", {}) or {})

    result = {
        "latest_stable_version": latest_version,
        "latest_stable_released": latest_released or "unknown",
        "total_versions_on_npm": total_versions,
        "package_url": f"https://www.npmjs.com/package/{package}",
        "signals_date": datetime.utcnow().strftime("%Y-%m-%d"),
    }

    print(f"  ✓ Latest: {latest_version}  |  Released: {latest_released}  |  Total versions: {total_versions}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch npm signals for a JS/TS package.")
    parser.add_argument("--package", required=True, help="npm package name (e.g., ai, @mastra/core)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    result = fetch_npm_signals(args.package)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("\n  Signal Patch for YAML:")
        print("  " + "-" * 40)
        for k, v in result.items():
            print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
