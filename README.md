# Enhanced_Humanizer

本地科研工程工作台；当前沿用暂定名，首次对外产品发布前与产品所有者复核。

最新：P0–P3 已独立验收并完成 Git 交付；P4 工程记忆/恢复本地独立验收通过。P5 交互工作台、后台审批门禁、真实原生暂停恢复和独立 Sol 完整接力已通过本地功能验收。推送/PR 待用户恢复 Du-YouLang Git连接，不使用其他账户。P6 未开始。

在本机运行 `.\scripts\start_workbench.ps1` 后直接打开 `http://127.0.0.1:8765`。使用与恢复说明见 [工作台](docs/workbench.md)，阶段结果见 [P4验收](docs/audits/P4-2026-10-10.md)、[P5报告](docs/audits/P5-2026-10-11.md)。

开发基线为 GPT_guides/ 中的 Implementation Guide v0.4 与 PRD v0.4，保留原文。优先复用 Humanfia Humanize Flow、官方 DeepSeek Harness 与 Codex Harness。

P2 已完成 N=1/3/4/5 任务级真实候选、隔离/硬测试/独立预算和 J0、原版 LAV 概率评分、独立 Sol 结构化评分。P3 已完成混合/全失败/拒绝池、Reviewer/M、Sol 重设计与 DS 回接。Jev 因地区访问限制不可用。合成演示验证工程功能；科研质量和增强净收益仍须后续冻结对照，不能提前声称有效。

可独立审阅：[P2 验收](docs/audits/P2-2026-10-10.md)、[P2 机器证据](docs/audits/P2-evidence-2026-10-10.json)、[任务契约](examples/p2-task-contract/README.md)、[P2 决策](docs/decisions/ADR-0008.md)、[P1 验收](docs/audits/P1-2026-10-10.md)、[项目状态](docs/project-status.md)、[完整需求追踪](docs/requirements/traceability.md)。入口见 [本地设置](docs/local-setup.md)。

项目工作区 D:\Desktop\Enhanced_Humanizer，新增环境、缓存、日志、模型状态与工作树均在项目内。WSL Linux VHD 在 D 盘项目；Microsoft 系统组件使用 C 盘为已批准例外。凭据、研究数据和 raw transcript 不上传。开发 PR 依用户授权采用轻量 CI/同步流程，产品自身每一次 PR 必须人工审核。
