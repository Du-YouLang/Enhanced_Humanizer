# 数据、执行权限与尚未隔离的边界

2026-10-10 重启后状态：项目 WSL2 已安装，关闭宿主磁盘挂载/互操作；Humanize Landlock/seccomp 文件与网络能力及 11 项实际测试通过，真实 Sol demo 通过。见 [当前验收](audits/P0-Linux-2026-10-10.md) 和 ADR-0006。下文 Windows 未隔离状态是保留的历史审计。CLI 自身登录状态属于授权运行时输入，不属于“已隔离的宿主凭据”；候选私有 Git 可被自己重写，权威 main 在写入边界之外。

新文件统一位于 `D:\Desktop\Enhanced_Humanizer`。运行状态、环境、日志、worktrees、credentials（若以后配置）放 `.local-workbench/` 或 `.venv/`，由 Git 排除。已有工具、已有认证和既有 Conda 只读复用，不搬迁或改写用户历史环境。

Git 可提交：项目代码、两份原始需求基线、配置示例、精简且无私密信息的验收摘要、依赖/上游版本锁、ADR。Git 禁止提交：真实 key、auth 文件、原始日志/轨迹、数据库、虚拟磁盘、科研数据和患者信息。测试和扫描工具的报告放 ignored 路径。

凭据审计只报告存在/来源/状态。DeepSeek key 通过本机 DSH refs 在内存中读取，仅发送到已有官方 HTTPS `/models`，拒绝重定向；不显示值、不拷入配置或 PR。Jev key 只检测项目环境变量，未搜索密码库；缺失时保留明确阻碍。需要用户配置时在本地完成，不要求在聊天中发送 key。

Humanize 的 [Security 文档](https://docs.humanfia.ai/humanize/user/security)说明 agents 自动执行工具。Windows 版本虽然能初始化，尚无实测过的 OS fence；DSH driver 的 bypass rung 更需要外部隔离。Git worktree 只隔离修改位置，不能阻止读取相邻候选、共享 `.git`、GitHub token 或用户文件。

在真实 Coding Flow 前执行拒绝测试：写工作树外、读其他候选、改主干 Git refs、访问宿主凭据、危险删除/force-push、执行超限重试。必须由实际执行层拒绝；测试失败即 INFRA_FAIL，不退回只靠 Prompt 禁止。若需 WSL2/容器/受限账户等系统变更，先提供具体安装目录、预计空间、权限和回退方法，再取得用户授权。

Windows WSL 目前未安装，Docker 不在 PATH；没有自动执行系统安装。即便启用 WSL2，还须验证实际 Linux kernel Landlock、凭据/挂载目录和 sibling worktree 读隔离；不能仅凭 WSL2 名称宣称安全。所有新虚拟磁盘必须置于本项目内置 SSD 路径。

Git 本地 pre-commit：私密路径、原始基线哈希、全量稳定 ID、Gitleaks；pre-push 额外要求明确用户授权、准确仓库、获批 refs/主干 SHA、非删除且可验证 fast-forward。它们保护日常失误，可被同一用户绕过，不是对敌意 agent 的安全边界。开发 main 按用户 ADR-0004 可在轻量 PR 的真实 CI 通过后同步；产品生成的每次 PR 仍须人工审核。

2026-10-10 用户批准 P0 额外 API 推理额度最多 1 美元/DeepSeek 4 次请求，Codex 现有订阅最多 2 回合，单次最长 120 秒，不充值。批准记录不是预算执行器；Humanize 轮次间计费不能单独保证硬上限。当前开发聊天的订阅使用记 unavailable。正式运行分别记录 prompt/output/cache/reasoning tokens、来源、实际模型 ID、usage 可见性、币种/价目快照/请求 ID、工具/排队/测试/判断/融合/CI 耗时。费用估算与账单实测分别记录，不能将订阅次数折成 API 美元。
