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
- 未授权自动合并 main、改账号全局权限、新增协作者或安装系统组件。

## GitHub 接入

主仓库并非空库，已有用户的 README 初始化提交 `ea7ff653569d752f70490c1ad513ac7524727ed8`。已 fetch 并在 P0 feature 分支合并两条历史，保留双方提交；README 冲突保留同名标题及本地项目介绍。远程 main 不覆盖、不 force-push，本地原 main 也保留。

Actions 已启用，Issues 已启用；main 保护 API 返回 404（尚未保护）。现阶段采用明确 SHA 的人工审批与本地 push 拒绝规则，服务器保护设置须先展示具体方案、获得权限变更授权。CI、Issue、PR 的实际结果另行回填。

## 凭据处理

用户在聊天中发送过密钥，本报告不保存其值、前缀、后缀或指纹。该密钥没有被写入命令、源码、GitHub 或新凭据文件。建议用户在 DeepSeek 控制台撤销并轮换，在本机交互式配置；无需再次在聊天发送。原有本机 DSH 凭据曾通过官方 /models 验证，可用性需每次实测；不把先前成功当作永久有效。

## 仍需验收

实际 push/PR/CI、真实 hmz demo 与模型能力/usage、Windows OS 隔离。Jev 凭据和原版 LAV 的 logprobs 仍未验证，不伪造收益，不要求现在为 P2 的 Jev 额外充值。USR-NAME-01 保留，P0 验收后、P1 开始前确认暂名。
