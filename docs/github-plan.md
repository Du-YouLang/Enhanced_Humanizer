# GitHub 仓库与交付

当前账号 Du-YouLang（ID 196413727），公开仓库 [Enhanced_Humanizer](https://github.com/Du-YouLang/Enhanced_Humanizer)。可见性/正确 Humanize Fork 已获用户明确授权，三个 Fork 已核验。保留名称，不创建重复仓库、不改权限/协作者/可见性。新的远程修改前复查 gh 当前身份和 owner。

用户 ADR-0004 政策优先：开发 PR 在实际 CI 成功后可由代理自主合并，保持本地/GitHub main 一致，不添加严格主干保护。软件产品自身每一次 PR 仍必须真正人工审核；它不能继承本次开发自由度。Git hooks 只是防误操作，不是 OS sandbox 或服务端保护。

P0 Issue #1 已按真实 Gate 验收关闭；PR #2/#3 为准备交付，PR #4 为实际 Linux 隔离和真实 Humanize/Codex demo，均保留。P0 最终基线 main aef940446eadd6a779264de28e266ff3ba2aeb6a。P1 Issue #5 / feature/5-basic-relay，证据见 audits/P1-2026-10-10.md。

每阶段执行：

1. 在 phase feature 分支提交重要改动，保留需求 ID、真实模型/测试/预算/回滚记录。
2. 提交及推送前运行 check_repository、治理/预算回归、Gitleaks staged/history，检查没有凭据、研究数据、raw transcript、环境或 VHD 被追踪。
3. 只推送获批的 feature refs，不直接推 main、force push、删除 refs。Issue/PR 正文从项目本地 UTF-8 文件用 --body-file 传入；PR 创建后附加到当前 Codex 聊天。
4. 检查当前 PR head 的实际 integrity/secrets/Linux-budget CI，不用旧 head 或仅 queued 状态冒充通过。CI 不运行模型或读取模型 secret。
5. 实际 CI 成功且阶段功能证据完整后按用户授权合并开发 PR；fetch、fast-forward 本地 main，核对 HEAD=origin/main=GitHub main。关闭 Issue 并记录验收、费用/Token及限制。
6. 生成项目私有 bundle，保留失败实验/refs/历史。回滚用新分支+revert+PR/CI，禁止自动 reset --hard/clean/强推。

产品 PR 后端的逐次人工审批留待其功能阶段实现与独立验收。P1 的 merge 不表示 P2–P6 或完整需求通过。暂名确认见 USR-NAME-01，首次外部产品发布前复核。

P2：Issue #7 / feature/7-ds-candidates。26个仅含合成代码的真实候选/程序故障fixture保留独立 Git bundle，并推送到已授权 feature/7-evidence/<run>/<candidate> 命名空间；没有每路另开PR。实际refs及本地/main/CI一致性进入私有最终验收。用户自定义科研任务不进入该公开导出流程。
