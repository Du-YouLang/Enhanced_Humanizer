# Pi 官方 SDK 工具与计量控制 · 2026-10-12

本轮复用固定Pi1.1.0的`createAgentSession`和默认工具，模型循环由官方SDK负责。传输观察器设置600秒请求取消信号、最多1000次SDK dispatch，关闭SDK自动重试、压缩和cache warming；DS实际wire次数仍由既有RecoveryBroker及共享主集账本负责，订阅内部wire次数继续标为未验证。

| 真实零模型控制 | 结果 |
|---|---|
| SDK→恢复/计量Broker→合成HTTP→write/bash/test/Git | PASS，五次wire/五次结算、输出上限均256000、请求timeout均600；四次工具执行、模型错误0 |
| 输入/输出/cache Token一致性 | PASS，SDK统计50输入/25输出/0缓存，与独立mock账本逐项一致 |
| 错误usage负对照 | PASS，故意令`total_tokens`不自洽；仅一次预留、未结算、无文件/工具执行，原未知usage预留保留；不按断线重试 |
| 候选复验 | 文件函数及Git提交在独立fence中重验；此复验不开放auth或模型runtime路径 |
| 当前主集串行前置门 | Windows拥有者查询和原生PID/start-ticks查询均真实拒绝在活动主集期间启动Pi实际探针，发生于读取真实key之前 |
| 源码准入 | 真实模式必须先找到当前控制器/SDK driver/共享transport源码匹配的正负控制回执；默认只运行fixture |

上述fixture使用独立mock账本及固定本地合成endpoint，真实模型访问/费用0。主集同期在单独执行真实模型请求，整体账本正在变化，不能用整个生产账本字节不变来证明本次控制零调用。Pi原始事件及包含上游能力的spec继续私有，不发布到GitHub。

新入口`benchmarks/pi-comparison/runners/run_sdk_tool_probe.py`仅用于P0微型工具探针，默认fixture。真实模式还需显式执行参数、干净Git源码、Windows和native空闲预检、既有累计授权和精确模型身份；DeepSeek实际key只经内存/管道进入受保护控制器，候选仅获Broker capability。OpenAI使用Pi自己的官方独立订阅文件，精确文件只读；不能把该权限描述成所有工具均无法读取自身凭据。OAuth刷新在只读环境中的行为仍需实际工具探针验证。

两次预检服务于同一操作员的串行调度，不是跨宿主共享互斥锁。本轮主集仍在运行，未启动真实Pi工具探针。SDK request signal对订阅实际transport的作用仍待真实验证；SDK dispatch/assistant message都不冒充订阅API wire计量。

汇总私有回执：`.local-workbench/pi-comparison/intake/sdk-tool-controls-final.private.json`，保留早期准备与所有日志。现有四组资源/OS控制和旧CLI合成控制继续作为独立证据，不把本次P0 SDK控制算作P1/P2/P3扩展、PRL后台/恢复或隐藏任务验收。

正式Black-2/GC×四组×两provider smoke与256次矩阵仍关闭。当前新增工作不会改A–F、活动v12-final2冻结协议、旧样本、数值门或累计预算。Pi收益和完整P6仍无完成结论。
