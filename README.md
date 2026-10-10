# Enhanced_Humanizer

本地科研工程工作台；当前沿用暂定名，首次对外产品发布前与产品所有者复核。

最新：P3 已独立验收并同步 PR #10/main；P4 工程记忆/恢复本地独立验收通过，P5 继续本地开发。用户要求暂缓推送/PR，待恢复 Du-YouLang Git连接后交付。入口见 [本地工程记忆](docs/workbench.md)、[P4验收](docs/audits/P4-2026-10-10.md)；下文早期状态由 [项目状态](docs/project-status.md) 的最新段落取代。

开发基线为 GPT_guides/ 中的 Implementation Guide v0.4 与 PRD v0.4，保留原文。优先复用 Humanfia Humanize Flow、官方 DeepSeek Harness 与 Codex Harness。

P0/P1 已独立验收并经 PR #4/#6 与 CI 同步 main。P2 已完成 N=1/3/4/5 任务级真实候选、隔离/硬测试/独立预算，以及冻结池上的 J0、原版 LAV 概率评分、独立 Sol 结构化评分。Jev 无凭据明确阻塞。阶段 Git 交付另须本阶段 PR 实际 CI 与 main 同步；候选综合、科研质量和增强净收益仍待后续受控实验，未进入 P3。

可独立审阅：[P2 验收](docs/audits/P2-2026-10-10.md)、[P2 机器证据](docs/audits/P2-evidence-2026-10-10.json)、[任务契约](examples/p2-task-contract/README.md)、[P2 决策](docs/decisions/ADR-0008.md)、[P1 验收](docs/audits/P1-2026-10-10.md)、[项目状态](docs/project-status.md)、[完整需求追踪](docs/requirements/traceability.md)。入口见 [本地设置](docs/local-setup.md)。

项目工作区 D:\Desktop\Enhanced_Humanizer，新增环境、缓存、日志、模型状态与工作树均在项目内。WSL Linux VHD 在 D 盘项目；Microsoft 系统组件使用 C 盘为已批准例外。凭据、研究数据和 raw transcript 不上传。开发 PR 依用户授权采用轻量 CI/同步流程，产品自身每一次 PR 必须人工审核。
