# 项目交接状态

用户最新范围：专用 WSL2 安装、P0 全部 Gate 通过后直接进入 P1；无需重新申请阶段启动。P1 沿用 Enhanced_Humanizer，首次对外产品发布前复核命名。两份 v0.4 基线已完整阅读且未修改，86 个稳定 ID 保留。

当前：**P0_ENVIRONMENT_PASSED_DELIVERY_CI_PENDING**。用户已重启并完成独立 Linux Codex ChatGPT 登录。Ubuntu 24.04.5 注册在项目 D 盘 VHD，Landlock ABI 7，文件/网络 fence 实测可用；11 项 OS 许可/拒绝测试全部通过。真实 Humanize 自定义 Flow + gpt-6.1-sol 完成编辑、测试和 commit，独立验收 PASS，31.692826 秒。见 [P0 Linux 验收](audits/P0-Linux-2026-10-10.md)、[ADR-0006](decisions/ADR-0006.md)。前次 BLOCKED_RESTART 是历史状态。

交付分支 feature/1-linux-isolation，基于已合并 [PR #3](https://github.com/Du-YouLang/Enhanced_Humanizer/pull/3) 的 main `7dde7e45e0cdf863439e3c7dfa60167756460e78`，关联 [P0 Issue #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1)。本次成果必须经过真实 CI/PR 再同步 main；安装、CI、合并各自都不能单独替代阶段验收。

Linux 使用 `/opt/workbench/.venv-linux`、Ubuntu native Python 3.12.3；初始 portable 3.13.14 缺 pidfd，保留失败环境。发行版 EnhancedHumanizer-P0，Windows 挂载/互操作关闭，无 sudo workbench 用户。所有新增环境/缓存/会话/实验/日志位于 D 盘项目 VHD；Microsoft 系统组件为已批准 C 盘例外。不得删除 VHD、unregister、复制全局认证目录或自动重启。

P0 已用：DeepSeek 2/4 请求、input 24 / output 8，估算 USD 0.0000084–0.0000168，账单 unavailable；Codex 1/2 实验回合，input 55,512 / cached 31,872 / output 448。订阅成本 unavailable，不折算 API 美元；本次 Codex demo API 现金 0。持久 ledger 不重置。

P1 独立授权：DeepSeek API USD 1 / 最多 40 请求，Codex 订阅最多 6 实验回合；每请求 120 秒、每实验 15 分钟，不充值。目前尚未动用，预算配置不是熔断证明。先交付 P0 当前 CI/PR，随后直接做原版 RLAR/Flame Chase 实测和 ADR、双 Builder 真实编码接力、独立会话/结构化 handoff、暂停恢复、请求前预算控制及同任务 DSH/Humanize 时延对照；不提前做 P2。

GitHub 身份 Du-YouLang、公开仓库和正确 Humanize Fork 已批准。遵守 ADR-0004：轻量开发 PR 的真实 CI 通过后可自主同步 main，不加严格主干保护；产品自身每一次 PR 必须真实人工审核。重要提交、失败证据、refs、bundle 和验收记录保留。
