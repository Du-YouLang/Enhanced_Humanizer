"""Read-only P0 audit. No installation, inference, clone, fork or remote writes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import tomllib


ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"(?i)(?:sk-[a-z0-9_.-]{10,}|gh[pousr]_[a-z0-9_]{15,}|github_pat_[a-z0-9_]{15,}|eyJ[a-z0-9_.-]{30,})")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize(text: str) -> str:
    text = re.sub(r"(?im)^.*\bToken:.*$", "Token: [REDACTED]", text)
    return TOKEN.sub("[REDACTED]", text)


def decode(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    if b"\x00" in data:
        return data.decode("utf-16-le", errors="replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("gb18030", errors="replace")


def execute(argv: list[str], timeout: int = 30) -> dict:
    started, tick = now(), time.perf_counter()
    program = shutil.which(argv[0])
    record = {"argv": argv, "started_at": started, "program": program}
    if not program:
        return record | {"status": "NOT_INSTALLED", "exit_code": None, "elapsed_seconds": 0}
    command = [program, *argv[1:]]
    if os.name == "nt" and Path(program).suffix.lower() in {".cmd", ".bat"}:
        command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *command]
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=timeout, check=False)
        record.update(status="EXECUTED", exit_code=result.returncode,
                      stdout=sanitize(decode(result.stdout)), stderr=sanitize(decode(result.stderr)))
    except subprocess.TimeoutExpired:
        record.update(status="TIMEOUT", exit_code=None)
    except OSError as exc:
        record.update(status="INFRA_FAIL", exit_code=None, error=sanitize(str(exc)))
    record.update(ended_at=now(), elapsed_seconds=round(time.perf_counter() - tick, 6))
    return record


HARDWARE = r"""
$os = Get-CimInstance Win32_OperatingSystem
$sys = Get-CimInstance Win32_ComputerSystem
$drive = Get-Partition -DriveLetter D | Get-Disk
[ordered]@{
 os = $os.Caption; version = $os.Version; build = $os.BuildNumber
 architecture = $os.OSArchitecture; ram_gib = [math]::Round($sys.TotalPhysicalMemory / 1GB, 2)
 cpu = @((Get-CimInstance Win32_Processor).Name); logical_processors = $sys.NumberOfLogicalProcessors
 powershell = $PSVersionTable.PSVersion.ToString()
 workspace_disk = @{number=$drive.Number; model=$drive.FriendlyName; bus=$drive.BusType.ToString()}
 volumes = @(Get-Volume -DriveLetter C,D | ForEach-Object {@{drive=$_.DriveLetter; free_gib=[math]::Round($_.SizeRemaining/1GB,2); size_gib=[math]::Round($_.Size/1GB,2)}})
 disks = @(Get-PhysicalDisk | ForEach-Object {@{model=$_.FriendlyName; media=$_.MediaType.ToString(); bus=$_.BusType.ToString()}})
} | ConvertTo-Json -Depth 5 -Compress
"""


DSH_AUDIT = r"""
const fs = require('fs'), path = require('path');
const npmRoot = process.argv[2];
const yaml = require(path.join(npmRoot, '@deepseek-ai/dsh/node_modules/js-yaml'));
const home = process.env.DSH_HOME || path.join(process.env.USERPROFILE, '.dsh');
function load(name) {const p=path.join(home,name);return fs.existsSync(p)?yaml.load(fs.readFileSync(p,'utf8')):{};}
const settings=load('settings.yaml') || {}, credentials=load('.credentials.yaml') || {};
const selected=settings['agent-default-model'] || {};
const key=process.env.DEEPSEEK_API_KEY || credentials.refs?.DEEPSEEK_API_KEY;
const summary={home, settings_present:fs.existsSync(path.join(home,'settings.yaml')),
 credentials_present:fs.existsSync(path.join(home,'.credentials.yaml')),
 api_key_present:typeof key==='string' && key.length>0,
 credential_source:process.env.DEEPSEEK_API_KEY?'environment':(key?'dsh_saved_ref':'unavailable'),
 default_model:selected.model || null, default_provider:selected.provider || null,
 reasoning_effort:selected.reasoningEffort || null};
