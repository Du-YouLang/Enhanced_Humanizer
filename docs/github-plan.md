# GitHub 仓库与交付规划

状态更新：用户已创建 [Du-YouLang/Enhanced_Humanizer](https://github.com/Du-YouLang/Enhanced_Humanizer)，并于 2026-10-10 明确批准保持 PUBLIC、上传 P0、Issue/PR/CI。账号 `Du-YouLang`（ID 196413727）已重新验证。以下原私有建库提案已由用户决定替代。

实际目标：`Du-YouLang/Enhanced_Humanizer`，**public**，用户个人账号。保留暂名，命名决定见 USR-NAME-01。公开上传范围包括用户本轮批准的项目规范和 P0 代码，排除凭据、科研数据和原始运行轨迹。

批准范围建议一次涵盖：创建该私有仓库、开启 Issues 与 Actions、推送已扫描的规范与代码、设置仓库内 main 规则、建立 P0 Issue/草稿 PR。无需更改账号全局权限，无需组织归属，无需新增协作者。现有 token 已有 repo/workflow scopes；不请求新的广泛授权。

实施顺序：

1. 重新核对 `gh auth status` / `gh api user` 的身份与同名仓库状态，避免状态变化覆盖既有工作。
2. 已核对既有公开仓库 owner/permissions，关联 origin。用户远程 main 已有 README 初始化提交 ea7ff653569d752f70490c1ad513ac7524727ed8。
3. 保留远程 main，在 feature 分支合并本地与远程历史。取消原 72ad614 初次 main 推送提案；最新用户政策改为开发 PR 经实际 CI 成功后同步 main，见 ADR-0004。
4. 创建 P0 Issue，内容用 `docs/issues/P0.md`，记录真实 URL/编号，再据真实编号规范 feature 分支名。随后推送 P0 feature，创建一个草稿 PR，正文使用 `docs/github/p0-pr-draft.md`。PR 创建成功后附加到当前 Codex 聊天。
5. CI 执行 `integrity` / `secrets`，必须实际成功并保留 workflow URL、head SHA。CI 不调用任何模型、不读取研究数据、不使用外部模型 secret。
6. main 保护查询返回 404（未设置）。具体 JSON 提案已备，但用户要求开发 PR 不施加过多限制，因此不应用。保留提交/PR/CI 追踪，不自动升级账户。产品自身每次 PR 人工审核是独立硬要求。
7. 仅一个账号时，PR 作者不能作为独立批准者；不添加他人来满足 review 规则。开发仓库按用户授权采用轻量流程同步代码；产品执行器不能继承这份自由授权绕过逐次人工审核。
8. 已有基础成果以 P0 PR 同步，明确保留隔离/真实 demo 阻碍；后续真实 smoke 的补充成果继续关联 Issue #1。P0 未通过前不推进 P1。

可审阅文本准备好后，实际命令采用 `gh repo create Du-YouLang/Enhanced_Humanizer --private`、`gh issue create --body-file ...`、`gh pr create --draft --body-file ...`。执行时固定仓库参数，临时正文文件也放项目内；不通过 shell 拼接密钥或多行正文。

本地主干 / 候选规则：

- `feature/<真实Issue号>-<slug>`：一个可验收目标、一个正式 PR；现在 `feature/p0-environment-audit` 暂无远程编号。
- `run/<task>/<run_id>/ds-1..N`、`merged`、`sol`：P2/P3 才执行，独立 worktree 放项目内 `.local-workbench/worktrees/`。
- `archive/<task>/<run_id>/<attempt>` tags 保留失败成果，远程 refs 与 manifest 关联，未经明确批准不删除。
- 回滚：新建历史分支或 `git revert`；回滚结果也经 PR/CI。禁止自动 reset --hard/clean/force-push。

已核验 Fork：Humanize、DeepSeek Harness、LAV，均公开，详见 [upstreams.md](upstreams.md)。主项目可见性已由用户明确选择公开。纯只读参考不 Fork。

平台依据：[GitHub Fork 可见性](https://docs.github.com/en/pull-requests/reference/forks)规定公开仓库的 Fork 仍公开；[分支保护](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)受套餐限制；[PR 审批规则](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/approving-a-pull-request-with-required-reviews)不允许作者批准自己的 PR。实际账户与规则能力需创建后实测。

机密与研究材料：`.local-workbench/`、环境、凭据、数据、完整运行轨迹排除；每次 push 前扫描历史与变更。用户已批准项目保持公开并上传 P0（含两份需求基线）；原始实验/患者/论文私有数据不在上传范围。GitHub Actions 日志和摘要也需脱敏。

限制：当前身份读取成功不代表 push 成功；公开 ls-remote 不验证写权限。账户套餐未能从当前 user API 确认，不能承诺私有仓库规则免费可用。本地 hooks 可以被绕过，不能冒充服务器端保护。
