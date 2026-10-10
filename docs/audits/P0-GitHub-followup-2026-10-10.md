# P0 GitHub 与凭据补充核验

2026-10-10，延续 P0，本报告不替代首次审计快照。未进入 P1。

## Fork 来源核验

通过 GitHub REST 的 parent/source、repository ID 和固定 commit 查询核验，随后从用户 Fork 检出；不按仓库名字猜测来源。

| 用户仓库 | 实际上游 | 结论 |
|---|---|---|
| [deepseek-harness](https://github.com/Du-YouLang/deepseek-harness) | deepseek-ai/deepseek-harness | 正确，用户创建；固定 d743267388641bc76f17c45ce8b4c231aed1d32c |
| [llm-as-a-verifier-ds4p1](https://github.com/Du-YouLang/llm-as-a-verifier-ds4p1) | llm-as-a-verifier/llm-as-a-verifier | 正确，改名不影响 Fork 血缘；固定 90e8fc215606447d6d31e9e24bff7200fb0c0994 |
| [oh-my-humanize](https://github.com/Du-YouLang/oh-my-humanize) | humanfia/oh-my-humanize，ID 1274630894 | 旧终端 Agent，上游已归档并指向 humanfia/humanize；不是本项目主编排层 |
| [humanize-plugin](https://github.com/Du-YouLang/humanize-plugin) | humanfia/humanize-plugin，ID 1291641367 | 旧 MCP 插件，上游已归档并指向 humanfia/humanize；不是本项目主编排层 |
| [humanize](https://github.com/Du-YouLang/humanize) | humanfia/humanize，ID 1310474846 | 经本轮明确授权补建；Fork ID 1412913283；固定 0488ca796c44e16b0b30468e673f541d358b07a9 |

旧项目官方说明：[oh-my-humanize README](https://github.com/humanfia/oh-my-humanize)、[humanize-plugin README](https://github.com/humanfia/humanize-plugin)。两个旧 Fork 均保留，未安装、未删除。正确的三个源码 checkout 位于 ignored 的 `.local-workbench/upstreams/`；origin 指向用户 Fork，upstream 指向原作者仓库，detached HEAD。下载及检出墙钟：Humanize 6.190 秒、DSH 37.617 秒、LAV 21.449 秒；三者并行，不能把总和报告为端到端耗时。

## 本轮明确授权

- 用户亲自建立 `Du-YouLang/Enhanced_Humanizer`，repository ID 1412901750，并回复“保持公开并推进 P0”。允许上传审计后的 P0 文件、Issue/PR/CI；研究数据和凭据仍排除。
- 用户回复“授权补建正确的公开 Fork”。已创建 `Du-YouLang/humanize`，parent/source 均为 humanfia/humanize。
- 用户批准 P0 API 现金最多 1 美元、DeepSeek 最多 4 次请求、Codex 现有订阅最多 2 回合、单次最长 120 秒、不充值。批准不等于已实现硬预算控制或已花费；真实调用必须预留最坏上界并记录 usage。
- 随后用户调整开发协作政策：给予开发仓库自主权，保持本地/GitHub 一致，不给开发 PR 施加过多限制；软件自身每一次 PR 仍须人工审核。按 ADR-0004 实施轻量开发 PR/CI，不启用提案的严格 main 规则。系统安装、账号全局权限或新增协作者未获批。

## GitHub 接入

主仓库并非空库，已有用户的 README 初始化提交 `ea7ff653569d752f70490c1ad513ac7524727ed8`。已 fetch 并在 P0 feature 分支合并两条历史，保留双方提交；README 冲突保留同名标题及本地项目介绍。远程 main 不覆盖、不 force-push，本地原 main 也保留。

Actions 已启用，Issues 已启用；main 保护 API 返回 404（尚未保护）。用户最新要求轻量开发流程，保留 CI/PR/提交追踪，不应用服务器保护提案；软件产品的每次 PR 人工审核另行严格实现。

已建立 [Issue #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1)、[PR #2](https://github.com/Du-YouLang/Enhanced_Humanizer/pull/2)。4029a525e05eabd7dfc5adb33c1bc476ea4c8c73 的 push 与 pull_request 两轮 CI 均成功：[PR CI](https://github.com/Du-YouLang/Enhanced_Humanizer/actions/runs/38035720487)，07:49:02Z 至 07:50:05Z，63 秒端到端（含排队）；integrity 60 秒、secrets 5 秒。后续 head 必须有各自检查结果，不能沿用旧 CI。

## 凭据处理

用户在聊天中发送过密钥，本报告不保存其值、前缀、后缀或指纹。该密钥没有被写入命令、源码、GitHub 或新凭据文件。建议用户在 DeepSeek 控制台撤销并轮换，在本机交互式配置；无需再次在聊天发送。原有本机 DSH 凭据曾通过官方 /models 验证，可用性需每次实测；不把先前成功当作永久有效。

## 仍需验收

真实 hmz demo、Sol 新 turn 与 Windows OS 隔离。原版 LAV 最小流程和 Jev 凭据仍未验证，不伪造收益，不要求现在为 P2 的 Jev 额外充值。USR-NAME-01 保留，P0 验收后、P1 开始前确认暂名。

## 已执行的付费 API 探针

在获批预算内，复用已有本机 DSH 凭据，仅调用官方 HTTPS，未保存/传递聊天所贴的新密钥。无工具权限、不重试、不跟随重定向，output max_tokens=64，thinking disabled。

| 请求 | 结果 | 输入/输出 Tokens | 缓存命中/未中 | 墙钟 |
|---|---|---|---|---|
| 普通文本 | HTTP 200，返回 deepseek-flash，固定回答匹配 | 12 / 4 | 0 / 12 | 1.0839294 秒 |
| logprobs=true, top_logprobs=2 | HTTP 200，固定回答匹配，真实返回 4 个 token 的 logprobs | 12 / 4 | 0 / 12 | 1.2755676 秒 |

合计输入 24、输出 8、总计 32 Tokens；API 两次请求墙钟合计 2.359497 秒，**不是开发交互总耗时**。依据 [2026-10-10 官方美元价目](https://api-docs.deepseek.com/quick_start/pricing/)，两次估算共 0.0000084–0.0000168 美元（空闲/峰值）；实际账户币种、赠额抵扣和账单实扣 unavailable，不报告为实扣。两次 request ID 未保留，明确 unavailable；脚本已改进为后续保留响应 ID，不为补 ID 额外调用。

普通 API token logprobs 成功，不等于原版 LAV score-token/PPT/compare/select/track 已复现；不将 Sol 评分冒充概率算法。DeepSeek 原生 Harness/Coding 工具未在这两次请求使用。

调用前保守预留每请求整个 1M context 的峰值输入价及封顶输出 0.3146496 美元，共预留 0.6292992 美元；失败也不释放预留。持久 ledger 保留请求数 2/4，Codex 额外实验回合 0/2。该固定探针的三项纯策略测试通过：未授权/坏账本拒绝、费用先耗尽拒绝、次数耗尽且不改账本。它不是通用 Coding Agent 的预算控制器。

## Windows 隔离与存储结论

实际 DshAgent 的受限 Fence 配置抛 `Unfenced`，0.027839 秒，0 模型请求；Windows 的 filesystem/network enforceable 均 false，判为 BLOCKED_OS_ISOLATION。不是因为 API key 不可用，也不回退为 Prompt 限制。

用户要求 WSL2 安装先等存储说明：当前没有安装/修改系统功能。现有 `.venv` 约 276 MiB，连缓存/源码/工具等逻辑长度合计约 1.39 GiB；D 盘约 131.08 GiB 空闲。拟 P0 WSL2 新增 5–10 GiB，预留 15–20 GiB 余量，属估算非实测；细节见 [隔离方案](../isolation-proposal.md)。开发聊天/完整交互墙钟及订阅 Token 无可核验计量，记 unavailable。
