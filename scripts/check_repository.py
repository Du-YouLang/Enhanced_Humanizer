"""Fail CI on private paths, changed baselines, or incomplete requirement coverage."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PARTS = {".local-workbench", ".venv", ".conda", "node_modules", "datasets", "data", "artifacts", ".dsh", ".codex"}
PRIVATE_SUFFIXES = {".vhd", ".vhdx", ".sqlite", ".sqlite3", ".db", ".pem", ".key", ".p12", ".pfx", ".jsonl", ".ndjson", ".zip", ".7z", ".iso"}


def private_path(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    lower_parts = {part.lower() for part in path.parts}
    base = path.name.lower()
    return (bool(lower_parts & PRIVATE_PARTS) or any(p.startswith(".venv-") for p in lower_parts) or path.suffix.lower() in PRIVATE_SUFFIXES
            or base == ".env" or (base.startswith(".env.") and base != ".env.example")
            or base == "auth.json" or "credentials" in base)


def baseline_errors() -> list[str]:
    errors = []
    manifest = json.loads((ROOT / "docs/requirements/baselines.json").read_text(encoding="utf-8"))
    expected = {
        "GPT_guides/Codex_Research_Agent_Workbench_Implementation_Guide_v0.4.md": "d2eac13daefdfE0cf4ba211e3d57b3003e2383f4c1bea55b5f155bc372a0c206".lower(),
        "GPT_guides/Research_Agent_Workbench_PRD_v0.4_2026-10-10.md": "5e404e6fd44e68d3b96489eb61ce6f2fede2309d4e58f6b36636cf3c54f11edf",
    }
    if {s["path"]: s["sha256"] for s in manifest["sources"]} != expected:
        errors.append("Baseline manifest differs from the original supplied files")
    for name, digest in expected.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            errors.append("Original baseline changed: " + name)
    return errors


def traceability_errors() -> list[str]:
    prd = (ROOT / "GPT_guides/Research_Agent_Workbench_PRD_v0.4_2026-10-10.md").read_text(encoding="utf-8-sig")
    ids = set(re.findall(r"\*\*([A-Z]+-\d{2})(?: \[|\*\*)", prd))
    ledger = json.loads((ROOT / "docs/requirements/traceability.json").read_text(encoding="utf-8"))
    rows = ledger["requirements"]
    found = {r["id"] for r in rows}
    errors = []
    if ids != found or len(rows) != len(found):
        errors.append(f"Requirement ID coverage mismatch: missing={sorted(ids-found)}, extra={sorted(found-ids)}")
    for row in rows:
        if not all(row.get(k) for k in ["tags", "sources", "phases", "issue", "tests", "implementation_status", "relevant_adrs"]):
            errors.append("Incomplete traceability: " + row["id"])
        if "F" in row["tags"] and row["implementation_status"] != "DEFERRED_FUTURE":
            errors.append("Future requirement incorrectly promoted: " + row["id"])
    originals = {m.group(1): (m.group(2).split("/"), m.group(3), m.group(4)) for m in re.finditer(r"^\*\*([A-Z]+-\d{2}) \[([^;]+); ([^\]]+)\]\*\* (.+)$", prd, re.M)}
    for row in rows:
        if row["id"] in originals and (row["tags"], row["sources"], row["requirement"]) != originals[row["id"]]:
            errors.append("Requirement tags/source/text changed: " + row["id"])
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true")
    args = parser.parse_args()
    command = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"] if args.staged else ["git", "ls-files", "-z"]
    names = subprocess.check_output(command, cwd=ROOT).decode("utf-8").split("\0")
    errors = ["Private file must not be tracked: " + n for n in names if n and private_path(n)]
    errors.extend(baseline_errors())
    errors.extend(traceability_errors())
    if errors:
        print(json.dumps({"verdict": "FAIL", "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"verdict": "PASS", "scope": "staged" if args.staged else "tracked", "checked_files": sum(bool(n) for n in names), "stable_ids": 86}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
