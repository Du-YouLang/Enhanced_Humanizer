# 给 Codex 的实施指导书：Research Agent Workbench v0.4

> **状态：开发任务合同 v0.4（2026-10-10）。** 本文指导 Codex 在用户自己的本地计算机及经授权的 GitHub 账号中逐阶段开发；它不是已执行的代码、已建立的仓库或已验证的性能结果。
>
> **优先级：** 用户明确要求 > 本文的 MUST 条款 > 累积需求总账 PRD v0.4 > 技术建议。遇到冲突，请提出 ADR（架构决策记录），不得擅自把需求删除或降级。

## 0. 接手方式——先读、检查、建库、再开发

你是主实施 Agent（Codex），用户是产品所有者和最终科学验收人。请先阅读本文、`Research_Agent_Workbench_PRD_v0.4_2026-10-10.md`（**权威累积需求总账**）、此前 v0.2/v0.3 和原始用户要求。**第一轮不得直接编写全新 Harness，也不得未经检查便覆盖现有工作。**

第一阶段任务：

1. 检查宿主机（Windows、WSL2、SSD 空间、Python/uv、Conda、Node.js、Git、GitHub CLI），Codex 登录、DSH/DeepSeek API 连通性。只记录非敏感状态，不输出 API Key。
2. 使用已授权的**用户本人 GitHub 账号**，先确认 `gh auth status` 中的身份及将要创建的仓库名、可见性和组织归属；未经用户确认，不创建公共仓库、不 Fork、不推送私有科研材料。
3. 选择本地内置 SSD 为工作区；优先复用当前可工作的 Windows 工具链。若 DSH/Humanize 需要 WSL2，则将 WSL2 虚拟磁盘放在**内置 SSD**，不要放到机械硬盘；记录实测必要性及路径。不准默认执行破坏性安装。
4. 将上游源码作为**固定版本的依赖**评估。优先以 Humanize 自定义 Python Flow 扩展；对于实际克隆、复现或增量开发的外部开源仓库，整理拟 Fork 清单并请求用户一次性授权，随后使用用户账号 Fork；不必 Fork 只读的网页参考项目。对实质使用的仓库维护许可证、来源、固定 commit/tag 和致谢清单，不自动 Star。
5. 初始化用户自己的云端项目、Issue、保护规则（账户套餐不支持时用 CI + 明确人工门禁替代）、CI、PR 模板、ADR、`.gitignore`、敏感信息扫描、可复现的安装说明、运行日志与回滚机制。私有为建议默认值，但最终由用户确定。
6. 每个 Phase 都提交一个可审阅 PR；报告：做了什么、证据、未完成项、开销/用时、下一阶段建议。人类批准前不合并主干。

**必须向用户确认的事项（仅在真正执行相关操作前请求）**：GitHub 权限/新仓库是否私有、项目路径、模型/API 访问方式、初始费用上限、涉及安装或删除的高风险操作、推送含敏感信息内容、主分支合并、四篇/四项科学基准的原始材料。其余常规代码开发可自主执行。


## 0A. v0.4 专项修正：不能遗漏早期需求

PRD v0.3 是以最新一轮 16 项 + 后续 4 项变更为中心整理的，未完整保留数轮更早的需求。**PRD v0.4 是新的权威需求总账**，其 S0–S4 来源标签、稳定需求 ID（例如 `WF-04`、`DS-06`、`OP-05`）和附录 A–C 的映射必须保留。

开始 P0 时额外交付 `docs/requirements/traceability.md`：每个 v0.4 ID 对应 `phase / issue / tests / implementation status / relevant ADR`。**不要把 [P] 建议或 [F] 未来需求当作当前必做，也不要因其不是首版目标就把它们从需求总账里删除。**

### 四类早期重要方向及当前处理方式

