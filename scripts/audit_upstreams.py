"""Record public upstream metadata and release hashes without checking out source."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
REPOS = {
    "humanfia/humanize": "fork_requested",
    "deepseek-ai/deepseek-harness": "fork_requested",
    "llm-as-a-verifier/llm-as-a-verifier": "fork_requested",
    "llm-as-a-verifier/TurboAgent": "read_only_reference",
    "danielgshea/jev-as-a-judge": "read_only_license_unresolved",
    "cathrynlavery/diagram-design": "read_only_reference",
    "openai/codex": "existing_binary_no_source_checkout",
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Enhanced-Humanizer-P0-audit"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)


def main():
    start = time.perf_counter()
    report = {"schema_version": 1, "observed_at": datetime.now(timezone.utc).isoformat(),
              "scope": "public read-only metadata; no source checkout or fork", "repositories": [], "packages": [], "ci_actions": []}
    for repo, use in REPOS.items():
        item = {"repository": repo, "url": "https://github.com/" + repo, "use": use, "installed_source": False}
        try:
            meta = get("https://api.github.com/repos/" + repo)
            head = get("https://api.github.com/repos/" + repo + "/commits/HEAD")
            item.update(default_branch=meta["default_branch"], license=(meta.get("license") or {}).get("spdx_id"),
                        archived=meta["archived"], allow_forking=meta.get("allow_forking"),
                        candidate_sha=head["sha"], committed_at=head["commit"]["committer"]["date"], status="AUDITED")
        except Exception as exc:
            item.update(status="INFRA_FAIL", error_type=type(exc).__name__)
        report["repositories"].append(item)
    for name, version in [("hmz", "0.1.0b2"), ("deepseek-harness-sdk", "0.1.5rc1"), ("deepseek-harness-runtime-bin", "0.1.5rc1")]:
        item = {"name": name, "version": version, "metadata_url": f"https://pypi.org/pypi/{name}/{version}/json"}
        try:
            data = get(item["metadata_url"])
            item.update(requires_python=data["info"].get("requires_python"), requirements=data["info"].get("requires_dist"),
                        files=[{"filename": f["filename"], "sha256": f["digests"]["sha256"]} for f in data["urls"]], status="AUDITED")
        except Exception as exc:
            item.update(status="INFRA_FAIL", error_type=type(exc).__name__)
        report["packages"].append(item)
    for repo, tag in [("actions/checkout", "v4"), ("actions/setup-python", "v5"), ("gitleaks/gitleaks-action", "v2")]:
        item = {"repository": repo, "tag": tag}
        try:
            obj = get(f"https://api.github.com/repos/{repo}/git/ref/tags/{tag}")["object"]
            while obj["type"] == "tag":
                obj = get(obj["url"])["object"]
            item.update(sha=obj["sha"], status="AUDITED")
        except Exception as exc:
            item.update(status="INFRA_FAIL", error_type=type(exc).__name__)
        report["ci_actions"].append(item)
    binary = Path(r"C:\Users\Administrator\AppData\Local\OpenAI\Codex\bin\9691020b546a15b2\codex.exe")
    if binary.exists():
        report["existing_codex_binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
    report["elapsed_seconds"] = round(time.perf_counter() - start, 6)
    dest = ROOT / ".local-workbench/audits" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest.mkdir(parents=True, exist_ok=False)
    path = dest / "upstreams.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence": str(path), "elapsed_seconds": report["elapsed_seconds"],
                      "repositories": report["repositories"], "ci_actions": report["ci_actions"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
