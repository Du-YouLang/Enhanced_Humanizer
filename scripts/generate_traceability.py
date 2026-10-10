"""Generate a complete ID ledger without editing the signed-off source documents."""

import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PRD = ROOT / "GPT_guides/Research_Agent_Workbench_PRD_v0.4_2026-10-10.md"
GUIDE = ROOT / "GPT_guides/Codex_Research_Agent_Workbench_Implementation_Guide_v0.4.md"
SPECIAL = {
    "V-01": ["P6"], "V-02": ["P1", "P3"], "V-03": ["P5"], "V-04": ["P6"], "V-05": ["P0", "P1"],
    "WF-01": ["P0", "P1"], "WF-03": ["P1", "P3"], "WF-05": ["P3"], "WF-06": ["P1", "P4"], "WF-07": ["P1", "P4"],
    "DS-05": ["P2", "P6"], "DS-06": ["P2", "P6"], "DS-07": ["P2", "P3"], "DS-08": ["P2", "P3"], "DS-09": ["P1", "P6"], "DS-10": ["P6"],
    "JR-01": ["P0", "P2", "P6"], "JR-02": ["P0", "P2", "P6"], "JR-03": ["P0", "P2"],
    "JR-07": ["P3", "P6"], "JR-08": ["P2", "P3"],
    "HR-05": ["P6"], "HR-07": ["P0", "P2"], "CX-06": ["P4", "P6"],
    "GC-03": ["P2", "P4"], "GC-04": ["P0", "P4"], "OP-03": ["P1", "P6"],
    "SG-01": ["P0", "P2"], "SG-02": ["P0"], "SG-03": ["P0"], "SG-04": ["P4", "P6"], "SG-05": ["P6"],
    "O-01": ["P0"], "O-02": ["P0"], "O-03": ["P0"], "O-04": ["P0"], "O-05": ["P6"], "O-06": ["P1", "P5"],
}
DEFAULT = {"WF": ["P1"], "DS": ["P2"], "JR": ["P3"], "HR": ["P0"], "CX": ["P4"], "GC": ["P0", "P4"], "UI": ["P5"], "BM": ["P6"], "OP": ["P2", "P6"]}
TESTS = {"P0": "P0-A01..A08", "P1": "P1-A01..A04", "P2": "P2-A01..A04", "P3": "P3-A01..A04", "P4": "P4-A01..A04", "P5": "P5-A01..A03", "P6": "P6-A01..A04", "FUTURE": "后续立项"}


def restore_progress(rows, previous):
    for row in rows:
        old = previous.get(row['id'], {})
        for key in ('issue', 'tests', 'implementation_status', 'relevant_adrs', 'phase_evidence'):
            if key in old:
                row[key] = old[key]


