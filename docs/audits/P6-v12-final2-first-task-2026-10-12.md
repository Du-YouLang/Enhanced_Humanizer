# v12-final2 首题实际验收 · 2026-10-12

冻结协议：`b751822058b84512f8755676881e38eb691081ae8fa58456737824803bffc454`。有限batch `20261012T125458Z`，实际首题run `p6-main-execute-BIP-black-2-20261012T125459Z`。此协议此前准备均未运行模型，旧v11完成/部分样本保留。

Black-2实际完整主流程回执为`MAIN_TASK_COMPLETED`，A、B、C、D、E、F六分支全部通过各自独立验收。编码N3候选池按冻结方案共享，这六个分支不是六个独立随机样本；生成COMPLETED和judge分数不作为私有验收替代。

| 实际记录 | 数值/状态 |
|---|---|
| 主流程墙钟 | 1838.856秒（约30.65分钟） |
| 模型活动 | 1834.990秒；同题每角色仍900秒 |
| receipt SHA256 | `c3e0e206e6ef2f6f580772a8d71478e290184b18130fab6a6415c5dab3d66a84` |
| Judge状态 | J0/J1/J3 COMPLETED；J2保留用户报告的地区限制BLOCKED |
| 最近累计账本快照 | 1811次DS、68个订阅实验回合、API费用保守上界USD30.742602；已包含同期敏感性检查进展 |
| 实际账单/订阅美元成本 | unavailable；不把预算上界或Pi估计价格称为现金 |

新DS逐wire输出cap均256000。streaming已结算记录的request timeout字段为600；20条LAV logprobs结算记录未记录该字段，必须标unavailable，不能用0或猜测代填。实际LAV执行源已按新config调用600秒recover；这个源码事实和账本逐请求字段的测量缺口分别记录，后续计量改进需新源码/协议证明。

原生首题控制器已结束，拥有者PID/start-ticks独立复验；完整工具轨迹敏感性run `p6-main-sensitivity-BIP-black-2-20261012T132738Z`仍在运行，后续任务由有限batch继续。私有汇总`.local-workbench/audits/p6-v12-final2-black2-accepted.private.json`绑定原始receipt哈希；旧账本不重置，失败/未知usage不退款，任务不自动重放。

这是一题的结果，不能据此认定增强/融合/Harness收益，或把首题PASS称为完整P6。Pi真实工具、四组对照及PRL后台仍待串行验收。当前功能fba8a12精确三CI和P7新包安装/HTTP/端口/旧包回滚已通过，详见P7-network600-2026-10-12.md。产品Draft30仍待用户GitHub合并，未外部发布。
