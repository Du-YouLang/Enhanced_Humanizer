# GitHub 仓库与交付规划

状态：具体方案已准备；远程操作待用户授权。已验证账号 `Du-YouLang`（user ID 196413727），未发现组织成员身份；同名仓库 API 返回 404。

建议目标：`Du-YouLang/Enhanced_Humanizer`，**private**，用户个人账号。保留当前暂名，命名决定见 USR-NAME-01。创建时不生成额外 README/LICENSE，以避免与本地历史分叉。

批准范围建议一次涵盖：创建该私有仓库、开启 Issues 与 Actions、推送已扫描的规范与代码、设置仓库内 main 规则、建立 P0 Issue/草稿 PR。无需更改账号全局权限，无需组织归属，无需新增协作者。现有 token 已有 repo/workflow scopes；不请求新的广泛授权。

实施顺序：

1. 重新核对 `gh auth status` / `gh api user` 的身份与同名仓库状态，避免状态变化覆盖既有工作。
2. 创建空私有仓库并核对 `visibility=PRIVATE`、owner、permissions。关联本地 origin。
3. 经此次明确批准，只首次推送最小 main 根提交 `72ad614`，作为 PR base；这不是把 P0 成果合并 main。后续 main 更新仍逐次需要人工审阅批准。
4. 创建 P0 Issue，内容用 `docs/issues/P0.md`，记录真实 URL/编号，再据真实编号规范 feature 分支名。随后推送 P0 feature，创建一个草稿 PR，正文使用 `docs/github/p0-pr-draft.md`。PR 创建成功后附加到当前 Codex 聊天。
5. CI 执行 `integrity` / `secrets`，必须实际成功并保留 workflow URL、head SHA。CI 不调用任何模型、不读取研究数据、不使用外部模型 secret。
6. 查询 GitHub 支持的主干规则，设置 PR + 必需 CI、禁止 force-push/删除、关闭 auto-merge。规则收费或权限不足时不自动升级账户；记录 API 拒绝与替代门禁差距。
7. 仅一个账号时，PR 作者不能作为独立批准者；人工查看 PR 后手动合并或在当前聊天批准明确 SHA。不会擅自添加他人来满足 review 规则，也不会自动合并。
8. 完成真实 smoke 后更新同一个 P0 PR，填写实际验收证据、开销和剩余阻碍。P0 未通过前不推进 P1。

可审阅文本准备好后，实际命令采用 `gh repo create Du-YouLang/Enhanced_Humanizer --private`、`gh issue create --body-file ...`、`gh pr create --draft --body-file ...`。执行时固定仓库参数，临时正文文件也放项目内；不通过 shell 拼接密钥或多行正文。

本地主干 / 候选规则：

- `feature/<真实Issue号>-<slug>`：一个可验收目标、一个正式 PR；现在 `feature/p0-environment-audit` 暂无远程编号。
- `run/<task>/<run_id>/ds-1..N`、`merged`、`sol`：P2/P3 才执行，独立 worktree 放项目内 `.local-workbench/worktrees/`。
- `archive/<task>/<run_id>/<attempt>` tags 保留失败成果，远程 refs 与 manifest 关联，未经明确批准不删除。
- 回滚：新建历史分支或 `git revert`；回滚结果也经 PR/CI。禁止自动 reset --hard/clean/force-push。

待批 Fork：Humanize、DeepSeek Harness、LAV 三个公开仓库。自己的私有项目与公开 Fork 权限不同，必须分别确认。详细许可证/SHA/用途见 [upstreams.md](upstreams.md)。纯只读参考不 Fork。

平台依据：[GitHub Fork 可见性](https://docs.github.com/en/pull-requests/reference/forks)规定公开仓库的 Fork 仍公开；[分支保护](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)受套餐限制；[PR 审批规则](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/approving-a-pull-request-with-required-reviews)不允许作者批准自己的 PR。实际账户与规则能力需创建后实测。

机密与研究材料：`.local-workbench/`、环境、凭据、数据、完整运行轨迹排除；每次 push 前扫描历史与变更。原始两份开发需求可随获批私有项目版本化，原始实验/患者/论文私有数据不在本次上传范围。GitHub Actions 日志和摘要也需脱敏。

限制：当前身份读取成功不代表 push 成功；公开 ls-remote 不验证写权限。账户套餐未能从当前 user API 确认，不能承诺私有仓库规则免费可用。本地 hooks 可以被绕过，不能冒充服务器端保护。
