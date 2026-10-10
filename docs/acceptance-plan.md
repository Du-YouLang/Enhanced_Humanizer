# 按阶段独立验收计划

以下是测试设计，除 P0 报告中明确附实测证据者外，均未执行。对应稳定 ID 可从 requirements/traceability.json 筛选。

| 验收 ID | 验收内容 | P0 当前证据 / 未来要求 |
|---|---|---|
| P0-A01 | 完整读基线，硬件/SSD/路径/工具/环境审计，原始哈希不变 | 本地环境报告、两份 SHA256、无研究数据外传 |
| P0-A02 | 用户确认 GitHub 身份/可见性/归属；创建私有仓库、Issue/PR、push、CI、main 规则 | 真实 GitHub URL、head SHA、CI logs；不可用保护明确替代门禁 |
| P0-A03 | 固定版本可重装、CLI/SDK 探针、上游许可证/commit | 32 项哈希 lock、版本与导入、DSH initialize；源码 Fork 待批准 |
| P0-A04 | 本地自定义 Humanize Flow 可加载；官方 fake 测预算；真实 hmz demo 成功 | mock 与真实结果分开，真实 Coding demo 仍待隔离与预算 |
| P0-A05 | DS/Sol 的真实模型访问、工具/日志/恢复/Token 能力，Jev/LAV 能力界限 | /models 与登录不能代替真正 turn；缺 Jev key、缺 logprobs 明确 BLOCKED |
| P0-A06 | ignore/路径拒绝/机密扫描；OS 层拒绝越界、读取别的候选、危险操作 | 本地治理单测 + Gitleaks；Windows 自主 agent 的外部隔离待验证 |
| P0-A07 | 用户确认初始成本和时间上限；真实 usage 可见性、超限停止记录 | 初始推理额度 0、提案未授权；不可见填 unavailable |
| P0-A08 | checkpoint/revert/历史 worktree 与远程 refs 恢复演练 | 独立本地 demo 与项目远程恢复分开，保留正负结果 |
| P1-A01 | 原生 RLAR / Flame Chase 接口、角色、可用性/资源实测并写 ADR | 不强制两个模式都进入 UI |
| P1-A02 | DS 与 Sol 各真实改代码、运行测试、commit，且交接 session 独立 | Sol 必须能替代设计；交接包含事实与失败证据 |
| P1-A03 | 暂停/恢复、轮次/费用/时长限制、明确停止状态 | 外部执行层的限制失败即基础设施失败 |
| P1-A04 | 同任务 DS 原生 DSH 与 Humanize 墙钟、工具/排队/限流与响应对比 | 可用时加入现有 CC/Codex DS 参照，记录环境开销 |
| P2-A01 | N=1/3/4/5，任务级完整候选，同 base/env，独立 worktree/Session/读写 | N=3 实测互不读取/污染；每个真实 commit |
| P2-A02 | 硬验收、候选 manifest、缓存/重试/独立预算/超时 | 首补丁/首通过/结束、input/output/cache Tokens 全记录 |
| P2-A03 | J0/J1/J2/J3 接口与冻结证据；logprobs 与 Jev 真实能力 | 缺 Jev/LAV 端点不伪造结果，其余主线可工作 |
| P2-A04 | 部分失败、全部失败、基础设施失败的分类与诊断 | 保留失败者，不能将最佳失败者报告为成功 |
| P3-A01 | 成功/失败候选池均进入独立 Reviewer，生成真实候选 M | 可彻底重写，不强制 cherry-pick；M 只写隔离 worktree |
| P3-A02 | M 与 A..N 使用同一冻结环境/独立测试器复测 | 额外成本/时间计入，不默认 M 获胜 |
| P3-A03 | 全失败/不可融合池诊断，拒绝假成功，暂停/重启可恢复 | 保持 FAIL/INDETERMINATE，所有分支可恢复 |
| P3-A04 | Sol-Builder 接管候选或 M、真重构/测试，随后 DS 可继续 | Builder/Verifier/Reviewer 会话与预算分立 |
| P4-A01 | SQLite + append-only NDJSON + artifacts + Git 的关联和导出 | 模型/Harness/配置/证据/人工指令完整可追溯 |
| P4-A02 | 结构化 handoff 与 fact/hypothesis/rejected 等状态，原始日志可展开 | 摘要不覆盖事实；正确检索失败历史 |
| P4-A03 | 从任意合法 checkpoint 新 worktree，revert 并保留失败 refs | 主干无损，远程 refs 不被 GC/自动清理丢失 |
| P4-A04 | 项目备份/恢复/重建，隐私排除与 GitHub Issue/PR 对应 | 不依赖 Codex 私有聊天 Memory |
| P5-A01 | 探索图完整重建候选→Judge→M→Sol→PR 的真实路径 | 节点关联 commit/diff/log/test/证据，成功失败均展示 |
| P5-A02 | 人工注释、拒绝、审批、暂停/恢复、从历史节点分叉 | 权限必须后端执行，UI 不是唯一门禁 |
| P5-A03 | N/预算/墙钟与阶段延时/执行状态可见，基本易用 | 先可用，再按实际使用迭代，不强制 Electron |
| P6-A01 | 冻结 6 BugsInPy + 6 SWE-Lite + 4 科研任务、材料/环境/seed/隐藏测试 | 先 smoke 2 项；材料缺失科研 NOT_RUN/INDETERMINATE |
| P6-A02 | A–F、同池 J0–J3、Best-of-N vs +M，DS 原生 Harness 速度参照 | 不增加 Aider/Agentless 等为必跑臂，不泄漏隐藏答案 |
| P6-A03 | 逐任务完成率、每成功任务总成本、端到端耗时、人工干预 | 时延分解、Token/缓存、等成本/等时长、失败类别完整 |
| P6-A04 | 科研金标准/容差/不变量、GPU精度/性能与报告可复现 | 16 项仅探索性小样本，负结果不删，评分不是科研真值 |