async function main() {
 if(process.argv[3]==='network' && summary.api_key_present && (!selected.provider || selected.provider==='deepseek-official') && !process.env.DEEPSEEK_BASE_URL) {
  const start=performance.now();
  try {
   const r=await fetch('https://api.deepseek.com/models',{redirect:'error',signal:AbortSignal.timeout(20000),headers:{Authorization:'Bearer '+key}});
   summary.models_probe={endpoint:'https://api.deepseek.com/models',http_status:r.status,elapsed_seconds:(performance.now()-start)/1000,inference_requests:0};
   if(r.ok){const b=await r.json();summary.models_probe.models=(b.data||[]).map(x=>({id:x.id,name:x.name,effort:x.effort,api_capabilities:x.api_capabilities}));}
  }catch(e){summary.models_probe={status:'INFRA_FAIL',error_type:e.name,elapsed_seconds:(performance.now()-start)/1000,inference_requests:0};}
 } else summary.models_probe={status:process.argv[3]==='network'?'BLOCKED_CREDENTIAL_OR_ENDPOINT':'NOT_REQUESTED',inference_requests:0};
 console.log(JSON.stringify(summary));
}
main().catch(()=>{console.log(JSON.stringify({status:'CONFIG_PARSE_FAILED'}));process.exitCode=1;});
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network", action="store_true", help="Allow read-only GitHub and official DeepSeek /models probes")
    parser.add_argument("--output", default=".local-workbench/audits")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    output.relative_to(ROOT / ".local-workbench")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = output / stamp
    output.mkdir(parents=True, exist_ok=False)
    tick = time.perf_counter()
    report = {"schema_version": 1, "started_at": now(), "timezone": "Asia/Shanghai",
              "workspace": str(ROOT), "commands": [], "network_enabled": args.network}
    commands = [
        ["git", "--version"], ["gh", "--version"], ["python", "--version"],
        ["uv", "--version"], ["uv", "python", "list", "--only-installed"],
        ["conda", "--version"], ["node", "--version"], ["npm", "--version"],
        ["codex", "--version"], ["codex", "login", "status"],
        ["dsh", "--version"], ["dsh", "--help"], ["hmz", "--version"],
        ["wsl", "--status"], ["wsl", "--list", "--verbose"], ["docker", "--version"],
        ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
        ["gitleaks", "version"], ["pwsh", "-NoProfile", "-Command", HARDWARE],
    ]
    if args.network:
        commands.extend([
            ["gh", "auth", "status"],
            ["gh", "api", "user", "--jq", "{login: .login, id: .id, type: .type}"],
            ["gh", "api", "user/orgs", "--jq", "[.[] | {login: .login}]"],
            ["gh", "api", "repos/Du-YouLang/Enhanced_Humanizer", "--jq", "{full_name: .full_name, private: .private, permissions: .permissions}"],
        ])
    local_hmz = ROOT / ".venv/Scripts/hmz.exe"
    if local_hmz.exists():
        commands.append([str(local_hmz), "--version"])
    for command in commands:
        report["commands"].append(execute(command))
    conda = execute(["conda", "info", "--json"])
    if conda.get("exit_code") == 0:
        data = json.loads(conda["stdout"])
        report["conda"] = {key: data.get(key) for key in ["conda_version", "python_version", "root_prefix", "platform", "root_writable", "is_windows_admin"]}
        report["conda"]["environment_count"] = len(data.get("envs", []))
    else:
        report["conda"] = {"status": conda["status"], "exit_code": conda["exit_code"]}
    root = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    config = root / "config.toml"
    report["codex"] = {"config_exists": config.exists(), "existing_home": str(root)}
    if config.exists():
        data = tomllib.loads(config.read_text(encoding="utf-8-sig"))
        for key in ["model", "model_reasoning_effort", "sandbox_mode", "approval_policy"]:
            if key in data:
                report["codex"][key] = data[key]
    cache = root / "models_cache.json"
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8-sig"))
        report["codex"]["cached_model_ids"] = [x.get("slug", x.get("id")) for x in data.get("models", [])]
    report["credential_environment"] = {name: bool(os.environ.get(name)) for name in [
        "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "JEV_API_KEY", "TYPESAFE_API_KEY", "GITHUB_TOKEN", "GH_TOKEN"
    ]}
    npm = execute(["npm", "root", "-g"])
    if npm.get("exit_code") == 0:
        npm_root = npm["stdout"].strip()
        package = Path(npm_root) / "@deepseek-ai/dsh/package.json"
        if package.exists():
            data = json.loads(package.read_text(encoding="utf-8"))
            report["dsh_package"] = {k: data.get(k) for k in ["name", "version", "repository", "license"]}
            dsh = execute(["node", "-e", DSH_AUDIT, "audit", npm_root, "network" if args.network else "offline"])
            if dsh.get("exit_code") == 0:
                report["dsh"] = json.loads(dsh["stdout"])
            else:
                report["dsh"] = {"status": "INFRA_FAIL", "exit_code": dsh.get("exit_code")}
    report["baseline_hashes"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((ROOT / "GPT_guides").glob("*.md"))
    }
    report.update(ended_at=now(), elapsed_seconds=round(time.perf_counter() - tick, 6),
                  model_inference_requests=0, api_cash_cost={"amount": 0, "currency": "USD", "scope": "no inference requests"},
                  current_chat_usage={"input_tokens": "unavailable", "output_tokens": "unavailable", "cash_cost": "unavailable", "billing_kind": "existing Codex subscription"})
    target = output / "environment.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence": str(target), "elapsed_seconds": report["elapsed_seconds"], "dsh": report.get("dsh"), "model_inference_requests": 0}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
