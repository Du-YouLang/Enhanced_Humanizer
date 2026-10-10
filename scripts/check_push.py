"""Local push gate; requires recorded user authorization. Not an OS security boundary."""

import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def validate(remote: str, updates: list[list[str]], approval: dict | None) -> list[str]:
    if not approval or approval.get("approved_by") != "human_user" or not approval.get("authorization_reference"):
        return ["GitHub repository visibility and push authorization are pending"]
    owner, repo = approval.get("owner"), approval.get("repository")
    accepted = {f"https://github.com/{owner}/{repo}", f"https://github.com/{owner}/{repo}.git", f"git@github.com:{owner}/{repo}.git"}
    if remote not in accepted:
        return ["Remote does not match the specifically authorized repository"]
    errors = []
    for local_ref, local_sha, remote_ref, remote_sha in updates:
        if set(local_sha) == {"0"}:
            errors.append("Remote ref deletion requires separate approval")
        elif remote_ref == "refs/heads/main":
            if local_sha != approval.get("main_push_approved_sha"):
                errors.append("main push requires approval of this exact commit")
        elif not any(remote_ref.startswith(prefix) for prefix in approval.get("allowed_ref_prefixes", [])):
            errors.append("Ref is outside the authorized namespace")
        if not re.fullmatch(r"[a-f0-9]{40,64}", local_sha):
            errors.append("Invalid local Git object ID")
    return errors


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("Use as a Git pre-push hook")
    approval_path = ROOT / ".local-workbench/approvals/github.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8")) if approval_path.exists() else None
    updates = [line.split() for line in sys.stdin if line.strip()]
    if any(len(row) != 4 for row in updates):
        raise SystemExit("Malformed push update")
    errors = validate(sys.argv[2], updates, approval)
    for local_ref, local_sha, remote_ref, remote_sha in updates:
        if remote_ref.startswith("refs/heads/") and set(remote_sha) != {"0"} and set(local_sha) != {"0"}:
            result = subprocess.run(["git", "merge-base", "--is-ancestor", remote_sha, local_sha], cwd=ROOT, capture_output=True)
            if result.returncode:
                errors.append("Non-fast-forward or unverified history is denied; fetch and review first")
    if errors:
        print("Push denied: " + "; ".join(errors), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
