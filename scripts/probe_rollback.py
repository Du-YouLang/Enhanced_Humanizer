"""Exercise commit/revert/history recovery in a disposable local demo repository."""

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time


ROOT = Path(__file__).resolve().parents[1]


def main():
    tick = time.perf_counter()
    output = ROOT / ".local-workbench/audits" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    repo, restored = output / "rollback-demo", output / "restored-worktree"
    repo.mkdir(parents=True, exist_ok=False)
    operations = []

    def git(*args):
        start = time.perf_counter()
        result = subprocess.run(["git", "-c", "user.name=Du-YouLang", "-c", "user.email=196413727+Du-YouLang@users.noreply.github.com", *args], cwd=repo, capture_output=True, check=True)
        operations.append({"argv": ["git", *args], "exit_code": result.returncode, "elapsed_seconds": round(time.perf_counter() - start, 6)})
        return result.stdout.decode("utf-8").strip()

    git("init", "-b", "demo")
    marker = repo / "safety_marker.txt"
    marker.write_text("baseline\n", encoding="utf-8")
    git("add", "--", marker.name)
    git("commit", "-m", "test: preserved baseline")
    baseline = git("rev-parse", "HEAD")
    marker.write_text("changed\n", encoding="utf-8")
    git("commit", "-am", "test: reversible change")
    changed = git("rev-parse", "HEAD")
    git("revert", "--no-edit", changed)
    reverted = git("rev-parse", "HEAD")
    assert marker.read_text(encoding="utf-8") == "baseline\n"
    git("worktree", "add", "-b", "recovery/from-baseline", str(restored), baseline)
    assert (restored / marker.name).read_text(encoding="utf-8") == "baseline\n"
    assert changed != baseline and reverted not in {changed, baseline}
    record = {"schema_version": 1, "kind": "LOCAL_DISPOSABLE_DEMO", "verdict": "PASS",
              "observed_at": datetime.now(timezone.utc).isoformat(), "baseline_sha": baseline,
              "changed_sha": changed, "revert_sha": reverted, "historical_worktree": str(restored),
              "history_preserved": True, "remote_recovery": "NOT_TESTED", "operations": operations,
              "elapsed_seconds": round(time.perf_counter() - tick, 6)}
    path = output / "rollback.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record | {"evidence": str(path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
