# Enhanced_Humanizer

本地科研工程工作台；项目名暂定，正式发布前需与产品所有者再次确认。

开发基线为 `GPT_guides/` 中的 Implementation Guide v0.4 与 PRD v0.4，保留原文。
当前完成 P0 剩余门禁，用户已授权通过后直接进入 P1。主仓库公开、正确 Humanize Fork 和模型测试上限均已确认；开发仓库采用轻量 PR/CI 同步流程，产品自身每次 PR 仍须人工审核。

优先复用 Humanfia Humanize Flow、DeepSeek Harness 与 Codex Harness。DS-Enhanced、Jev、候选综合与双 Builder 的收益均待受控实验检验。

项目工作区：`D:\Desktop\Enhanced_Humanizer`。新增环境、缓存、日志与工作树均放在此目录；现有全局工具仅复用，微软 WSL 系统组件使用 C 盘为已批准例外。

当前状态：P0 本地/GitHub 基线、三 Fork 和两次 API 探针已完成；WSL 3.0.1 系统组件安装成功，Windows 要求手动重启，Ubuntu 24.04.5 镜像已校验待安装。Linux 隔离与真实 Humanize demo 未通过，P0 尚未完成，P1 未开始。见 [安装验收记录](docs/audits/P0-WSL-2026-10-10.md)。

可审阅交付：[P0 报告](docs/audits/P0-2026-10-10.md)、[实施计划](docs/implementation-plan.md)、[GitHub 规划](docs/github-plan.md)、[能力矩阵](docs/capability-matrix.md)、[需求追踪](docs/requirements/traceability.md)。

无模型调用的复现方法见 [本地安装与探针](docs/local-setup.md)。阶段交接与命名提醒见 [项目状态](docs/project-status.md)。