1. **Humanize 的协作机制**：调研并实际验证 RLAR 与 Flame Chase 的差异。P1 必须实现两个 Builder 真正接力开发；是否提供双模式切换属于单独产品决策，而不是默认所有流程一股脑启动。
2. **TurboAgent 粒度对照**：首版 DS-Enhanced 按工程任务生成 N 个完整 Coding Agent 候选；TurboAgent 的“逐请求多采样”只是参考/后续实验，不得悄悄改成它来替代任务级多候选。调研需形成 ADR。
3. **Aider / Agentless**：记录强模型设计—廉价模型编辑、局部补丁候选这些低成本对照技术；可作为后续优化参考，不强迫第一轮 16 项 Benchmark 新增更多实验臂。
4. **NVIDIA KDA / OpenEvolve**：保留客观性能反馈驱动的持续代码优化作为未来专项工作流；先保证通用科研代码执行与审计，不把“更快的算子”错误等同于“更可信的科学结论”。

同时，首轮必须测量 DS 在既有 CC/Codex/DSH 与 Humanize 下的实际墙钟、限流与交互响应，不允许只报告后者的正确率。Sol/Astra 必须保留直接开发能力，而非只充当 Verifier。未来每一步切换模型属于明确的未来需求，但第一版不搭通用多模型路由。

## 1. 产品目标与非目标

### 1.1 目标

实现由 **Humanfia Humanize** 统一编排的**双执行者科研工程系统**：

- `DS-Enhanced`：DeepSeek V4.1 Flash 作为执行型 Coding Agent，针对一个清晰定义的工程任务，在独立 worktree 中**并行完成 N=3/4/5 个完整候选**（支持 N=1）；每个候选可以读取代码、修改文件、运行测试。N 默认 3。
- `Sol-Builder`：GPT-6.1 Sol 通过 Codex Harness **直接接力进行设计、重构、编程、测试、性能优化**；绝不是只能评审 DeepSeek。后续允许继续接力 DeepSeek。
- `Sol-Verifier`：独立于 Builder 的新会话，对候选进行结构化检验/必要的高级评价。
- `Sol-Reviewer/Merger`：又一个独立会话，读取**全部成功与失败候选**，自由提炼优点、诊断共性问题、制定并**实际实现一个新候选 M**；可以重写而非仅代码拼接。新 M 重新验收，与 A...N 比较。
- `Judge`：可插拔但**仅限当前明确的 3 个对照后端**：原版 LLM-as-a-Verifier（支持 logprobs 的后端）、Jev 结构化决策、Sol 直接结构化评审。第一版不是通用多模型产品。不得把 Jev 当可写代码的生成模型，也不得把 Sol 的结构化评分冒充原论文概率评分。
- `Research Memory + UI`：完整可追溯的运行事件、项目决策、历史分叉、测试、Git refs；以**可交互工程探索图**为核心的人机协作界面。

### 1.2 非目标

- 不开发自研完整 Coding Harness；DSH 与 Codex 已经承担工具执行和会话运行时，Humanize 负责 Flow。
- 不同时引入多套互相竞争的编排框架（AutoGen、CrewAI、Gas Town 等只借鉴机制）。
- 不在第一轮将 WSL2/Conda/记忆迁移到移动机械硬盘；不开发跨主机“即插即用”。
- 不在第一轮评测让 Agent 自主挑选安装依赖的能力。
- 不承诺 Jev/Verifier/融合必然有效；不把评分视为科研真值。
- 不在第一版支持其他生成模型或云端服务器（保留配置适配点即可）。

## 2. 上游项目：先固定版本并复用

| 项目 | 作用 | 要求 |
|---|---|---|
| `https://github.com/humanfia/humanize` | **唯一主 Flow 编排层**；启动/停止、预算、日志、恢复、TUI/Web | 优先使用 `.hmz/flows/` 自定义 Flow；先验证 DSH 和 Codex 后端。 |
| `https://github.com/llm-as-a-verifier/llm-as-a-verifier` | 原版 `compare/select/track`、概率评分与 PPT 的实验后端 | 先运行官方最小复现；保留其对 logprobs 的要求，固定 SHA、记录 token 用量。 |
| `https://github.com/llm-as-a-verifier/TurboAgent` | 模型请求级并发代理与可视化参考 | **只作参考与对照，不代替任务级多候选**；其逐请求扩展可能拖慢整体开发。 |
| `https://github.com/danielgshea/jev-as-a-judge` | Jev Judge 示例 | 借鉴 API 与测量方法；小样本结果仅作启发。 |
| `https://docs.typesafe.ai/introduction` | Jev 官方 API/原语 | 获取 Jev 访问凭据并完成 smoke test 后才能开启。 |
| `https://github.com/gastownhall/beads` / `https://github.com/gastownhall/gastown` | 持久任务状态、依赖与交接 | 可以参考 schema，不另起一个大编排框架。 |
| `https://github.com/FoundationAgents/MetaGPT`、`https://github.com/microsoft/autogen`、`https://github.com/crewAIInc/crewAI` | 结构化交接、协商、角色分工 | 在 ADR 列出借鉴点即可，不盲目安装。 |
| `https://github.com/cathrynlavery/diagram-design` | 探索图视觉规范和导出样式 | **不是日志库或实时交互引擎**；可以用 React Flow 做交互。 |

