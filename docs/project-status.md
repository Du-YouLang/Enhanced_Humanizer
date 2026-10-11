# 项目交接状态

2026-10-11 最新授权：P6 两项公共 smoke 独立预算已批准：USD5、200 DS 请求、32 Codex 订阅回合；120秒/请求、600秒/候选或角色、1200秒/实验，不充值/不结转。先验证两项冻结 smoke，再按实际耗用估算公共主集；主集模型矩阵不属于本次 smoke 预算。科研材料由用户暂缓，四项原定任务仍保留。P7 范围明确为安装打包和交付准备，对外发布前再次确认。GitHub 继续暂缓，所有交付先留本地分支、提交和备份。见 ADR-0013 和 configs/budget-p6-smoke-approved.json；以下等待授权文字是历史状态。

2026-10-11 最新：用户授权继续P6，并提到P7；原指导书只定义P0–P6，P7范围待确认。P6在feature/p6-frozen-benchmark进行本地准备：12公共实例身份/材料hash+4缺料科研槽位、A–F96计划单元已冻结v2，Black/Python3.8.3正负对照与实际隔离、依赖封条通过。真实模型基准尚未运行，P6预算提案等待答复，不能结转P5。第二项Requests环境/原生执行适配、主集/消融/科学材料仍待完成；详见audits/P6-preparation-2026-10-11.md和ADR-0012。P7不视为已定义或验收。GitHub仍按用户指示暂缓，main/P4/P5 refs不变。以下旧“P6未开始/未授权”为历史记录，由本段取代。

2026-10-11 当前：P0–P3已功能与远程交付验收，main仍为8d9b11de9ccbe13f12fb8a9b32a89fb19991404b。P4本地功能PASS，独立阶段提交8de702adf9d13d343fada7b85b317c938bf8401f、Issue #11此前已创建；远程P4交付暂缓。P5分支feature/p5-exploration-workbench的P5-A01..A03本地原型功能PASS；54 Windows（1 Linux skip）、47 native Linux、Node3、原生Flow/独立会话/硬测试/备份已验证。P6未开始。

真实完成run p5-20261010170912-de864bc2，复用原N3池、新候选生成0；Reviewer后真暂停/新worktree/恢复→M硬测试→独立J3比较→Sol Builder→最终J3完成。M 3a828fcf1e91dc987faab993564cf733d2aa20f1，Builder 57fa264299c45719fffc670e3cdfb5fe53ed3ac0；五个角色session独立。活动150.649352399秒、Windows控制172.8471566秒。5个隐藏复验、M的5项及Builder的12项可见测试PASS；不据此宣称科学质量或增强收益。

用户最新要求：暂时断开Du-YouLang Git连接，本地代码/提交继续，PR等恢复后处理；不得推送、建/改远程Issue/PR、运行远程CI或使用其他账户。恢复后先核对身份，按P4→P5依次交付并实际跑CI。产品生成的每一次PR仍需新的真实人工审批；本地提案AWAITING_HUMAN_REVIEW，不是用户批准。

P5预算按用户“按需”授权采用有限门禁$5/160 DS请求/16 Codex预留回合；请求120秒、候选/角色600秒、累计活动1200秒、单候选12请求/$0.5，不充值/不结转。已用30 DS/12 Codex，API上界$0.1014468、账单/订阅美元成本unavailable；14原生session有10项可见usage、4未知，不能视为0。账本文件SHA16c4f6960bce0838b61f003f58a56bd66131c0e26b1daab9e6b7c5bb88114b49，canonical SHA另见机器证据；P0–P3账本不变。

原订阅限额及恢复后的协议失败均保留：自动Harness重试会话匹配、公开评分池hash、可见测试elapsed导致hash变化、Reviewer附带M名单误拒绝已分别修复并有回归/实际重试。源码变动后明确新run，不篡改旧冻结检查点。无需继续探测额度或重复付费调用，不自动恢复/上传/改模型。

入口 .\scripts\start_workbench.ps1 → http://127.0.0.1:8765，仅Windows loopback。当前P5源码/账本/备份及干净工作区在私有 .local-workbench/audits/p5-delivery-local.json；公开结果见audits/P5-2026-10-11.md。产品远程发布硬禁用，目标/基线祖先/隐私/CI预检仍待恢复连接后处理。下文为历次记录，由以上当前状态取代。

2026-10-10 最新用户授权：执行 P4→P5，本轮预算按需但保留有限执行门禁。P3 私有 p3-accepted.json 已 PASS，main 8d9b11de9ccbe13f12fb8a9b32a89fb19991404b。P4 本地 P4-A01..A04 独立 PASS（28历史节点逐一分叉、失败复验、备份新目录恢复）；见 audits/P4-2026-10-10.md。用户随后断开 Du-YouLang Git连接，允许继续本地代码修改，要求PR等明天恢复连接；不得用其他账号推送或更改远程，不把本地验收称为远程交付。P5 实现中；P6 未授权开始。下文旧的阶段状态为历史记录，由本段取代。

2026-10-10 最新：P2 私有最终交付验收 PASS，main 基线 ee6eb07921f93ab3373acbe5f3d2c1c1c8741f36。用户授权进入 P3，并批准独立预算 USD 1 / 40 DeepSeek 请求 / 12 Codex 订阅实验回合，单请求120秒、候选/角色600秒、实验1200秒，不充值。P3-A01..A04 真实功能和16个冻结独立复验通过；feature/9-synthesis-loop、Issue #9 / [PR #10](https://github.com/Du-YouLang/Enhanced_Humanizer/pull/10) 的 Git 交付仍须实际 PR CI/main/12归档 refs 同步，私有 p3-accepted.json 为 PASS 才可声称交付完成；评分使用明确的 Sol/J3。Jev 因用户所在地区不被 TypeSafe 支持而阻塞，不新增 OpenRouter 支出。此前文中的“不进入 P3”为历史状态，由本段取代。

