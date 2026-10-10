# P0→P6 实施计划

本轮只推进 P0，其他阶段只列计划与验收；不得在 P0 尚未通过时实现后续产品功能。所有新目录位于当前工作区。

| 阶段 | 具体实施 | 独立交付与门禁 |
|---|---|---|
| P0 | 本机/凭据/接口审计；锁定 Humanize/DSH/Codex；需求追踪、ADR、Git/CI/扫描/回滚准备；获批后 Fork、建仓、真实 smoke | 一个 P0 Issue + PR；main 保护/人工门禁、push、CI、hmz 真 demo 实际成功；缺凭据明确阻碍 |
| P1 | 核对 RLAR/Flame Chase；选择自定义 Flow；原生 DS 与 Sol 轮换真实编辑/测试/commit/交接 | 双 Builder 各至少一轮；独立上下文；暂停恢复；DS 原生 vs Humanize 墙钟实测 |
| P2 | 扩展 Flow 调用官方 DSH，在独立 worktree 执行 N=1/3/4/5 完整候选；固定测试器和 manifest；接 J0–J3 | N=3 不互读污染，真实 commits；成功/全失败/预算/限流路径；LAV/Jev 无效清楚标注 |
| P3 | 独立 Sol-Reviewer 读所有候选，自主生成 M；公平复测；Sol-Builder 再设计/测试并交还 DS | 混合成功/全失败/不可融合池均有结果；不假报 M 获胜；完整闭环可暂停恢复 |
| P4 | SQLite 索引 + append-only NDJSON + 证据工件；handoff；Issue/PR/Git refs；导出/恢复 | 从任意合法节点恢复/分叉；失败分支与研究历史不丢，原始证据可检索 |
| P5 | 优先扩展 Humanize Web 或轻量只读事件/控制前端，交互探索图与节点证据 | 用户查看全路径、diff/log/test/PR、预算时延；能注释/拒绝/审批/暂停/继续/分叉；后端授权 |
| P6 | 冻结 16 项及每实例环境，2 项 smoke 后运行 A–F、J0–J3、Merge 消融；统计图表和技术决策 | 逐任务可复现的成本/时间/完成率/干预；科研数值验收；包含负结果与不确定性 |

P0 剩余执行顺序：

1. 已确认主仓库保持公开、三个正确 Fork 与 P0 限额；开发仓库采用 ADR-0004 的轻量 PR/CI 流程。
2. 已接入用户既有 main、Issue #1 / PR #2 / push / 无模型 CI；追加提交继续验证各自 head。
3. Fork Humanize / DSH / LAV 并在 `.local-workbench/upstreams/` 检出审核 SHA；检查完整许可证/NOTICE 与已装发布版本的映射。Codex 继续复用已有二进制，不 Fork 整套 Harness。
4. 在不调用模型的情况下测试 Humanize 实际 OS fence 与路径拒绝。Windows 不成立则形成明确的 WSL2/受限系统方案，由用户批准后实施；不绕过隔离。
5. 用户批准模型路由与预算后，做最小真实 DS/Sol/Humanize smoke；记录 actual model ID、Token/现金/订阅、超时、日志、工具结果。Jev/LAV 端点不具备时保留真实阻碍和 mock 路径。
6. CI 通过的开发基线可经 PR 同步 main；P0 的真实 demo 等 Gate 全有证据后再交用户独立验收，不把部分成果合并当作 P0 通过或 P1 启动授权。

正式目录按指南增量形成：`.hmz/flows/`、`src/workbench/{adapters,orchestration,candidates,judging,synthesis,evidence,memory,gitops,api}`、`ui/`、`benchmarks/`。本轮只建立必要 P0 文件，不提前用空实现冒充完整产品。

需求与科学边界：Sol 不只评分；候选单位是完整工程任务；失败候选保留；Jev/LAV/Sol 算法身份分清；Reviewer 可重写；M 无保证；首轮只固定环境，保持 6+6+4；科研材料到 P6 前再索取，缺失不阻塞 P0–P5。

每阶段 PR 必须写稳定需求 ID、实际验证、代码/日志 SHA、费用与墙钟、未完项和回滚方法。`docs/acceptance-plan.md` 给出对应验收编号；`traceability.json` 可按标签/Phase/状态筛选。
