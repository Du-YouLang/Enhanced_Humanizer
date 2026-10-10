"""Initialize and close the official DSH SDK runtime; never sends a prompt."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from deepseek_harness import DeepSeekHarness, DeepSeekHarnessConfig


ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / ".local-workbench/audits" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output.mkdir(parents=True, exist_ok=False)
    runtime_home = ROOT / ".local-workbench/dsh-initialize-probe"
    runtime_home.mkdir(parents=True, exist_ok=True)
    native_cache = ROOT / ".local-workbench/cache/pkg"
    native_cache.mkdir(parents=True, exist_ok=True)
    tick = time.perf_counter()
    record = {"schema_version": 1, "observed_at": datetime.now(timezone.utc).isoformat(),
              "kind": "SDK_INITIALIZE_ONLY", "model_inference_requests": 0,
              "prompt_sent": False, "api_cost_usd": 0, "model": "deepseek-flash"}
    config = DeepSeekHarnessConfig(model="deepseek-flash", cwd=str(ROOT),
                                   dsh_home=str(runtime_home), initialize_timeout_seconds=20,
                                   request_timeout_seconds=20, max_tokens=16,
                                   env={"DSH_HOME": str(runtime_home), "DEEPSEEK_API_KEY": "",
                                        "DEEPSEEK_BASE_URL": "", "XDG_CACHE_HOME": str(ROOT / ".local-workbench/cache"),
                                        "PKG_NATIVE_CACHE_PATH": str(native_cache),
                                        "TMP": str(runtime_home), "TEMP": str(runtime_home)})
    client = DeepSeekHarness(config)
    try:
        client.start()
        record["verdict"] = "PASS"
    except Exception as exc:
        record.update(verdict="INFRA_FAIL", error_type=type(exc).__name__, error=str(exc)[:2500])
    finally:
        client.close()
    record["elapsed_seconds"] = round(time.perf_counter() - tick, 6)
    path = output / "dsh-initialize.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record | {"evidence": str(path)}, ensure_ascii=False, indent=2))
    return 0 if record["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