对所有实际修改/嵌入的上游项目检查许可证兼容性并记录来源。用户要求对**实际进入开发/复现流程、需要检出源码的外部开源项目**使用其本人 GitHub 账号 Fork 并保留 upstream 链接；第一轮先提交候选 Fork 清单，获一次性授权后批量执行；纯阅读文档或提及的参考链接不机械创建 Fork。若上游许可、仓库权限或 GitHub 平台限制不允许 Fork，应记录原因，不作假。最终交付 `docs/upstreams.md` 列出重点项目，用户自己决定 Star。

## 3. 逻辑架构和责任隔离

```
[Human: 任务合同 / Git 审批 / 预算 / 暂停]
                      |
                 [Humanize Flow]
                      |
     +----------------+-------------------+
     |                                    |
[DS-Enhanced: N 路并发]                 [Sol-Builder]
  DSH + N 个 worktree                 Codex + 独立会话
     |                                    ^
[候选 A/B/C/...: commit + tests]          |
     |                                    |
[固定环境测试器 + 证据摘要]                |
     +--> [Judge: 原版 / Jev / Sol]        |
     +--> [Sol-Reviewer: 看全部候选]        |
                |
          [新 worktree 写候选 M]
                |
          [M 和 A..N 统一复测]
                |
  [接受 / 继续 / 重试 / 全失败诊断 / 人类升级]
                |
       [Humanize 下一轮：交给 Sol-Builder]
                |
        [Git + SQLite/NDJSON + UI]
```

**Agent context 规则：** `sol_builder`, `sol_verifier`, `sol_reviewer` 为分立 Session ID；DS 候选各自 Session ID。交接使用由程序生成、可追溯的 `handoff_package`，不把上一代理完整聊天强行塞入后继上下文。原始日志可展开，摘要不能覆盖事实。若 Reviewer 自己实现 M，其工具写入权限仅针对 M 的隔离 worktree；原始候选与主干只读。

**权限规则：** 由于 Humanize 的 Agent 可能在无逐步工具批准模式下运行，必须通过 OS/容器/工作树层面实施隔离；仅靠 Prompt 禁止删除或修改是不够的。危险命令、破坏性 Git 操作、提交敏感数据、花费超限、main 合并都必须被外部执行层禁止或门禁。为首版明确写出威胁模型与未隔离风险，不能误报“安全沙盒”。

## 4. DS-Enhanced：候选、评分、融合和全失败路径

### 4.1 候选生成

- 一个任务有固定 `task_contract`、`base_commit`、固定环境和候选 N。候选之间共享任务目标与测试接口，但执行进程、文件系统修改、会话、调用预算和日志彼此隔离。N=3 默认，4/5 可在 UI/CLI 设置，N=1 用于基线。
- **候选单位是一次完整的工程任务或明确子任务**。对于“从零完成一个小型项目”，允许每个候选独立实现整个项目。不得偷换为一次模型回复抽样 N 次。
- 对并发 N 设置最大并发数、排队等待、限流/重试策略、费用上限和独立超时。记录候选的首可用补丁时刻、首通过本地可见测试时刻、完成时刻。
- 每个候选最终输出：`base_commit`, `head_commit`, `patch`, `env_hash`, `model_id`, `prompt_hash`, `tool_trace`, `test_report`, `tokens`, `cost`, `timeline`, `known_failures`。
- 防止候选互相读取其他候选输出，避免使独立性失效。相同 base commit，一致可见任务规范；如使用不同种子或采样参数，记录但不人为挑选对某组有利的值。

