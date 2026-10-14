# 已核验能力

本表区分实际观察与尚未执行，不把安装或合成响应算成模型质量证据。

| 配置 | 实际加载 | 隔离/启动 | 合成工具链 | 真实模型/隐藏验收 |
|---|---|---|---|---|
| H0/原A–F | 既有官方DSH/Codex/Humanize，v11冻结 | 已有实际runtime控制通过 | 历史控制保留 | v11有限主集运行中，未完整接受 |
| Pi-P0 | Pi1.1.0，0 Skills/0 extensions | PASS，uid1000/private PID/无有效cap | PASS：5个fixture请求、4工具、文件/测试/commit | NOT_RUN |
| Pi-P1 | Scientific1.7.0，162 Skills，sci_find工具及sci命令 | 同上PASS，其他组资源不可读 | 同上PASS | NOT_RUN，未证明模型实际选用Skill |
| Pi-P2 | NeuroForge固定8f589b47…，实际1个mne-python入口 | 同上PASS，0 extensions | 同上PASS | NOT_RUN，不能声称其他神经库Skill已存在 |
| Pi-P3 | Research Loop0.6.3，1 Skill/1 extension/12 prl工具注册 | 同上PASS，无P1/P2资源 | 同上PASS，未调用prl后台工具 | NOT_RUN，后台/恢复门待验 |

四组实际拒绝共享Codex auth、控制器和其他profile/package读取，拒绝未授权活动loopback canary连接；运行库不可写、自己工作区可写。原始回执`/opt/workbench/pi-comparison/controls-20261012-v2/receipt.json`，SHA256 `8ce86facd0c27027e13a911e34d833920cc8d7dbf353e176e2fb8548cf912420`。旧v1控制保留。

官方CLI在同一fence/namespace中实际version/help/catalog通过：版本1.1.0，离线catalog存在deepseek-flash而非旧deepseek-v4-flash。没有调用模型。采用官方本地npm固定版本及ignore-scripts安装，传递依赖锁SHA80b9e4c54e300b1d015547bd8f6dcc3a466183ca483ac9e764b42abde5b89eda。

四组`tool-control-20261012-v2-P0..P3`实际wire均为max_tokens256000、stream_options.include_usage=true、/chat/completions，工具无错误、无重试、agent_settled=true；每组五条合成assistant使用量只用于归一化控制，绝不是供应商账单。官方Pi工具执行了写文件、Python断言和Git提交；不是从零重写agent循环。后台PRL、模型reasoning=low映射、长消息/缓存账单、真实API限流与压缩恢复仍未验。

| 供应商条件 | 证据 | 当前边界 |
|---|---|---|
| DeepSeek官方API | H0已有真实请求及wire256000证据；Pi仅合成HTTP链通过 | 待Pi真实独立tool探针、严格计量及同推理模式核验 |
| OpenAI API | 本次Windows/WSL项目进程未配置OPENAI_API_KEY；未搜索/复制全局认证 | BLOCKED_CREDENTIAL，尚无API模型ID可冻结 |
| Codex订阅 | H0既有独立登录及真实实验 | 独立订阅层；不会借此假定Pi/OpenAI API已授权/可计美元 |

上游来源：[Pi安装](https://pi.dev/docs/latest/quickstart)、[CLI/资源](https://pi.dev/docs/latest/cli)、[Scientific1.7](https://pi.dev/packages/pi-scientific-skills)、[NeuroForge](https://github.com/HughYau/neuroforge-skills)、[Research Loop0.6.3](https://pi.dev/packages/pi-research-loop)。Registry和repo标注MIT；Scientific分发包含上游资料与许可证声明，不能把所有嵌入材料和数据视为自动获得本项目公开再分发许可。

2026-10-12独立订阅更新：Pi官方ChatGPT OAuth真实gpt-6.1-sol无工具访问PASS（21输入/5输出Token，4.443秒，现金API0）。新账号字段加密，明文一致性不可见。此路由不需要另购OpenAI API key；先前API路线的BLOCKED状态仍为其历史记录。正式四profiles工具/计量/隐藏任务门仍未验收。新v12角色1000/请求600/网络五次方案见ADR-0027；旧v11准备配置保留，新对照另冻。
