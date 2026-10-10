# P0 真实能力矩阵

日期：2026-10-10（Asia/Shanghai）。`PASS` 只针对表内实际操作；mock、初始化、文档说明均不能推出真实编码任务通过。

| 组件 | 已验证事实 | 未验证 / 阻碍 | 下一项验收 |
|---|---|---|---|
| DeepSeek 官方 API | 使用本机 DSH 已保存凭据，仅内存读取；GET `/models` HTTP 200，0.203 秒；返回 `deepseek-flash` / DeepSeek-V4.1-Flash | 未生成，未测工具调用、Token、限流、logprobs、现金扣费 | 批准后一个固定小请求，检查 actual model/usage/request ID |
| 现有 Node DSH | `@deepseek-ai/dsh` 0.1.2-rc.1，version/help 正常；本机选 `deepseek-v4-flash`、max effort | 不是 Humanize 所驱动的 Python SDK；未验证 headless 编码/恢复 | 作为原生速度基线候选，固定版本后再测 |
| 项目 Python DSH | SDK/runtime 0.1.5rc1 的 Windows wheel 安装与导入正常；initialize/close 实测 PASS（修正缓存后 1.129 秒） | 无 prompt；没有代码编辑、命令、测试、commit、恢复或 Token 实测；无隔离证明 | 先验证 OS 隔离，再进行受预算约束的真实 smoke |
| Codex / Sol | CLI 0.162.0-alpha.2；ChatGPT 登录；本地配置和缓存含 `gpt-6.1-sol`；exec JSON/schema/ephemeral/resume 可用帮助 | 未发起新 Sol turn；缓存不是账户实时模型权限；Humanize driver 文档参照 0.153.4，存在协议差异风险；logprobs 未验证 | 使用已有订阅，固定会话与路径，检查 app-server/JSON 使用记录 |
| Humanize | hmz 0.1.0b2；Windows CLI/version/help、Flow API、`hmz.sdk` 导入；自定义 p0_probe + 官方 fake driver PASS；下一轮 cost budget 拒绝 PASS | 真实 demo 未运行；暂停恢复、工具、双 Builder、费用记录未验证；Windows fence 未证实 | 正式源码 Fork/固定 SHA 后做真实 P0 demo；P1 才验证双 Builder |
| LAV J1 | 上游存在，MIT，固定候选源码 SHA；README 需要支持 logprobs 的端点 | 未安装/复现；未确认 score-token logprobs；现有 Sol 登录不能充当该能力的证据 | Fork 授权后官方最小复现；不支持即 BLOCKED_ENDPOINT |
| Jev J2 | [官方接口](https://docs.typesafe.ai/introduction)用于 typed judgment；仅评分对照 | 项目环境未发现 Jev/TypeSafe key；未登录/请求；示例库 license 未检测到 | 获取用户自行配置的凭据与预算后 smoke；否则 BLOCKED_CREDENTIAL |
| GitHub | gh 2.97.0 在线身份 `Du-YouLang`；HTTPS；repo/workflow/read:org/gist scopes；无组织；同名 repo 查询 404 | 未创建、未推送、未验证仓库写权限/保护套餐/CI | 批准私有个人仓库及权限后真正 create/push/PR/CI |
| GPU | RTX 4060 Laptop 8188 MiB；驱动 616.64；现有 CuPy 14.1.1 可识别 1 设备，CUDA runtime 12.9、driver API 13.4 | 有 CUDA_PATH 警告；不是冻结环境；未测科研数值一致性/性能 | P6 在项目内另建固定 CuPy 环境并进行精度验收 |

官方 [DeepSeek 模型说明](https://api-docs.deepseek.com/quick_start/pricing/)把旧 `deepseek-v4-flash` 视为 V4.1 Flash 的兼容别名。新项目配置使用实际 `/models` 返回的 `deepseek-flash`，并同时记录请求 ID、返回 ID、版本可见性；不静默换成 Pro 或其他生成模型。

[OpenAI 身份说明](https://developers.openai.com/codex/auth)区分 ChatGPT 订阅登录与 API 计费；[非交互接口说明](https://developers.openai.com/codex/noninteractive)支持 JSONL usage。已安装 CLI 帮助与本机登录先于文档推断；真正的会话 Token 与现金成本仍需运行测量。

Humanize 安全资料使用 Linux Landlock / macOS Seatbelt；当前 DSH driver 采用 bypass rung + 外部 fence。Windows wheel 存在且初始化成功不能证明 sandbox 成立。见 ADR-0003。
