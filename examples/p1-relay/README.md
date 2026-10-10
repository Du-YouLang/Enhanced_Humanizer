# P1 合成双 Builder 交付样本

这是冻结 weighted_mean 小任务的实际代码快照，模型运行/commit/会话/Token/暂停恢复证据见 [P1 验收](../../docs/audits/P1-2026-10-10.md)。没有科研数据，也不是 P6 benchmark。

- `after-ds/weighted_stats.py`：DeepSeek 第一轮 commit 的函数实现。
- `after-sol/`：新的 Sol 会话实现 WeightedMean 流式累加器、函数委派和新增测试。

在项目根运行 `python -m unittest discover -s examples/p1-relay/after-sol -v`，只重测公开样本，不调用模型。独立外部设计检查还验证 add/merge/异常和实际委派，见 `scripts/p1_acceptance.py`。
