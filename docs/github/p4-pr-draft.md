工程历史此前分散在阶段报告和 Linux trace 中，无法独立从统一事件库检索/恢复。本改动增加 append-only NDJSON、可重建 SQLite、私有内容寻址 artifacts、结构化 handoff 以及无损 Git fork/快照/revert/backup restore；候选代码只通过现有 Linux 隔离验证器执行。

验收：P4-A01..A04 本地 PASS，28 个真实历史节点逐一 fork，失败冻结测试复验、fresh backup restore；39 项 Python 检查（Windows 1项 Linux-only 跳过）、3项 Node 检查和 Gitleaks PASS。实际模型新增请求/现金/订阅回合均0。产品 PR 能力 gate 的测试批准仅用于测试 fixture。详见 docs/audits/P4-2026-10-10.md 和 ADR-0010。

Closes #11

用户临时断开 Git 连接，因此本说明先保存在本地；恢复正确账号后重验 CI 和远程 main 一致性，不能把本地验收等同于远程交付。P5 另行 PR，不含 P6 科研增益结论。