当前：**P0_ACCEPTED / P1_ACCEPTED / P2_FUNCTIONAL_ACCEPTED**。P1-A01..A04 已有真实模型、独立隔离复验和预算控制证据。P1 开发交付以 Issue #5 关联 PR 的实际 CI 成功及 main 同步为准；不把 merge/CI 单独当作功能验收。阶段交付分支 feature/5-basic-relay，[PR #6](https://github.com/Du-YouLang/Enhanced_Humanizer/pull/6)。最终 CI/merge/main 一致性及 bundle 哈希记录在项目私有 `.local-workbench/audits/p1-accepted.json`；该记录不存在或非 PASS 时不得声称 Git 交付完成。用户已明确授权开始 P2，独立预算已批准；P2 功能独立验收通过，Git 交付以 PR #8 实际 CI/main 同步及私有 p2-accepted.json 为 PASS 为准（公开文档不预写合并结果）；不进入 P3。

用户已授权专用 WSL2 和 P0 全 Gate 后直接 P1，并批准 P1 独立预算。项目继续使用 Enhanced_Humanizer，首次对外产品发布前复核命名。两份 v0.4 基线哈希未变，80 主需求+6操作 ID、标签/来源/附录完整保留；多阶段需求仅标记本阶段的部分实现。

P0：11 项真实 OS 测试、独立 Linux Codex 登录和 Humanize/Sol 编辑/测试/commit demo 全部通过。PR #4（实现 5c981b5）实际 CI 成功后合并，main 基线 aef940446eadd6a779264de28e266ff3ba2aeb6a；Issue #1 已关闭。见 audits/P0-Linux-2026-10-10.md。P0 ledger 保持 DS 2/4 请求、input 24/output 8；Codex 1/2 回合，input 55,512/cached 31,872/output 448；不重置。

P1：原版 RLAR、Flame Chase 实测；原生 DSH/Humanize 对照；自定义薄 Flow 完成 DS commit→实际暂停→resume 新 Sol 会话→重设计/测试/新 commit。五个仓库只读/禁网独立复验 PASS，模型调用 0；八个 Git bundle（含三个失败尝试）保留在项目私有 backups。P1 验收与 ADR-0007 记录实际边界和测量限制，不能据此宣称增强器有效。

P1 独立预算已用 **30/40 DS 请求、3/6 Codex 回合**。API 保守上界 USD 0.0770688，缓存感知估算 USD 0.009915264–0.019830528，账单 unavailable。DS 非重叠 input/cache/output=40,928/194,688/5,320；Codex input/cached/output=140,968/107,264/3,422，cached 是 input 子集。订阅 API 现金 0，订阅美元成本 unavailable。上限 USD 1 / 40请求 / 6回合 / 每请求120秒 / 每实验900秒，不充值；Windows gate→Linux broker/ledger 在调用前执行。不要重置账本或绕过入口重跑。

Linux EnhancedHumanizer-P0、/opt/workbench/.venv-linux、native Python 3.12.3，固定工具/依赖。VHD 在项目 D 盘；Windows 挂载/互操作关闭，无 sudo workbench 用户。原 portable 3.13.14 缺 pidfd 的失败环境保留。所有新增环境/缓存/会话/实验/日志留在项目；Microsoft 系统组件为已批准 C 盘例外。不得自动重启、unregister、删除 VHD 或复制全局认证目录。

GitHub Du-YouLang、公有仓库及三个正确 Fork 已确认。ADR-0004：开发 PR 实际 CI 成功后可自主合并同步 main，不加严格 main 保护；产品自身每一次 PR 必须人工审核。提交前跑 integrity、治理/预算测试与 Gitleaks。失败历史、refs、bundle 和验收记录保留。当前详细证据见 audits/P1-2026-10-10.md 和 audits/P1-evidence-2026-10-10.json。

P2：Issue #7，[PR #8](https://github.com/Du-YouLang/Enhanced_Humanizer/pull/8)，feature/7-ds-candidates。2026-10-10 用户批准 USD 2 / 100 DeepSeek 请求 / 6 Codex 评分回合；每请求120秒、候选600秒、实验1200秒，不充值，独立账本。ADR-0008 说明任务级候选和命名空间隔离；真实 N=1/3/4/5 共13候选通过，独立隔离/硬测试复验、失败分类/超时/通用任务契约/缓存均通过。J0/J1 原版概率/J3 Sol 已完成同池评分，J2 BLOCKED_CREDENTIAL。使用87请求/2订阅预留回合，API保守上界USD 0.2236917，缓存感知估算USD 0.037955418–0.075910836，账单unavailable。P2详细证据见 audits/P2-2026-10-10.md；最终Git交付须私有 p2-accepted.json 为PASS，26个候选/受控故障归档refs和bundle须实际验证。

P3：详见 audits/P3-2026-10-10.md、ADR-0009。三组真实实验：混合池 M PASS（原A也通过）、全失败池 M恢复PASS、矛盾池REFUSED且最终FAIL；独立Sol Builder真实流式重设计→新DS N3批处理，A/C成功、B并发最坏现金预留门禁停止。预算21/40 DS请求、11/12订阅预留（含2次启动失败），API保守上界USD0.065025、账单unavailable。不重置账本，不结转；P4–P6未执行。完整失败工作区用明确程序快照归档，不冒充模型提交。
