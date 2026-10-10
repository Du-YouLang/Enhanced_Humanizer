# 上游来源、许可证与拟 Fork 清单

审计快照：2026-10-10。完整 SHA、发布时间、发布包哈希和 CI action SHA 见 [upstreams.lock.json](../configs/upstreams.lock.json)。HEAD 是本轮审核候选，并非已经检出的源码依赖。

| 上游 | 用途 | 许可证（元数据） | 固定候选 SHA | 本轮操作 |
|---|---|---|---|---|
| [humanfia/humanize](https://github.com/humanfia/humanize) | 唯一主 Flow 编排层 | Apache-2.0 | `0488ca796c44e16b0b30468e673f541d358b07a9` | 请求 Fork；只读源码元数据 + 发布包接口审计 |
| [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) | 官方 DS 工具运行时与 SDK | MIT | `d743267388641bc76f17c45ce8b4c231aed1d32c` | 请求 Fork；已复用现有 CLI 与项目内 wheel |
| [llm-as-a-verifier/llm-as-a-verifier](https://github.com/llm-as-a-verifier/llm-as-a-verifier) | 原版 J1 官方最小复现 | MIT | `90e8fc215606447d6d31e9e24bff7200fb0c0994` | 请求 Fork，未安装/检出 |
| [llm-as-a-verifier/TurboAgent](https://github.com/llm-as-a-verifier/TurboAgent) | 请求级多采样参照 | Apache-2.0 | `31ea8dadc00211b96544d3edd02ded1ef64e9856` | 只读参考，不 Fork/安装 |
| [danielgshea/jev-as-a-judge](https://github.com/danielgshea/jev-as-a-judge) | Jev 测量参考 | 未检测到 | `adfea74905f721ea2594e22804c8c8edf1693163` | 不复制/嵌入源码；优先官方 API 文档 |
| [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design) | P5 视觉参考 | MIT | `246d6d71d752245403d2bf28d27f124192584d18` | 只读参考，非事件存储引擎 |
| [openai/codex](https://github.com/openai/codex) | 既有官方 Sol Harness | Apache-2.0 | `c3d3b142d10f4316b46e35aad7e5317e7e506cb7` | 仅核查来源，不检出/改写 Harness |

Codex 上游 HEAD 不是已安装 CLI 的源码映射。实际固定 CLI 0.162.0-alpha.2 + 可执行文件 SHA256 `3553cd6e7df5a093d8cb8301cd8088a57e0971aba71ddbe0e67f7f44a15cdf68`。桌面更新后须重新验收，不能悄悄改变实验版本。现有 Node DSH 固定 0.1.2-rc.1，npm integrity 单独保留于审计证据；不把最新 npm 版本当作已装版本。

拟一次性授权 Fork：以上前三个仓库到 `Du-YouLang` 个人账号。它们都是公开上游；Fork 预期仍公开，而自己的 Enhanced_Humanizer 推荐私有。Fork 中不得添加本项目研究材料、API 密钥或私有运行记录。不自动 Star。授权后先核查是否已有同源 Fork，复用合适 Fork，并将 origin/upstream/固定 commit 写入清单。

本轮更新：用户已有 DSH 和 LAV Fork 来源正确，LAV 名为 `Du-YouLang/llm-as-a-verifier-ds4p1`；经明确授权补建 `Du-YouLang/humanize`。前三个源码已从用户 Fork 在项目内固定上述 SHA 检出，origin/upstream 与时长见 lock 和 [补充核验](audits/P0-GitHub-followup-2026-10-10.md)。未 Star、未修改上游源码。`oh-my-humanize` / `humanize-plugin` 是已归档旧项目，不作为当前编排层。

后续参考目录继续保留在 PRD §14：Beads/Gas Town、MetaGPT/AutoGen/CrewAI/LangGraph、Aider/Agentless、OpenEvolve/NVIDIA KDA、上下文工程、BugsInPy/SWE-bench。它们不是当前核心依赖。P6 确定实际 Benchmark 仓库/任务后，再请求确切的增量 Fork 范围。

集成时逐项保留 LICENSE/NOTICE/作者与来源；本项目自己的许可证尚未由用户决定，未擅自选择开源许可证。

P0 实际已装的 32 项包版本、许可证元数据与分发内 license 文件索引见 [installed-packages-p0.json](../configs/installed-packages-p0.json)。原有上游 notice 保留在发布包中；缺元数据项明确记为 unavailable，不将此清单冒充完整许可兼容性结论。

P2复用固定LAV源码90e8fc2，MIT LICENSE随Linux源码保留。通过原版select(client=...)注入计费HTTP客户端，算法/概率提取/PPT未改写。optional OpenAI/Google客户端构造器未使用，不安装额外SDK。Jev仅按官方typed Score文档实现接口，不嵌入无许可示例库；TurboAgent仅请求级对照参考。P1 Linux依赖lock未变。详见ADR-0008。