### 4.2 判断与融合

1. **程序化硬验收**：可安装、可执行、显式单元测试/科学不变量/性能阈值，结果写入不可变记录。失败者仍保留作为 Reviewer 的输入。
2. **评分器对照**：
   - `judge_lav`: 原版 `llm_verifier.select/compare`，需要能返回 score-token logprobs 的模型端点；`Sol` 不应虚报 logprobs 支持。
   - `judge_jev`: 根据 TypeSafe 的 `Choice/Score/Noul`，采用相同、精简的结构化候选证据。其返回值不是论文中 LAV 的概率 reward；Jev 不负责生成补丁。
   - `judge_sol`: 独立 Sol-Verifier 对候选按固定 rubric 给出分项结构化评价；保证可追溯的比较证据。
   - 各 judge 必须在**冻结候选池、冻结测试证据**上进行对照，不允许不同 judge 因为看了不同材料而产生不公平比较；同时保留完整轨迹实验作为单独敏感性分析。
3. **Sol-Reviewer 自由综合**：读取全部候选，包括失败原因、代码、测试和决策证据；独立提出新思路，在新 worktree 直接实现候选 M。它可以全部重写、部分复用、拒绝融合或提出下一轮探索；不得强制要求 mechanical cherry-pick。
4. **公平复测 M**：同一环境、同一独立测试器、同一任务合同。比较 A...N 和 M 的正确性、效率、维护成本、证据可信度，并记录额外的 M 生成时间和成本。不得仅因“融合”自动获胜。
5. **全失败**：若 A...N 全失败，不得交付最佳失败者为成功项目。要求生成 `failure_report`（失败归因、复现步骤、局部有效成果、共性错误、下一轮任务建议）；Reviewer 仍可尝试 M。若 M 也失败，记录 `FAIL` / `INDETERMINATE`，在预算内修复/重启，否则向人类交付诊断，且保留所有分支。
6. **Sol-Builder 接力**：接收当前经过验证的代码与清晰的交接说明，**直接写代码进行重构、优化、替代设计**。它不受 DS 的设计决定约束，可回退到更早的 base。之后同样测试、记录、交接给 DS-Enhanced。允许多轮交替，但设置上限/停止条件。

### 4.3 状态机和停止条件

建议最少：`QUEUED -> CANDIDATES_RUNNING -> TESTING -> JUDGING -> REVIEWING -> MERGE_TESTING -> SOL_BUILDING -> DECISION -> HUMAN_REVIEW -> ARCHIVED`。任何状态可以进入 `FAILED / PAUSED / BUDGET_EXHAUSTED / INFRA_ERROR`；这些状态均可恢复/审计，不与任务失败混为一谈。

停止：明确验收通过并得到人类审阅、达到费用/时间上限、连续改进不足、人类暂停、无法获得关键 API 或环境失败。运行中不得反复看最终隐藏测试分数调参。

## 5. GitHub、分支、PR、回滚、人工控制

- `main`：原则上只经 PR + CI + 人类批准进入；保护 main、拒绝自动 force-push。若 GitHub 账户权限不支持相应规则，实施本地/CI 替代门禁，并清楚报告差距。
- 一个 GitHub Issue 表示一个可验收目标。`feature/<issue>-<slug>` 为主任务分支，`run/<task>/<run_id>/ds-1..N` 为候选分支，`run/<task>/<run_id>/merged` 为 Reviewer 候选，`run/<task>/<run_id>/sol` 为 Sol-Builder 优化分支。
- 所有重要状态保存 Git commit SHA；在运行前、中、后建立检查点，保存任务根提交、候选头提交、Merge 提交；**失败分支也保持远程可恢复引用**（专门命名空间/归档 tags），避免垃圾回收导致不可恢复。主 PR 关联这些 refs。
- 一个可验收任务对应一个正式 PR，不能每轮回复都开 PR；每次候选执行产生 run record 并与 PR 评论或工件链接关联。不要把全部 raw agent transcript 塞入 PR 正文，可附摘要和结构化 manifest。
- 回滚采用 `git revert` 或从历史 commit 新建分支，绝不默许自动 `git reset --hard` 擦除尚未归档的人类文件；高风险操作先检测工作树并请求用户批准。
- GitHub 云端从 **P0** 开始维护；每个阶段至少一份可审阅 PR，失败与被否定的探索不能只剩口头描述。
- secrets、数据集、患者信息、完整个人目录、虚拟磁盘、Conda 缓存均需排除，检查 `.gitignore` 和 push 前 secret scan。