def main():
    content = PRD.read_text(encoding="utf-8-sig")
    rows = []
    for match in re.finditer(r"^\*\*([A-Z]+-\d{2}) \[([^;]+); ([^\]]+)\]\*\* (.+)$", content, re.M):
        identifier, tag_string, sources, text = match.groups()
        tags = tag_string.split("/")
        phases = ["FUTURE"] if "F" in tags else SPECIAL.get(identifier, DEFAULT.get(identifier.split("-")[0], ["P0"]))
        status = "DEFERRED_FUTURE" if "F" in tags else ("PENDING_USER_DECISION" if "O" in tags else ("PLANNED" if "C" in tags else "PLANNED_STUDY_OR_OPTION"))
        if "P0" in phases and "C" in tags:
            status = "AUDITED_PARTIAL_NOT_ACCEPTED"
        group = identifier.split("-")[0]
        adr = "ADR-0003" if group in {"GC", "SG", "HR", "OP"} else "ADR-0002"
        rows.append({"id": identifier, "tags": tags, "sources": sources, "requirement": text,
                     "phases": phases, "issue": "https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1" if "P0" in phases else "PLANNED:" + phases[0],
                     "tests": [TESTS[p] + " (计划；不能视为已通过)" for p in phases], "implementation_status": status,
                     "relevant_adrs": ["ADR-0001", adr], "source_line": content[:match.start()].count("\n") + 1})
    for match in re.finditer(r"^- \*\*(O-\d{2})\*\* (.+)$", content, re.M):
        identifier, text = match.groups()
        phases = SPECIAL[identifier]
        status = "AUDITED_PATH_CONFIRMED" if identifier == "O-02" else "PENDING_USER_DECISION"
        rows.append({"id": identifier, "tags": ["O"], "sources": "PRD §13", "requirement": text,
                     "phases": phases, "issue": "https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1" if "P0" in phases else "PLANNED:" + phases[0],
                     "tests": [TESTS[p] + " (计划)" for p in phases], "implementation_status": status,
                     "relevant_adrs": ["ADR-0001", "ADR-0003"], "source_line": content[:match.start()].count("\n") + 1})
    destination = ROOT / "docs/requirements"
    destination.mkdir(parents=True, exist_ok=True)
    # Regeneration must not erase already recorded acceptance and user decisions.
    existing_path = destination / 'traceability.json'
    if existing_path.exists():
        previous = {r['id']: r for r in json.loads(existing_path.read_text(encoding='utf-8'))['requirements']}
        restore_progress(rows, previous)
    ledger = {"schema_version": 1, "baseline": str(PRD.relative_to(ROOT)).replace("\\", "/"),
              "baseline_sha256": hashlib.sha256(PRD.read_bytes()).hexdigest(), "requirements": rows,
              "additional_user_requirements": [{"id": "USR-NAME-01", "requirement": "项目名 Enhanced_Humanizer 暂定，后续向用户确认命名", "status": "CONFIRMED_CURRENT_NAME_2026-10-10", "checkpoint": "用户确认 P1 继续使用 Enhanced_Humanizer；首次对外产品发布前再复核"}, {"id": "USR-GIT-01", "requirement": "开发仓库轻量 PR/CI，给予代理自主权并保持本地与 GitHub 代码一致", "status": "ADOPTED_ADR-0004"}, {"id": "USR-PR-01", "requirement": "软件产品自身每一次 PR 必须经过人工审核", "status": "REQUIRED_FUTURE_IMPLEMENTATION", "checkpoint": "产品 PR 功能实现与独立验收"}]}
    (destination / "traceability.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# PRD v0.4 需求追踪", "", f"完整保留 {len(rows)} 个稳定 ID：80 项主需求和 6 项操作待决项。原始来源 S0–S4 及附录 A–C 保存在原文；[C]/[E]/[P]/[F]/[O] 不相互替代。", "",
             "机器可筛选数据见 [traceability.json](traceability.json)，phase_evidence 保存已执行证据。测试计划不能视为已通过；阶段验收不等于整个需求已经实现。", "",
             "| ID | 标签 | 来源 | Phase | Issue 草案 | Tests（计划） | 实施状态 | ADR |", "|---|---|---|---|---|---|---|---|"]
    for row in rows:
        issue = row["phases"][0]
        issue_link = "[P0 #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1)" if "P0" in row["phases"] else (f"[{issue}](../issues/{issue}.md) 待建远程" if issue != "FUTURE" else "后续立项")
        adrs = ", ".join(f"[{adr}](../decisions/{adr}.md)" for adr in row["relevant_adrs"])
        lines.append(f"| {row['id']} | {'/'.join(row['tags'])} | {row['sources']} | {'/'.join(row['phases'])} | {issue_link} | {'; '.join(TESTS[p] for p in row['phases'])} | {row['implementation_status']} | {adrs} |")
    lines.extend(["", "USR-NAME-01：已记录用户最新命名要求，见 [项目状态](../project-status.md)。此项是新增用户指示，未擅自改写 PRD 的稳定 ID。", ""])
    (destination / "traceability.md").write_text("\n".join(lines), encoding="utf-8")
    manifest = {"schema_version": 1, "sources": [{"path": str(p.relative_to(ROOT)).replace("\\", "/"), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in [GUIDE, PRD]]}
    (destination / "baselines.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"requirements": len(rows), "main_requirements": sum(not r["id"].startswith("O-") for r in rows), "operational_decisions": sum(r["id"].startswith("O-") for r in rows)}))


if __name__ == "__main__":
    main()
