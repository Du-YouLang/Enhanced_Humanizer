# Pi新增对照准备审计

本轮完成可独立复核的免费准备，状态PASS_RESOURCE_AND_OS_CONTROLS + PASS_SYNTHETIC_PI_TOOL_CHAIN；指导书完整Gate P0和Gate P1尚未通过，真实API/两题smoke没有执行。见[ADR-0026](../decisions/ADR-0026.md)及[能力矩阵](../../benchmarks/pi-comparison/docs/capability-matrix.md)。

完整读取用户指导书，项目内保留精确原字节SHA57cf23e6469a4dcaf03a17c71dd3ab7140874f111901b298e89224faf35031fb。对照固定Pi1.1.0/Node24.19.0、Scientific1.7.0、Research Loop0.6.3、NeuroForge8f589b47f1c95ae3c736f2dfd12d9f42a8bc7be4；npm integrity及Node14b342e7…SHA验证后本地安装，传递依赖lock另存public metadata。一次大包代理下载IncompleteRead保留，后续重新下载同固定上游并验证哈希才解包；这不是模型重试。

本机D盘为内置YMTC SSD；原生新环境全部在本项目D盘WSL VHD/opt/workbench/pi-comparison，不触及外置WD HDD。安装runtime21.537秒；没有生命周期安装脚本。旧runtime/主集源码/认证未改。四组SDK资源加载、uid1000/零effective cap/private PID、读写边界、peer+auth+包负控制及未授权真实loopback连接拒绝PASS；v2实际receipt SHA8ce86facd0c27027e13a911e34d833920cc8d7dbf353e176e2fb8548cf912420。CLI version/help/catalog分别0.494/0.384/0.386秒通过，离线内建deepseek-flash ID存在。

四组原生CLI合成工具控制实际用固定fixture响应驱动：每组5HTTP请求，全部max_tokens256000及include_usage；执行4个真实write/bash工具、Python断言与Git提交，工具错误0/自动重试0/compaction0/agent_settled=true。P0/P1/P2/P3墙钟分别1.233/1.907/1.214/1.762秒；tool-control-20261012-v2-P0..P3的原始事件与receipt全部私有，旧P0 v1保留。归一化真实63event fixture为5assistant usage而非重复统计turn_end/agent_end，reasoning/cash/未测细分时延显式null+原因。

最终工具控制源码补齐了中断/非法JSON的失败留证；fresh tool-control-20261012-final-P0..P3四项重新全部PASS，源码SHA5226a9440e9bd08cfbffdc73bc8451c38f801a9e401f7fe5fec9548f62920d7a，墙钟1.281/1.752/1.152/1.637秒。此前v1/v2证据未覆盖。新增三项实质回归测试涵盖Unicode LF framing与事件去重、缺失usage/retry不冒充成功、精确v11任务hash及256000/时限/禁止模型启动；治理及原86ID完整性检查通过。

这些是合成响应的工具/传输/日志证据，provider明确workbench-fixture；真实provider调用0/API现金0，不能算正式benchmark成绩或声称Skill被模型自然调用。P3实际注册12工具，但没有启动后台PRL Run、恢复或计费，所以专项门仍NOT_RUN。

代码交付：独立16题元数据合同、四profiles、attempt JSON Schema、LF JSONL归一化与实际Linux资源/工具控制、预冻结两题smoke准备计划。smoke Black-2/GC的8个DeepSeek格等待门，8个OpenAI API格BLOCKED_CREDENTIAL；整个模型入口关闭，256次方案未启动。科学任务沿用已READY冻结输入而非另造替代论文。活跃v11批次继续原源/协议；本轮零模型控制不会被混入其成绩或重置累计额度。

针对其他失败因素的实证见[P6因素审计](P6-other-factors-2026-10-12.md)。原主集累计费用不是本轮Pi调用费用；本轮用户不需再次操作或提交密钥。待DeepSeek真实计量/low/tool/独立验收回放、PRL后台和OpenAI API实际条件后，才可把相应行标为正式可运行。
