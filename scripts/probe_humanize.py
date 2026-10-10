"""Exercise the installed Humanize engine without model calls or subprocess agents."""

import asyncio
from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import time


ROOT = Path(__file__).resolve().parents[1]
os.environ["HUMANIZE_HOME"] = str(ROOT / ".local-workbench/humanize")
os.environ["HUMANIZE_SENTRY"] = "off"
os.environ["DSH_HOME"] = str(ROOT / ".local-workbench/dsh")
os.environ["XDG_CACHE_HOME"] = str(ROOT / ".local-workbench/cache")

from hmz.flows import Budget, CostExceeded, load  # noqa: E402
from hmz.sdk import fakes  # noqa: E402


async def probe():
    start = time.perf_counter()
    flow = load("p0_probe")
    driver = fakes.FakeAgentDriver(harness="codex", reply="P0_FAKE_OK", cost=0.0)
    result = await fakes.run_fake(flow, "P0 fake turn", agents={"probe": driver}, budget=Budget(cost=0.01))
    if result.get("probe_kind") != "MOCK_ONLY" or len(driver.prompts) != 1:
        raise AssertionError("Flow did not take exactly one fake turn")
    exhausted = fakes.FakeAgentDriver(harness="dsh", cost=1.0)
    budget_verdict = "FAIL"
    try:
        await fakes.run_fake(flow, "P0 budget probe", agents={"probe": exhausted}, params={"turns": 2}, budget=Budget(cost=0.5))
    except CostExceeded:
        budget_verdict = "PASS"
    if budget_verdict != "PASS":
        raise AssertionError("Fake runtime did not enforce the declared cost budget")
    report = {"schema_version": 1, "observed_at": datetime.now(timezone.utc).isoformat(),
              "kind": "MOCK_ONLY", "hmz_version": version("hmz"),
              "dsh_sdk_version": version("deepseek-harness-sdk"), "flow_load": "PASS",
              "fake_session_and_turn": "PASS", "fake_budget_exhaustion": budget_verdict,
              "budget_scope": "before the next turn; no proof of strict per-request cash cap",
              "model_inference_requests": 0, "api_cost_usd": 0,
              "elapsed_seconds": round(time.perf_counter() - start, 6),
              "real_hmz_demo": "NOT_RUN_PENDING_AUTHORIZATION", "real_coding_agent_tools": "NOT_TESTED"}
    output = ROOT / ".local-workbench/audits" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output.mkdir(parents=True, exist_ok=False)
    path = output / "humanize-mock.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report | {"evidence": str(path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(probe())
