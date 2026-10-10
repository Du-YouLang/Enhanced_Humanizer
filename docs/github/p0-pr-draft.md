P0 需要确认本机能否复用 Humanize、DSH 和 Codex，并建立可追踪、可回滚的开发基线。本变更保留原始 v0.4 文件，建立 86 个稳定 ID 的需求追踪、接口探针、依赖锁、治理门禁与阶段验收计划。

关联 Issue：https://github.com/Du-YouLang/Enhanced_Humanizer/issues/1 。阶段：P0。稳定 ID：WF-01、HR-01/02/03/07、JR-01/02/03、GC-01/02/04/05/06/07、SG-01/02/03、O-01–04。

验证：Windows CLI/Flow SDK 导入；官方 fake driver + 轮次间成本拒绝；DSH SDK initialize/close（无 prompt）；DeepSeek 官方 GET /models HTTP 200；六项治理回归检查；独立本地 revert/历史 worktree 演练。机密扫描与基线哈希证据见 docs/audits/P0-2026-10-10.md。

用户已批准主仓库公开、P0 上传/Issue/PR/CI、正确 Humanize Fork 和限定预算。三个正确 Fork 固定检出已通过；两个旧 Humanize Fork 保留，不作主编排层。git push、4029a52 的两轮 CI 已通过，后续 head 仍须自己的 CI。两次无工具 DeepSeek API 请求通过，合计输入 24/输出 8 Tokens，第二次返回 logprobs；估算 0.0000084–0.0000168 美元，账单实扣 unavailable，Codex 实验回合 0。PR base 为用户原 main ea7ff653569d752f70490c1ad513ac7524727ed8，保留双方历史。

实现限制：win32 上 Humanize enforceable(net=False/True) 实测均 false，当前无可用外部 fence；真实 hmz Coding demo 未运行。LAV 的 logprobs 与 Jev 凭据未验证；现有 Codex alpha 与 Humanize driver 版本差异需真实 smoke。ADR-0001/2/3 与补充核验报告记录依据与差距。草稿 PR 保持待验收。

用户最新开发政策见 ADR-0004：本开发仓库采用轻量 PR/CI，可在实际 CI 成功后同步 main，不启用过多审批限制；产品自身的每一次 PR 仍须人工审核。本 PR 交付可独立审阅的 P0 基础审计与 GitHub 基线，**P0 Gate 尚未全部通过**，Issue #1 保持开放，P1 未开始。

回滚：从保留 checkpoint 新分支，或对本阶段提交 git revert；不 reset --hard/清理历史。WSL2 未安装，用户先核对存储需求；预估与实测容量见 docs/isolation-proposal.md。
