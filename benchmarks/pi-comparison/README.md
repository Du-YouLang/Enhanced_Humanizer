# Pi 对照增量工作包

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

`smoke-plan.json`保留原v11准备快照。`smoke-plan-v2.json`保留初次v12零模型准备；最终新版`smoke-plan-v3.json`另绑定v12-final，同样预选Black-2和GC共两题×四组×两provider，不含重复补跑赢家。DeepSeek行等待真实计量/模型/工具及验收回放门。用户已亲自完成Pi独立官方ChatGPT订阅OAuth，真实gpt-6.1-sol访问探测通过；OpenAI比较采用此订阅通道，无需另购API key。账号元数据加密不可明文比对，不能假报账号一致。所有正式比较入口仍关闭，访问探测不等于工具或任务验收；256次全量矩阵仅为指导书提案。没有第二份100美元额度，不复制全局认证、不自动全题重跑。见[ADR-0027](../../docs/decisions/ADR-0027.md)。

后续真实smoke先串行并避开现有主集计算，按同模型/同环境/同公开合同对照；H0产品组合另表，并保留订阅与API费用的不同单位。Research Loop的后台任务、checkpoint、恢复和费用归属仍需专项实际控制，不能从扩展加载通过推断完整支持。

实际证据与限制见[能力矩阵](docs/capability-matrix.md)、[风险记录](docs/risk-register.md)和[本轮审计](../../docs/audits/Pi-comparison-Phase0-2026-10-12.md)。公开PR只包含适配/元数据和脱敏证据摘要，原轨迹、患者/科研材料、密钥、上游包和运行目录继续私有。
