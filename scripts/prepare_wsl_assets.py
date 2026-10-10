"""Download the authorized WSL system/distribution assets into this project only."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def acquire(asset):
    tick = time.perf_counter()
    folder = ROOT / ".local-workbench/wsl/downloads"
    folder.mkdir(parents=True, exist_ok=True)
    name = asset["name"]
    if Path(name).name != name:
        raise ValueError("Asset name must be a filename")
    dest = folder / name
    cached = dest.exists()
    if not cached:
        partial = folder / (name + ".partial")
        if partial.exists():
            raise FileExistsError("An earlier partial download needs inspection")
        req = urllib.request.Request(asset["url"], headers={"User-Agent": "Enhanced-Humanizer-WSL-setup"})
        with urllib.request.urlopen(req, timeout=60) as response, partial.open("xb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        partial.rename(dest)
    with dest.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if digest != asset["sha256"]:
        raise ValueError("Asset digest differs from pinned official metadata")
    if asset.get("expected_bytes") and dest.stat().st_size != asset["expected_bytes"]:
        raise ValueError("Asset size differs from official release")
    return {"name": name, "path": str(dest), "sha256": digest, "bytes": dest.stat().st_size,
            "reused": cached, "elapsed_seconds": round(time.perf_counter() - tick, 6), "verdict": "PASS"}


def main():
    tick = time.perf_counter()
    approval = json.loads((ROOT / ".local-workbench/approvals/wsl.json").read_text(encoding="utf-8"))
    if approval.get("approved_by") != "human_user" or not approval.get("system_components_allowed"):
        raise PermissionError("Specific WSL installation approval is required")
    lock = json.loads((ROOT / "configs/wsl-assets.lock.json").read_text(encoding="utf-8"))
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(acquire, lock["assets"]))
    report = {"observed_at": datetime.now(timezone.utc).isoformat(), "assets": results,
              "elapsed_seconds": round(time.perf_counter() - tick, 6), "model_requests": 0}
    output = ROOT / ".local-workbench/audits/wsl-assets.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
