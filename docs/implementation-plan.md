# P0→P6 实施计划

2026-10-10 更新：P2 已完成最终交付；用户已批准 P3 和独立预算，正在按 ADR-0009 实施。下文“不进入 P3 / 需新的指示”是历史状态，由此更新取代。P4–P6 未执行。

P0 已通过真实 Linux/模型门禁并经 PR #4/CI 同步 main；P1 功能已按授权完成，见 [P1 验收](audits/P1-2026-10-10.md)。用户已明确授权并完成 P2 功能独立验收；当前不进入 P3。所有新环境状态位于项目 D 盘，Microsoft 系统组件为已批准 C 盘例外。

| 阶段 | 具体实施 | 独立交付与门禁 |
|---|---|---|
| P0 | 本机/凭据/接口审计；锁定 Humanize/DSH/Codex；需求追踪、ADR、Git/CI/扫描/回滚准备；获批后 Fork、建仓、真实 smoke | 一个 P0 Issue + PR；main 保护/人工门禁、push、CI、hmz 真 demo 实际成功；缺凭据明确阻碍 |
| P1 | 核对 RLAR/Flame Chase；选择自定义 Flow；原生 DS 与 Sol 轮换真实编辑/测试/commit/交接 | 双 Builder 各至少一轮；独立上下文；暂停恢复；DS 原生 vs Humanize 墙钟实测 |
| P2 | 扩展 Flow 调用官方 DSH，在独立 worktree 执行 N=1/3/4/5 完整候选；固定测试器和 manifest；接 J0–J3 | N=3 不互读污染，真实 commits；成功/全失败/预算/限流路径；LAV/Jev 无效清楚标注 |
| P3 | 独立 Sol-Reviewer 读所有候选，自主生成 M；公平复测；Sol-Builder 再设计/测试并交还 DS | 混合成功/全失败/不可融合池均有结果；不假报 M 获胜；完整闭环可暂停恢复 |
| P4 | SQLite 索引 + append-only NDJSON + 证据工件；handoff；Issue/PR/Git refs；导出/恢复 | 从任意合法节点恢复/分叉；失败分支与研究历史不丢，原始证据可检索 |
| P5 | 优先扩展 Humanize Web 或轻量只读事件/控制前端，交互探索图与节点证据 | 用户查看全路径、diff/log/test/PR、预算时延；能注释/拒绝/审批/暂停/继续/分叉；后端授权 |
| P6 | 冻结 16 项及每实例环境，2 项 smoke 后运行 A–F、J0–J3、Merge 消融；统计图表和技术决策 | 逐任务可复现的成本/时间/完成率/干预；科研数值验收；包含负结果与不确定性 |

已完成 P0/P1：固定上游和依赖、三正确 Fork、公开仓库/Issue/PR/CI、独立 Linux 登录/隔离、真实 demo、原版 Flow 对照、双 Builder/结构化 handoff/暂停恢复、执行层预算及原生时延测量。各次失败、账本、refs 和 bundle 保留。P1-A01..A04 实测通过，开发交付还须实际 PR CI 成功。P2 已获单独指示/预算并实现真实多候选与同池 J0/J1/J3；J2 无凭据。P3 需新的阶段指示与独立预算，剩余额度不自动结转。

后续目录按指南增量形成：src/workbench 的 candidates/judging/synthesis/memory/api、ui 和 benchmarks。当前实际实现位于 .hmz/flows/basic_relay 和 scripts/p1_*，只是调用官方 Harness 的编排/控制/计费/验收层。未用空目录冒充完整产品。

需求与科学边界：Sol 不只评分；候选单位是完整工程任务；失败候选保留；Jev/LAV/Sol 算法身份分清；Reviewer 可重写；M 无保证；首轮只固定环境，保持 6+6+4；科研材料到 P6 前再索取，缺失不阻塞 P0–P5。

每阶段 PR 必须写稳定需求 ID、实际验证、代码/日志 SHA、费用与墙钟、未完项和回滚方法。`docs/acceptance-plan.md` 给出对应验收编号；`traceability.json` 可按标签/Phase/状态筛选。

P2 的任务级候选/冻结评分/受控故障证据见 audits/P2-2026-10-10.md、ADR-0008。实现位于 .hmz/flows/ds_candidates、sol_judge 和 scripts/p2_*；通用任务契约可使用已准备的本地冻结基线，科研输入默认私有。
