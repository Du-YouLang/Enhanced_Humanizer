# GRANGER 验收修复与本机结果

GRANGER 的验收阻碍已经解决。八份冻结候选通过独立数值检查和实质 GPU 算法源码复核，原先冻结选择对应的 A–F 六臂全部通过。候选没有修改、模型没有重跑，数值容差、GPU worker、隔离和累计预算保持原样。

## 环境与检查器修复

原始故障是控制器环境缺少可见的 `threadpoolctl`，并非 GRANGER 环境未安装该依赖。修复复用冻结环境中的 3.6.0 纯 Python 模块，避开 Python 3.11 与 3.12 的二进制依赖混用。真实 NumPy/OpenBLAS 操作验证限流上下文内线程数为 1；环境路径别名按真实文件去重。未来入口在模型生成前检查依赖。

源码检查另有两类误判。DS0/E 使用函数字典缓存、A/B 使用普通字典缓存，均被旧检查器的 `.get()` 规则拒绝；A/B 的可选 `cp.asnumpy()` 仅转换边/窗口元数据，冻结主机输入不会触发。独立复核绑定每份源码哈希和具体调用位置，确认实际 RawKernel 构建设计或 Gram/RHS、GPU 求解、显式残差平方和与自然对数比值。没有 dummy kernel、CPU 回归、答案读取或防护替换。数值 worker 的信号回传拦截未放宽。

## 实际恢复过程

原运行 `p6-main-execute-SCI-GRANGER-GPU-20261013T060508Z` 的失败、候选、评分、选择、原始拒绝和中间数值结果均保留。补充源码和计划位于项目 WSL 的 `/opt/workbench/recovery/p6-granger-acceptance-20261013-v2` 与 `v3`，没有覆盖原生主集源码。

第一轮恢复实际耗时 94.435 秒，复用 C 已完成的 GPU 输出，其余五份此前未完成的数值验收在原科学隔离环境中执行。第二轮实际耗时 20.993 秒，复用六份已完成的数值检查，仅补 A/B 的检查，并完成八份精确源码复核。GPU 计算全部使用本机 4060。没有重新生成候选或重新评分。

最终回执为原运行目录内的 `control/granger-reviewed-acceptance.json`；原 `receipt.json` 保留中间 INDETERMINATE，不能单独替代最终补充判定。读取结果时须同时保留原始批次状态及补充回执，不把历史 INFRA_FAIL 擦掉。原模型阶段的完整墙钟区间仍为 unavailable，排除时延比较。

最终回执 SHA 为 `01f430c41036aaf32fd98aecc197e5b1d6f4f236636ddce270c08fa4405a1e5e`，源码复核计划 SHA 为 `7387534a205d50419768fdfe1cdd94e38555c607cd9932a0b64364960c6826f1`。每份候选通过 27 类数值检查及 10 份重复计时输出，跨八份候选的最大绝对误差为 `2.638446102223857e-12`；13 种非法输入、非连续输入、类型/device/输入不变和实际 RawKernel 检查也通过。

30 秒只读监控已升级为 `p6-readonly-observer-v3`，新拥有者 PID35212 与 HKCU 用户登录恢复指向无窗口入口。旧监控、原检查器和历史批次均保留；新监控核对精确补充回执和源码后显示 15 题主流程完成、14 次敏感性完成，完成数包含失败。GRANGER 的同池轨迹敏感性尚未执行，后续只有匹配原 source_run、源码、manifest 的完整敏感性回执才能解除该待办；旧 Black-5 中断现场继续保留。监控没有模型派发权限，45 分钟巡检维持现有授权。

## 验证与账本

Windows 全套测试 217 项通过（8 项平台跳过）；原生 Linux 的恢复、依赖、来源拒绝、源码复核正负控制共 23 项全部通过。控制覆盖精确 GPU 输出复用、输入/worker/资源参数篡改拒绝、错误或过期源码复核拒绝、数值失败不可提升、未知 `.get()` 拒绝和已完成结果跳过。

独立最终核验再次检查原始源码、候选完整 Git 证据、冻结选择、数值结果、六臂 schema 与持久化日志，并再次执行已完成入口验证没有新增 GPU 评估、日志写入或模型调用。精确核验结果保存在项目私有 `.local-workbench/audits/GRANGER-acceptance-20261013.private.json`。

API 账本 SHA 为 `aa7b6e588d178502f96f9e0efb8e1ff362b2ce77efd7c3ed303d494b0355fa40`，累计 5557 次 DeepSeek 请求、178 个订阅实验回合、USD99.7752408 保守上界，实付 unavailable。本次新增 API 请求、Token 使用及 API 费用均为零，历史余额和未知预留没有改写。

本地阶段分支为 `codex/granger-acceptance-repair`，源码在 `.local-workbench/worktrees/granger-acceptance`。GitHub 推送、PR 与远程 CI 按用户要求暂缓。本次不能代替完整 P6、Pi 或新 P7 交付验收，也不构成融合机制收益或其他硬件性能的结论。设计决定见 [ADR-0031](../decisions/ADR-0031.md)。