## 6. 记忆、结构化交接和可视化

### 6.1 本地持久存储

存储路径默认内置 SSD，不依赖 Codex/CC 的私有会话记忆。建议 `SQLite (决策/任务索引)` + `append-only NDJSON (不可变事件)` + `artifacts/` + `Git refs`。用户以后迁移磁盘或服务器时才考虑数据导出/恢复。

最少结构：

```
project_contract(id, version, hash, immutable_rules)
task(id, issue_url, base_sha, status, acceptance_hash)
run(id, task_id, flow, n_candidates, timestamps, model_configs, budgets)
attempt(id, run_id, role, session_id, base_sha, head_sha, status)
execution_event(id, attempt_id, sequence, timestamp, category, evidence_uri)
test_result(attempt_id, suite, verdict, exit_code, artifact_uri)
judgment(attempt_id, judge_kind, rubric_version, scores, evidence_uri)
decision(id, task_id, alternatives, reason, evidence_refs, human_approval)
handoff(id, from_role, to_role, current_sha, verified_facts, hypotheses, failures, next_action)
```

各记录必须关联模型实际 ID、SDK/CLI/Harness 版本、输入输出 token（可见时）、费用（可测时）、时间戳及 git sha；无法获取的数据标注 `unavailable`，不得伪造。判断必须引用代码或测试证据；“主观认为通过”不等于客观通过。所有数据可导出、备份和重建。

### 6.2 UI 首版

优先扩展 Humanize Web 或独立轻量页面读取 Humanize 运行日志，避免替换其执行层。核心是**交互探索图**（React Flow 等），借鉴 diagram-design 的简洁布局和清晰对比，但不要把生成的静态 SVG 当数据源。

页面必须展示：任务/Issue、分支与 commit、三至五个候选、各自的成功失败、Judge 三种模式及证据、Reviewer 融合方案、Sol-Builder 接力、预算和耗时、人工注释、决策树、运行日志、Diff、PR 链接。操作包括 `pause/resume`, `view-diff`, `inspect-trace`, `fork-from-node`, `reject`, `approve-for-PR`；权限由后端硬性检查，不把 UI 按钮当成安全保障。

开发 UI 前先保证事件 schema 完整，优先做可用而非华丽的 MVP；预留后续 UI 迭代。

## 7. Benchmark 固定环境（首轮只有一个轨道）

### 7.1 基准集合及固定材料

合计 **16 项**：

- `BugsInPy` ×6：选择真实 Python 错误修复任务，冻结原始仓库 commit 和可靠评测器。
- `SWE-bench Lite` ×6：冻结 instance ID、测试运行器和镜像/依赖版本，选择低成本、可局部执行实例。
- 科研编程 ×4：① PC_ALM 轻量复现；② 基于论文的卒中诊断实现并输出表格+图；③ Exponential Gradient Learning 轻量复现及论文表格+图；④ Granger Causality CPU→CuPy GPU 改写并验证数值一致性与性能。

**科学任务的论文、数据、图表真值尚未给出：**先实现任务契约模板/测试接口，不得臆造论文内容或宣称四项已验收。真正运行前向用户索取具体论文/参考实现/输入数据/预期结果（只在需要时）。

