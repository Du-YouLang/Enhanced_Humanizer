# Pi 对照增量工作包

2026-10-15用户直接授权补全16题：新入口`runners/run_pi_full_main.py`与`full-main-plan-v3.json`只分发此前未执行的14题112格，原Black-2/GRANGER16格及其补充记录保留。沿用同一累计10000次/USD200账本；Luna负责只读监控，Sol负责科学核验/代码。11题实际公开工具和3题科研环境绑定、SDK/重连正负门禁已零provider通过，正式模型进度取实际新批次回执。见[补测审计](../../docs/audits/Pi-full-main-2026-10-15.md)。下文两题/256次提案/100美元为历史范围，不覆盖本条；不启用额外重复轮次或外部发布。

2026-10-14最新授权及门禁：用户批准在Black-5之后推进预选16格正式对照，累计上限沿用USD200/10000次，无第二份额度，GitHub继续暂缓。新的官方SDK适配已通过四profile内存认证/真实OS隔离、五wire工具计量与错误usage/developer负对照、Research Loop后台/Git检查点/跨owner拒绝及Black-2/GRANGER私有裁判实际正负重放。订阅凭据只经私有管道进入官方AuthStorage内存，不把认证文件授予模型工具。实际执行采用单独`formal-plan-v3.json`，旧准备与首次真实工具HTTP422失败保留；真实provider工具门禁、任务结果及科研源代码复核仍以独立回执为准。见[正式对照审计](../../docs/audits/Pi-formal-2026-10-14.md)。下文“未授权/100美元/关闭”描述历史准备，不覆盖本条。

状态：真实安装、四组资源/OS隔离、CLI和合成工具链控制通过；真实供应商工具探针与正式两题smoke尚未执行。保留Humanize/DSH/Codex和原A–F，Pi只是新增对照，不替代项目Harness。

用户指导书v1.0原件另存项目私有intake，SHA256 `57cf23e6469a4dcaf03a17c71dd3ab7140874f111901b298e89224faf35031fb`。其中安装示例、授权建议和直接执行段落是待核验方案；最新用户的256000输出、公共15分钟/科研20分钟、累计10000请求/$100、本机计算及GitHub授权优先。参见[ADR-0026](../../docs/decisions/ADR-0026.md)。

P0=原生Pi，P1=Scientific Skills，P2=NeuroForge，P3=Research Loop；这四个编号不表示原项目开发阶段。运行时为本项目D盘上的WSL/Ubuntu，Node24.19.0、Pi1.1.0、Scientific1.7.0、Research Loop0.6.3、NeuroForge固定commit。Windows操作员继续使用本项目工作区；没有全局npm安装、全局认证迁移或安装脚本执行。

`versions.lock.json`及`npm-lock.json`固定上游与传递依赖；`profiles/`禁用环境自动发现并列出每组资源；`tasks/`映射原16题，仅放公开元数据。实际可见测试、精确环境/权限及私有裁判必须从既有P6 preparation绑定，不能仅凭这些模板开启模型。科学材料已经冻结，不采用指导书中陈旧的“科学四题缺资料”结论，也不替换论文或降容差。

可以从独立比较工作树执行以下免费检查：

```powershell
& D:\Anaconda\python.exe -m unittest discover -s tests -p test_pi_comparison.py -v
& D:\Anaconda\python.exe benchmarks/pi-comparison/runners/plan.py
```

`runners/probe_linux.py`在已有项目WSL中调用官方Pi资源加载器，复用已验证的Humanize fence及非root user/mount/PID namespace；`runners/tool_control_linux.py`用合成HTTP响应触发真实文件写入、测试及Git提交，并验证wire256000。其provider标识明确为`workbench-fixture`，成本0，不能算真实模型实验或两题smoke。调用者须先把文件送入项目WSL的独立controller目录，运行目录必须为新的`/opt/workbench/pi-comparison/...`路径；既有目录/失败记录不能覆盖。

`runners/events.py`只读取私有JSONL，按LF而非Unicode换行分割，仅统计assistant `message_end`；`turn_end`/`agent_end`副本不重复计Token。无法获取的reasoning、账单及细分时延留null+原因。`agent_settled`或Pi退出成功不是隐藏验收PASS；原私有裁判才有验收权。

`smoke-plan.json`保留原v11准备快照。`smoke-plan-v2.json`保留初次v12零模型准备；`smoke-plan-v3.json`保留v12-final准备；当前新版`smoke-plan-v4.json`绑定v12-final2，同样预选Black-2和GC共两题×四组×两provider，不含重复补跑赢家。DeepSeek行等待真实计量/模型/工具及验收回放门。用户已亲自完成Pi独立官方ChatGPT订阅OAuth，真实gpt-6.1-sol访问探测通过；OpenAI比较采用此订阅通道，无需另购API key。账号元数据加密不可明文比对，不能假报账号一致。所有正式比较入口仍关闭，访问探测不等于工具或任务验收；256次全量矩阵仅为指导书提案。没有第二份100美元额度，不复制全局认证、不自动全题重跑。见[ADR-0027](../../docs/decisions/ADR-0027.md)。

后续真实smoke先串行并避开现有主集计算，按同模型/同环境/同公开合同对照；H0产品组合另表，并保留订阅与API费用的不同单位。Research Loop的后台任务、checkpoint、恢复和费用归属仍需专项实际控制，不能从扩展加载通过推断完整支持。

实际证据与限制见[能力矩阵](docs/capability-matrix.md)、[风险记录](docs/risk-register.md)和[本轮审计](../../docs/audits/Pi-comparison-Phase0-2026-10-12.md)。公开PR只包含适配/元数据和脱敏证据摘要，原轨迹、患者/科研材料、密钥、上游包和运行目录继续私有。

新增官方SDK工具计量控制已真实通过：五次合成wire/完整工具链及错误usage负对照，输入/输出/cache统计与mock账本一致；主集活动期间Windows/native实际探针门均拒绝。免费入口是`runners/run_sdk_tool_probe.py`（默认fixture）及`--fixture-fault usage`。真实P0工具探针须显式选provider/执行参数、空闲主集、精确源码正负控制、干净提交和共享累计账本；当前尚未运行。此SDK适配不启用正式任务矩阵，也不把订阅内部wire计量或OAuth只读刷新称为已验。见[SDK控制审计](../../docs/audits/Pi-SDK-tool-gate-2026-10-12.md)。
