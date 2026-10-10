# 项目交接状态

用户最新范围：安装已批准的项目专用 WSL2；P0 全部 Gate 通过后直接进入 P1，无需再请求阶段启动授权。两份原始 v0.4 基线已完整阅读并保留，86 个稳定 ID 不变。用户确认 P1 继续使用 Enhanced_Humanizer，暂不改仓库或路径。

当前：**P0_BLOCKED_RESTART**。WSL 3.0.1.0 系统组件安装成功、虚拟机平台已启用，安装程序明确要求重启；Ubuntu 24.04.5 镜像已下载并校验，但发行版尚未注册，Linux 工具链、OS fence、真实 Humanize demo 尚未通过。没有启动 P1 模型实验。见 [本轮安装验收](audits/P0-WSL-2026-10-10.md)、[ADR-0005](decisions/ADR-0005.md)。

代码基线 main 为 `acaf82c9ede1032e27b271cb7d592edd2fd9658a`，已合并 [PR #2](https://github.com/Du-YouLang/Enhanced_Humanizer/pull/2)，本地与远程相同，主干 [CI 成功](https://github.com/Du-YouLang/Enhanced_Humanizer/actions/runs/38036529180)。当前安装成果分支 `feature/1-wsl-environment`，仍关联 [P0 Issue #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1)。初始双方历史、失败证据与 bundle 均保留；后续精确 head/PR/CI 写入本轮审计记录。

已授权：公开主仓库和正确的公开 Humanize Fork；开发仓库轻量 PR/CI、CI 成功后代理可同步 main，不启用严格 main 保护（ADR-0004）。产品自身每一次 PR 必须有真实人工审核门禁。WSL 系统组件 C 盘例外、D 盘项目 VHD 位置和存储预算已明确批准；不自动重启或删除环境。

P0 额度：DeepSeek USD 1 / 最多 4 次请求，Codex 订阅最多 2 个实验回合，每次 120 秒，不充值。已用 DeepSeek 2 次、输入 24 / 输出 8 Tokens，价格估算 USD 0.0000084–0.0000168，账单实扣 unavailable；Codex 实验 0 回合。本轮安装额外模型请求 0、API 现金 0，当前聊天订阅 Token unavailable。P0 持久预算 ledger 不重置。

P1 单独额度已获用户批准：DeepSeek USD 1 / 最多 40 次请求、Codex 订阅最多 6 个实验回合、每个模型请求 120 秒、每次实验 15 分钟、不充值。见 `configs/budget-p1.json`；尚未启用执行，必须先完成 P0 和真正的调用前预算控制器，不能把配置记录当作预算熔断已实现。

重启后继续顺序：检查 Windows boot 时间及 WSL2 可启动性 → 运行项目发行版安装脚本（固定名称/镜像哈希/目标位置，无默认 Store 安装）→ 创建 Linux 内部工具链和独立执行身份 → 验证 Landlock/seccomp/路径、凭据与 Git 拒绝边界 → 在剩余 P0 额度内完成真实 DS/Sol/Humanize demo → 提交 P0 独立验收证据 → 直接进入已授权的 P1，先复测 RLAR/Flame Chase 再选 Flow。失败时保留日志，不绕过隔离或假报成功。

USR-NAME-01：已完成本次确认；P1 沿用 Enhanced_Humanizer。下一次命名复核安排在首次对外产品发布前。
