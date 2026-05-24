"""
Lightweight script to sync TrueArch framework versions from PyPI / GitHub APIs.
Updates `latest_stable_version` and `latest_stable_released` in the YAML files.
"""
import os
import glob
import yaml
import requests
from datetime import date

_DATA_DIR = os.environ.get("TRUEARCH_DATA_DIR", "data/frameworks")

def get_pypi_latest(package_name: str) -> tuple[str, str]:
    """Returns (version, release_date) from PyPI."""
    url = f"https://pypi.org/pypi/{package_name}/json"
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        data = response.json()
        version = data["info"]["version"]
        releases = data["releases"].get(version, [])
        if releases:
            upload_time = releases[0].get("upload_time_iso_8601", "")
            release_date = upload_time.split("T")[0] if upload_time else date.today().isoformat()
            return version, release_date
    return None, None

def get_github_latest(repo: str) -> tuple[str, str]:
    """Returns (version, release_date) from GitHub API."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    # Note: For higher rate limits, you should inject GITHUB_TOKEN in headers
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        data = response.json()
        version = data.get("tag_name", "").lstrip("v")
        published_at = data.get("published_at", "")
        release_date = published_at.split("T")[0] if published_at else date.today().isoformat()
        return version, release_date
    return None, None

def main():
    print("Starting TrueArch nightly version sync...")
    yaml_files = glob.glob(os.path.join(_DATA_DIR, "**/*.yaml"), recursive=True)
    yaml_files += glob.glob(os.path.join(_DATA_DIR, "**/*.yml"), recursive=True)
    
    updated_count = 0
    
    for file_path in yaml_files:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
        if not data:
            continue
            
        fw_id = data.get("id")
        lang = data.get("primary_language", "").lower()
        url = data.get("url", "")
        
        version, release_date = None, None
        
        # Determine source
        if lang == "python" and fw_id:
            version, release_date = get_pypi_latest(fw_id)
        elif "github.com" in url:
            # e.g., https://github.com/langchain-ai/langgraph
            parts = url.rstrip("/").split("/")
            if len(parts) >= 2:
                repo = f"{parts[-2]}/{parts[-1]}"
                version, release_date = get_github_latest(repo)
                
        if version and release_date:
            old_version = str(data.get("latest_stable_version", ""))
            if version != old_version:
                print(f"[{fw_id}] Updating {old_version} -> {version}")
                data["latest_stable_version"] = version
                data["latest_stable_released"] = release_date
                
                # Write back to file
                with open(file_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)
                updated_count += 1
            else:
                print(f"[{fw_id}] Already up-to-date ({version})")
        else:
            print(f"[{fw_id}] Could not fetch latest version info.")
            
    print(f"Sync complete. Updated {updated_count} frameworks.")

if __name__ == "__main__":
    main()