**固定环境原则**：由 Codex **先预装并验证**依赖，之后同一实例的所有系统配置复用同一锁定环境，禁止参评 Agent 通过重新选择依赖占优。使用同一 Conda 管理器和公共科研依赖版本；由于历史 BugsInPy/SWE 实例可能依赖互相矛盾的旧版本，允许*预先准备、固定哈希的独立 task env/container*，不强行把所有任务塞进一个不可用的 Conda env。环境准备工时和失败单独报告，**不计入被测模型任务完成时间**；模型执行后实际运行的测试/调试时间则应计入。若人工需配环境，先通知用户；不能让不同模型在不一样的环境下比赛。

GC GPU 任务确实需要 GPU，记录型号、驱动、CUDA/CuPy 版本，并控制输入规模使整体评测尽量低算力；若硬件不可用，标注 `NOT_RUN`，不得虚报为失败。

### 7.2 比较配置

| ID | 运行系统 | 对照意义 |
|---|---|---|
| A | DeepSeek V4.1 Flash + 原生 DSH（可加既有 CC/Codex 中的 DS 快速基线） | 原始速度/完成率 |
| B | DeepSeek ×N + 自动测试选优 | 多次采样增益 |
| C | DS-Enhanced（含 judge + Reviewer 合并） | 增强器净增益 |
| D | Sol-Builder + 原生 Codex | 强模型基线 |
| E | 原生 DS + Sol-Builder 通过 Humanize 轮换 | 合作增益 |
| F | DS-Enhanced + Sol-Builder 通过 Humanize 轮换 | 完整系统是否超越单模型/官方 Harness |

**额外的 Judge 消融实验（必做）**：在**同一批冻结的 A...N/M 候选**上，分别运行 `J0=自动测试排序`、`J1=原版 LAV（logprobs）`、`J2=Jev-as-a-Judge`、`J3=Sol 结构化 Judge`，记录选择准确率、对错判、排序一致性、单次/总耗时、费用。若 Jev API 不可得，`BLOCKED_CREDENTIAL`，其余照常运行，不能伪造对比。

**额外的 Merge 消融（必做）**：在相同候选池上比较 `best-of-N` 与 `best-of-N + Sol-Reviewer-M`，包括全失败池子；统计 M 独立通过率增益、额外时间和成本。为避免信息泄漏，禁止 Reviewer 看到隐藏测试答案。

### 7.3 四项主要指标与时间细分

1. **任务完成率**：严格独立验收 `PASS/FAIL/TIMEOUT/INFRA_FAIL/INDETERMINATE`。
2. **每成功任务的真实总成本**：模型费用、缓存、验证器、工具运行/GPU；区分订阅额度与 API 现金成本，不能混算成美元。
3. **端到端耗时**：以用户发起任务至交付合格版本的墙钟为主，并报告 `time_to_first_patch`, `time_to_first_test_pass`, `time_to_accepted`, `DS_queue/generation/tools/test`, `Jev/LAV/Sol_judge`, `reviewer+merge`, `Sol_builder`, `CI`。请求级首 Token 延迟作为辅助，避免用 DS 单次流畅性代替系统交付效率。
4. **人工介入次数和时长**：定义干预类别、何时阻塞、恢复耗时，避免把配置环境时长归因于模型。

**公平性**：相同任务、隐藏验收、基础 commit、固定环境/硬件、工具和权限、单任务时间上限；记录总成本，并尽可能在等成本和等时间预算下比较。16 个任务只是探索性小样本，报告逐任务结果、失败类别和区间，不夸大统计结论。第一轮可先挑 2 个 smoke 任务验证整链，再运行 16 个；统一固定 seed/重复规则。

**科研正确性**：卒中诊断的医学论文复现不构成临床可用诊断工具；任务限定为离线科研验证，不能以“图表长得像”代替数值复现。模型不得根据隐藏测试直接调参，不能只保留最好随机种子。

## 8. 开发阶段与 PR 验收（严格先后，支持中断恢复）

### P0 环境 + 用户 GitHub + 真实接口核查

交付：仓库、目录/权限、文档、CI、Issue/PR 模板、锁依赖、CLI/API 探针；`docs/capability-matrix.md` 写明 DS、Sol、Humanize、原版 LAV、Jev **实际**支持哪些能力及不足。验证 Humanize 自定义 Flow API 可用。用户确认费用、可见性与授权。

