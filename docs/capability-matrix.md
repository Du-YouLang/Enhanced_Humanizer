# P0/P1/P2 真实能力矩阵

日期：2026-10-10（Asia/Shanghai）。`PASS` 只针对表内实际操作；mock、初始化、文档说明均不能推出真实编码任务通过。

最新实测优先于下表历史快照：WSL2 Ubuntu 24.04.5、Humanize filesystem/network fence 可执行，11 项 OS 测试通过；独立 Linux Codex 登录和真实 demo 通过，P0 PR #4 已合并。P1 原生 DSH 与 Humanize DSH 真实编码、原版 RLAR/Flame Chase、DS→新 Sol 双 Builder、暂停恢复、独立隔离复验和请求前预算均已通过。见 [P0 Linux](audits/P0-Linux-2026-10-10.md)、[P1 验收](audits/P1-2026-10-10.md)。五个模型实验共 30 DS 请求 / 3 Codex 回合；只是合成任务可用性，后续 P2 实际结果见下文；增强净收益与科研质量仍未验收。以下 P0 早期探针的“未验证”保留为历史，不再表示当前阶段阻塞。

| 组件 | 已验证事实 | 未验证 / 阻碍 | 下一项验收 |
|---|---|---|---|
| DeepSeek 官方 API | 原 GET /models 通过；本轮两个无工具真实文本 POST 均 HTTP 200，返回 deepseek-flash；分别 1.084/1.276 秒，各输入 12/输出 4 Tokens；第二次真实返回 4 个 token 的 logprobs | 未测工具调用/限流；账单实扣及这两次 request ID unavailable；不能推出 score-token 算法有效 | 隔离就绪后验证官方 Harness 真实 Coding；保持原版 LAV 接口与概率含义 |
| 现有 Node DSH | `@deepseek-ai/dsh` 0.1.2-rc.1，version/help 正常；本机选 `deepseek-v4-flash`、max effort | 不是 Humanize 所驱动的 Python SDK；未验证 headless 编码/恢复 | 作为原生速度基线候选，固定版本后再测 |
| 项目 Python DSH | SDK/runtime 0.1.5rc1 的 Windows wheel 安装与导入正常；initialize/close 实测 PASS（修正缓存后 1.129 秒） | 无 prompt；没有代码编辑、命令、测试、commit、恢复或 Token 实测；无隔离证明 | 先验证 OS 隔离，再进行受预算约束的真实 smoke |
| Codex / Sol | CLI 0.162.0-alpha.2；ChatGPT 登录；本地配置和缓存含 `gpt-6.1-sol`；exec JSON/schema/ephemeral/resume 可用帮助 | 未发起新 Sol turn；缓存不是账户实时模型权限；Humanize driver 文档参照 0.153.4，存在协议差异风险；logprobs 未验证 | 使用已有订阅，固定会话与路径，检查 app-server/JSON 使用记录 |
| Humanize | hmz 0.1.0b2；CLI/Flow/fake 通过；正确 Fork 固定 SHA 检出；win32 enforceable 两种模式均 false，受限 DshAgent 配置实测抛 Unfenced，0.028 秒且 0 模型请求 | BLOCKED_OS_ISOLATION，真实 demo 未运行；暂停恢复/工具/双 Builder 未验证 | WSL2 方案等待用户存储决策，隔离拒绝测试后做 P0 demo；P1 才验证双 Builder |
| LAV J1 | MIT，正确用户 Fork 固定 SHA 检出；DeepSeek API 的一般 token logprobs 已实测 | 官方包与官方最小 compare/select/track 尚未复现，score-token/PPT 行为未验证；Sol 未证明有 logprobs | 使用冻结配置做官方最小复现，不能将 API 一般 logprobs 成功当作原版算法成功 |
| Jev J2 | [官方接口](https://docs.typesafe.ai/introduction)用于 typed judgment；仅评分对照 | 项目环境未发现 Jev/TypeSafe key；未登录/请求；示例库 license 未检测到 | 获取用户自行配置的凭据与预算后 smoke；否则 BLOCKED_CREDENTIAL |
| GitHub | Du-YouLang 身份验证；用户批准 PUBLIC；Issue #1 / 草稿 PR #2 / git push 通过；4029a52 的 push/PR 两轮 integrity/secrets 全通过；三 Fork 已核验 | 最新追加提交仍须自己的 CI 证据；按用户决定不启用严格服务器保护；P0 Gate 仍待真实 demo | ADR-0004：轻量开发 PR/CI 后同步 main，产品 PR 仍逐次人审 |
| GPU | RTX 4060 Laptop 8188 MiB；驱动 616.64；现有 CuPy 14.1.1 可识别 1 设备，CUDA runtime 12.9、driver API 13.4 | 有 CUDA_PATH 警告；不是冻结环境；未测科研数值一致性/性能 | P6 在项目内另建固定 CuPy 环境并进行精度验收 |

官方 [DeepSeek 模型说明](https://api-docs.deepseek.com/quick_start/pricing/)把旧 `deepseek-v4-flash` 视为 V4.1 Flash 的兼容别名。新项目配置使用实际 `/models` 返回的 `deepseek-flash`，并同时记录请求 ID、返回 ID、版本可见性；不静默换成 Pro 或其他生成模型。

[OpenAI 身份说明](https://developers.openai.com/codex/auth)区分 ChatGPT 订阅登录与 API 计费；[非交互接口说明](https://developers.openai.com/codex/noninteractive)支持 JSONL usage。已安装 CLI 帮助与本机登录先于文档推断；真正的会话 Token 与现金成本仍需运行测量。

Humanize 安全资料使用 Linux Landlock / macOS Seatbelt；当前 DSH driver 采用 bypass rung + 外部 fence。Windows wheel 存在且初始化成功不能证明 sandbox 成立。见 ADR-0003。

## P2 最新实际能力（历史表不再作为当前阻塞）

N=1/3/4/5 共13个完整官方DSH候选，独立对象/Session/后台目录/PID namespace与实际fence拒绝、提交和硬测试均通过。候选/阶段原子预算在请求前执行，真实排队和超时停止通过。J0、固定原版LAV的score-position logprobs/PPT、独立只读Sol结构化评分已在同一池完成；Jev仅接口离线通过，真实BLOCKED_CREDENTIAL。LAV关闭思考/K1仅接口smoke，两次低思考无评分答案的失败保留；不推出判断或增强有效。见 [P2验收](audits/P2-2026-10-10.md)。
