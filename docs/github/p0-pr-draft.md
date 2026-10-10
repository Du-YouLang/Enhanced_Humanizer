P0 需要确认本机能否复用 Humanize、DSH 和 Codex，并建立可追踪、可回滚的开发基线。本变更保留原始 v0.4 文件，建立 86 个稳定 ID 的需求追踪、接口探针、依赖锁、治理门禁与阶段验收计划。

关联 Issue：待真实创建后填写。阶段：P0。稳定 ID：WF-01、HR-01/02/03/07、JR-01/02/03、GC-01/02/04/05/06/07、SG-01/02/03、O-01–04。

验证：Windows CLI/Flow SDK 导入；官方 fake driver + 轮次间成本拒绝；DSH SDK initialize/close（无 prompt）；DeepSeek 官方 GET /models HTTP 200；六项治理回归检查；独立本地 revert/历史 worktree 演练。机密扫描与基线哈希证据见 docs/audits/P0-2026-10-10.md。

这些结果不表示真实 Coding Agent 或 P0 全部门禁已经通过。创建 PR 前应回填 GitHub push/CI/保护规则、获批 Fork、真实模型 smoke/隔离结果、base/head SHA 和实际开销；未完成项保持明确状态。当前没有额外推理调用，API 推理现金 0；本聊天 Token/订阅成本 unavailable。

实现限制：Windows OS fence 尚未通过；LAV 的 logprobs 与 Jev 凭据未验证；现有 Codex alpha 与 Humanize driver 版本差异需真实 smoke。ADR-0001/2/3 记录依据与差距。

回滚：从保留 checkpoint 新分支，或对本阶段提交 git revert；不 reset --hard/清理历史。不自动合并 main。当前 P0 未验收，P1 未开始。