**Gate：** GitHub main 可保护/人工门禁、`git push`、CI 和 `hmz` demo 真正成功；保存截图/测试日志。未获得凭据，保留可运行 mock 路径并明确标记阻塞。

### P1 基础双 Builder 交替（没有增强器）

先对 Humanize 原有 RLAR 与 Flame Chase 做接口和资源消耗核对，确认可借鉴的交接/轮换机制；用 ADR 明确为何选择当前 Flow（两个内置模式是否出现在 UI 可延期）。

交付：DSH 和 Codex 作为真正 Coding Agent 在 Humanize 中轮流**直接修改**同一目标项目的隔离版本，且各自正确生成 commit/handoff；独立会话，能暂停恢复和约束预算。

**Gate：** 两个模型都完成一轮实际代码编辑+测试；验证 Sol 能重新设计而不是只审查。测量 DS 原生 Harness 与 Humanize 的调度开销。

### P2 DS-Enhanced 候选执行+原版评分/结构化评分

明确**任务级多候选**不可用 TurboAgent 逐请求 N 候选冒充；补充完整候选运行时限、并发延迟、Token 分解以及原版 LAV 的必要接口条件。TurboAgent 只列为可选对照。

交付：N=1/3/4/5 的 task-level 并发 worktrees、硬测试、缓存/重试、候选记录；LAV/Jev/Sol 统一 JudgeAdapter 的实验接口与硬约束。**优先让 Sol 评分可用，原版 LAV 的 logprobs 端点依实际 API 验证接入**。Jev 需有效 key，接不上时不能阻塞整条主线。

**Gate：** N=3 不互相污染；每个候选真实 commit、日志与测试，时延/费用分解；全失败触发正确故障报告。

### P3 Sol-Reviewer 综合与 Sol-Builder 闭环

交付：完整候选（包含失败者）的 Sol-Reviewer 输入、融合 M 的独立 worktree 与重测；Sol-Builder 自主继续重构，再回到 DS-Enhanced；所有角色独立上下文。

**Gate：** 一个混合成功/失败池、一个全失败池、一个无法融合池的受控测试均通过；融合不保证成功，但不能误报；人类可暂停和重启。

### P4 工程记忆与 Git 审计

交付：SQLite schema + NDJSON 原始事件日志 + handoff 生成器 + Git/PR/Issue 追踪 + checkpoint/revert + 项目导出；存储在本地 SSD，备份机制可测试。

**Gate：** 从任意历史合法节点恢复/新开 worktree；失败候选可检索和复现，任务记录不被压缩聊天覆盖，敏感信息不上云。

### P5 UI 原型

交付：交互探索图、运行/候选/评审详情、总延迟和阶段时延、Git diff、日志、审批/暂停/继续；视觉参考 diagram-design。首版先可用，再迭代。

**Gate：** 用户可在 UI 里重建一次多候选→融合→Sol 改进→PR 的路径，点击每个节点可找到真实文件/日志/Git commit；暂停/恢复安全。

### P6 Benchmark 与技术决策

除用户确认的 A–F、J0–J3、Merge 消融外，可以在讨论部分评估 Aider/Agentless 的更廉价替代路线，以及 KDA/OpenEvolve 对数值优化子任务的适用性；不添加到必跑基准以致第一轮超预算。

交付：冻结的 16 项评测定义与任务 ID、任务准备脚本、跑分配置 A-F、J0-J3、merge ablation、数据表及自动生成的延迟/成本/成功率图表；每个结果可追溯来源。

**Gate：** 先 smoke 两项再跑主测试集；环境固定；证据齐全；客观解释哪个方案在预算和总耗时上划算，指出不确定性；明确下一版需要调整哪些组件，不能声称未验证性能提升。

> P0/P1/P2/P3 是算法与编排 MVP，P4/P5 是可审计人机交互 MVP。每个 Phase 在 GitHub 以 Issue/PR 对应，完成一个可独立验收后再进入下一阶段。不要为了等待完整 16 任务材料而阻塞 P0–P5。

## 9. 建议仓库结构（可经 ADR 小幅调整）

