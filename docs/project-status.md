# 项目交接状态

当前：**P0_ACCEPTED / P1_FUNCTIONAL_ACCEPTED / P2_FUNCTIONAL_ACCEPTED / P2_DELIVERY_PENDING**。P1-A01..A04 已有真实模型、独立隔离复验和预算控制证据。P1 开发交付以 Issue #5 关联 PR 的实际 CI 成功及 main 同步为准；不把 merge/CI 单独当作功能验收。阶段交付分支 feature/5-basic-relay，[PR #6](https://github.com/Du-YouLang/Enhanced_Humanizer/pull/6)。最终 CI/merge/main 一致性及 bundle 哈希记录在项目私有 `.local-workbench/audits/p1-accepted.json`；该记录不存在或非 PASS 时不得声称 Git 交付完成。用户已明确授权开始 P2，独立预算已批准；P2 功能独立验收通过，Git 交付须实际 PR/CI/main 同步；不进入 P3。

用户已授权专用 WSL2 和 P0 全 Gate 后直接 P1，并批准 P1 独立预算。项目继续使用 Enhanced_Humanizer，首次对外产品发布前复核命名。两份 v0.4 基线哈希未变，80 主需求+6操作 ID、标签/来源/附录完整保留；多阶段需求仅标记本阶段的部分实现。

P0：11 项真实 OS 测试、独立 Linux Codex 登录和 Humanize/Sol 编辑/测试/commit demo 全部通过。PR #4（实现 5c981b5）实际 CI 成功后合并，main 基线 aef940446eadd6a779264de28e266ff3ba2aeb6a；Issue #1 已关闭。见 audits/P0-Linux-2026-10-10.md。P0 ledger 保持 DS 2/4 请求、input 24/output 8；Codex 1/2 回合，input 55,512/cached 31,872/output 448；不重置。

P1：原版 RLAR、Flame Chase 实测；原生 DSH/Humanize 对照；自定义薄 Flow 完成 DS commit→实际暂停→resume 新 Sol 会话→重设计/测试/新 commit。五个仓库只读/禁网独立复验 PASS，模型调用 0；八个 Git bundle（含三个失败尝试）保留在项目私有 backups。P1 验收与 ADR-0007 记录实际边界和测量限制，不能据此宣称增强器有效。

P1 独立预算已用 **30/40 DS 请求、3/6 Codex 回合**。API 保守上界 USD 0.0770688，缓存感知估算 USD 0.009915264–0.019830528，账单 unavailable。DS 非重叠 input/cache/output=40,928/194,688/5,320；Codex input/cached/output=140,968/107,264/3,422，cached 是 input 子集。订阅 API 现金 0，订阅美元成本 unavailable。上限 USD 1 / 40请求 / 6回合 / 每请求120秒 / 每实验900秒，不充值；Windows gate→Linux broker/ledger 在调用前执行。不要重置账本或绕过入口重跑。

Linux EnhancedHumanizer-P0、/opt/workbench/.venv-linux、native Python 3.12.3，固定工具/依赖。VHD 在项目 D 盘；Windows 挂载/互操作关闭，无 sudo workbench 用户。原 portable 3.13.14 缺 pidfd 的失败环境保留。所有新增环境/缓存/会话/实验/日志留在项目；Microsoft 系统组件为已批准 C 盘例外。不得自动重启、unregister、删除 VHD 或复制全局认证目录。

GitHub Du-YouLang、公有仓库及三个正确 Fork 已确认。ADR-0004：开发 PR 实际 CI 成功后可自主合并同步 main，不加严格 main 保护；产品自身每一次 PR 必须人工审核。提交前跑 integrity、治理/预算测试与 Gitleaks。失败历史、refs、bundle 和验收记录保留。当前详细证据见 audits/P1-2026-10-10.md 和 audits/P1-evidence-2026-10-10.json。

P2：Issue #7，feature/7-ds-candidates。2026-10-10 用户批准 USD 2 / 100 DeepSeek 请求 / 6 Codex 评分回合；每请求120秒、候选600秒、实验1200秒，不充值，独立账本。ADR-0008 说明任务级候选和命名空间隔离；真实 N=1/3/4/5 共13候选通过，独立隔离/硬测试复验、失败分类/超时/通用任务契约/缓存均通过。J0/J1 原版概率/J3 Sol 已完成同池评分，J2 BLOCKED_CREDENTIAL。使用87请求/2订阅预留回合，API保守上界USD 0.2236917，缓存感知估算USD 0.037955418–0.075910836，账单unavailable。P2详细证据见 audits/P2-2026-10-10.md；最终Git交付须私有 p2-accepted.json 为PASS，26个候选/受控故障归档refs和bundle须实际验证。
