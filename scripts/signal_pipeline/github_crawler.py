"""
TrueArch GitHub Signal Crawler

Fetches live signals for a framework from the GitHub REST API:
  - github_stars       (current star count)
  - commits_last_90d   (commit count in last 90 days)
  - merged_prs_per_30d (merged PRs in last 30 days)
  - avg_days_to_merge  (average time to merge PRs)
  - open_security_advisories (from GHSA)

No authentication required for public repos (60 requests/hour rate limit).
With GITHUB_TOKEN env var: 5000 requests/hour.

Usage:
    python scripts/signal_pipeline/github_crawler.py --repo langchain-ai/langgraph
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


GITHUB_API_BASE = "https://api.github.com"
_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def _get_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "TrueArch-Signal-Crawler/1.0",
    }
    if _TOKEN:
        headers["Authorization"] = f"Bearer {_TOKEN}"
    return headers


def _api_get(url: str, retries: int = 3) -> Optional[Any]:
    """Make a GitHub API GET request with retry."""
    req = urllib.request.Request(url, headers=_get_headers())
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 403:  # Rate limit
                reset_time = e.headers.get("X-RateLimit-Reset", 0)
                wait = max(int(reset_time) - int(time.time()), 0) + 5
                print(f"  Rate limited. Waiting {wait}s...")
                time.sleep(min(wait, 60))
            elif e.code == 404:
                print(f"  404: {url}")
                return None
            else:
                print(f"  HTTP {e.code} for {url}")
        except Exception as ex:
            print(f"  Error: {ex}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return None


def fetch_repo_signals(repo: str) -> Dict[str, Any]:
    """
    Fetch key signals for a GitHub repository.

    Args:
        repo: GitHub repo in 'owner/name' format (e.g., 'langchain-ai/langgraph').

    Returns:
        Dict of signal values ready to patch into framework YAML signals block.
    """
    print(f"  Fetching signals for: {repo}")

    # ── Basic repo info ──────────────────────────────────────────────────────
    repo_data = _api_get(f"{GITHUB_API_BASE}/repos/{repo}")
    if not repo_data:
        return {"error": f"Repo '{repo}' not found or inaccessible."}

    github_stars = repo_data.get("stargazers_count", 0)
    open_issues = repo_data.get("open_issues_count", 0)

    # ── Commit activity (last 90 days) ───────────────────────────────────────
    since_90d = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
    since_180d = (datetime.utcnow() - timedelta(days=180)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Use participation stats for commit counts (no pagination needed)
    participation = _api_get(f"{GITHUB_API_BASE}/repos/{repo}/stats/participation")
    commits_last_90d = 0
    commits_prev_90d = 0
    if participation and "all" in participation:
        weekly = participation["all"]  # 52 weeks of commit counts
        # Last 13 weeks (~90 days) vs prior 13 weeks
        commits_last_90d = sum(weekly[-13:]) if len(weekly) >= 13 else sum(weekly)
        commits_prev_90d = sum(weekly[-26:-13]) if len(weekly) >= 26 else 0

    # ── PR data (last 30 days) ───────────────────────────────────────────────
    since_30d = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Get recently merged PRs (first page only for efficiency)
    prs_data = _api_get(
        f"{GITHUB_API_BASE}/repos/{repo}/pulls"
        f"?state=closed&sort=updated&direction=desc&per_page=100"
    )

    merged_last_30d = 0
    merge_times_days: list = []
    if prs_data and isinstance(prs_data, list):
        for pr in prs_data:
            merged_at = pr.get("merged_at")
            created_at = pr.get("created_at")
            if merged_at and merged_at > since_30d:
                merged_last_30d += 1
                if created_at:
                    try:
                        mt = datetime.strptime(merged_at, "%Y-%m-%dT%H:%M:%SZ")
                        ct = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
                        merge_times_days.append((mt - ct).total_seconds() / 86400)
                    except ValueError:
                        pass

    avg_days_to_merge = (
        round(sum(merge_times_days) / len(merge_times_days), 1)
        if merge_times_days else 3.0
    )

    # ── Security advisories ──────────────────────────────────────────────────
    # GitHub Security Advisories API (public repos)
    advisories_data = _api_get(
        f"{GITHUB_API_BASE}/repos/{repo}/security-advisories"
        f"?per_page=10&state=published"
    )
    open_advisories = 0
    if isinstance(advisories_data, list):
        open_advisories = len([a for a in advisories_data if not a.get("withdrawn_at")])
    elif isinstance(advisories_data, dict) and "message" in advisories_data:
        # Not authorized or not available — treat as 0
        open_advisories = 0

    # ── Latest release ───────────────────────────────────────────────────────
    release_data = _api_get(f"{GITHUB_API_BASE}/repos/{repo}/releases/latest")
    latest_tag = None
    latest_released = None
    if release_data and isinstance(release_data, dict):
        latest_tag = release_data.get("tag_name", "").lstrip("v")
        published = release_data.get("published_at", "")
        if published:
            latest_released = published[:10]  # YYYY-MM-DD

    signals_date = datetime.utcnow().strftime("%Y-%m-%d")

    result = {
        "github_stars": github_stars,
        "commits_last_90d": commits_last_90d,
        "commits_prev_90d": commits_prev_90d,
        "merged_prs_per_30d": merged_last_30d,
        "avg_days_to_merge": avg_days_to_merge,
        "open_security_advisories": open_advisories,
        "open_issues": open_issues,
        "signals_date": signals_date,
    }
    if latest_tag:
        result["latest_stable_version"] = latest_tag
    if latest_released:
        result["latest_stable_released"] = latest_released

    print(f"  ✓ Stars: {github_stars:,}  |  Commits/90d: {commits_last_90d}  |  PRs/30d: {merged_last_30d}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch GitHub signals for a framework repo.")
    parser.add_argument("--repo", required=True, help="GitHub repo (e.g., langchain-ai/langgraph)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of summary")
    args = parser.parse_args()

    result = fetch_repo_signals(args.repo)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("\n  Signal Patch for YAML (signals block):")
        print("  " + "-" * 40)
        for k, v in result.items():
            print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
