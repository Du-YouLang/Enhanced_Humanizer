# Enhanced_Humanizer

本地科研工程工作台；当前沿用暂定名，首次对外产品发布前与产品所有者复核。

开发基线为 GPT_guides/ 中的 Implementation Guide v0.4 与 PRD v0.4，保留原文。优先复用 Humanfia Humanize Flow、官方 DeepSeek Harness 与 Codex Harness。

P0 已独立验收并经 PR #4/CI 同步 main。P1 已完成真实双 Builder 编辑/测试/commit、Sol 重设计、独立会话与结构化交接、实际暂停恢复、原版 RLAR/Flame Chase 实测和 DSH/Humanize 时延对照；阶段交付须关联开发 PR 的 CI 成功。没有进入 P2，DS-Enhanced、Jev/LAV、候选综合和科研质量收益仍待后续受控实验。

可独立审阅：[P1 验收](docs/audits/P1-2026-10-10.md)、[合成代码样本](examples/p1-relay/README.md)、[Flow/预算决策](docs/decisions/ADR-0007.md)、[项目状态](docs/project-status.md)、[完整需求追踪](docs/requirements/traceability.md)。无模型复验与已获批真实运行入口见 [本地设置](docs/local-setup.md)。

项目工作区 D:\Desktop\Enhanced_Humanizer，新增环境、缓存、日志、模型状态与工作树均在项目内。WSL Linux VHD 在 D 盘项目；Microsoft 系统组件使用 C 盘为已批准例外。凭据、研究数据和 raw transcript 不上传。开发 PR 依用户授权采用轻量 CI/同步流程，产品自身每一次 PR 必须人工审核。
