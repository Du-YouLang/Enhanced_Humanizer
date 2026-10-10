# 项目交接状态

用户最新范围：仅 P0。原始 v0.4 指导书与 PRD 已完整阅读并保留。项目暂名 Enhanced_Humanizer，实际工作区 `D:\Desktop\Enhanced_Humanizer`；不再要求用户重复确认已指定的路径。

状态：P0 本地审计已完成，远程接入进行中，真实 Humanize demo/隔离验收尚未通过。详见 [首次审计](audits/P0-2026-10-10.md)、[本轮核验](audits/P0-GitHub-followup-2026-10-10.md)、[GitHub 规划](github-plan.md)。P1 尚未开始。

本地 main 初始根提交：`72ad614`，保留。远程 main 为用户创建的 `ea7ff653569d752f70490c1ad513ac7524727ed8`；两条历史已在阶段分支合并，未覆盖 main。当前阶段分支 `feature/1-p0-environment-audit`，对应 [P0 Issue #1](https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1)。

2026-10-10 用户已明确批准：主仓库 PUBLIC；P0 上传/Issue/PR/CI；补建 humanfia/humanize 公开 Fork；DeepSeek 最多 1 美元/4 次请求、Codex 订阅最多 2 回合、单次 120 秒、不充值。准确 repo/feature refs 授权记录在 ignored `.local-workbench/approvals/github.json`，仍拒绝直接 main 推送。三个正确 Fork 已固定 commit 检出；旧 Fork 保留。最新开发政策见 ADR-0004：允许 CI 通过的开发 PR 同步 main，不启用过多审批限制；软件产品每一次 PR 仍须人工审核。系统安装未授权，用户先询问空间，WSL2 未安装。

已完成 [PR #2](https://github.com/Du-YouLang/Enhanced_Humanizer/pull/2)、git push、4029a52 的两轮 CI，以及两次无工具 DeepSeek API smoke（总输入 24/输出 8 Tokens，第二次真实返回 logprobs，估算 0.0000084–0.0000168 美元，账单实扣 unavailable）。Codex 实验回合 0。追加 head 需自己的 CI 后才同步 main，不能宣布 P0 通过。Humanize 受限 DshAgent 在 win32 实测抛 Unfenced；真实 hmz demo 仍 BLOCKED_OS_ISOLATION，见隔离方案。不得进入 P1、多候选或 UI 开发。

USR-NAME-01：P0 结束后、P1 启动前与用户确认是否继续使用 Enhanced_Humanizer，或选更贴近科研双 Builder 工作台的名称。当前不擅自改名；不以对话记忆替代这条持久记录。