```
research-agent-workbench/
  .hmz/flows/research_chase/     # Humanize 自定义 Flow
  src/workbench/
    adapters/                    # humanize/dsh/codex/jev/lav
    orchestration/               # flow + state machine + scheduler
    candidates/                  # N 个 worktree 生成/清理/隔离
    judging/                     # judge adapters + score schema
    synthesis/                   # Reviewer->M + test orchestration
    evidence/                    # fixed-env tests + trace normalization
    memory/                      # event store / SQLite / handoff
    gitops/                      # Issue/PR/refs/approval/rollback
    api/                         # UI local API
  ui/                            # 探索图（如 React Flow）
  benchmarks/
    manifests/                   # 6+6+4 冻结任务清单
    harnesses/                   # 任务运行器和隐藏测试接口
    reports/                     # 结果文件（无私密数据）
  docs/
    requirements/                # PRD 原始记录和 v0.4
    traceability.md              # 稳定需求 ID -> Issue/PR/测试/阶段
    decisions/                   # ADR
    upstreams.md
    capability-matrix.md
    privacy-and-permissions.md
    benchmark-protocol.md
  configs/
    example.yaml                 # 无密钥配置、N、预算、Judge 选择
  tests/                          # 单测、集成、故障注入
  .github/workflows/             # lint/test/secret scan
  README.md
```

实际日志和敏感工件统一存放在 `.local-workbench/` 或用户指定的本地路径（Git ignore），绝不放在 `docs/` 中推送。

## 10. 第一轮给用户的汇报格式

每做完一个 Phase，在 PR 和聊天中提供：

- 完成项 + 测试结果（附对应命令、输出文件与 SHA）。
- 当前 GitHub Issue、Branch、PR 与上下游 Fork 情况。
- 真实花费、总墙钟、瓶颈位置；无法测到的部分明确 `N/A`。
- 当前风险与尚未完成项目；与需求不一致的地方须有 ADR。
- 下一阶段具体任务；**仅对必需授权/实质产品决策请求用户介入**。

**完成定义：** 不是“软件启动成功”，而是用户在本地电脑使用自己的 DeepSeek 和 Sol 访问方式，能启动双 Builder、DS N 路候选、候选验证和独立综合、审计/回滚、通过交互探索图介入，并能在固定测试集合上诚实测得准确率、交付时延、成本和人工干预。

## 11. 引用与事实边界

官方起点：

- Humanize 文档：https://docs.humanfia.ai/humanize/ 、Flow API：https://docs.humanfia.ai/humanize/reference/flows
- 原版 LAV：https://github.com/llm-as-a-verifier/llm-as-a-verifier
- TurboAgent：https://github.com/llm-as-a-verifier/TurboAgent
- Jev：https://docs.typesafe.ai/introduction 、小样本示例：https://github.com/danielgshea/jev-as-a-judge
- SWE-bench Lite：https://www.swebench.com/lite.html
- diagram-design：https://github.com/cathrynlavery/diagram-design

这些资料证明接口/项目存在，**不证明**本项目的 API 权限、命名模型在用户账户实际可用、运行时性能、Jev 评分对科研代码可靠、融合方案一定超越候选。所有这些结论必须用本地运行与冻结基准检验。


## 12. v0.4 验收新增条款

- [ ] `traceability.md` 涵盖 PRD v0.4 中全部稳定 ID，能分别筛选 [C]/[E]/[P]/[F]/[O] 状态；不得只登记旧版 16 个 R-ID。
- [ ] P1 明确记录 RLAR、Flame Chase 的真实可用性、运行成本和选型，不必实现两个独立工作流 UI。
- [ ] P2 记录“任务级 N 路执行”和 TurboAgent“逐请求 N 路”之间的设计边界，避免误将后者作用户确认的需求。
- [ ] P6 或 ADR 保留 Aider、Agentless、OpenEvolve、NVIDIA KDA 的研究结论和未来使用场景，不把它们列成必须安装的核心依赖。
- [ ] 后续每个阶段提交的 PR 都引用 v0.4 稳定 ID 和对应验收证据；如果主实施指南与 PRD 冲突，应先向用户报告或提交 ADR，不得偷偷减少范围。
