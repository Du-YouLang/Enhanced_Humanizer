# Pi 缺失题目补测：公开科研接口澄清

本附录在新候选生成前冻结，仅用于补测 cohort。原始任务卡、原16格 Pi 结果及原主集结果保留。数值参考、种子、算法、数据、精度与容差不变。

## SCI-STROKE

`metrics.json.metadata` 使用如下键：`input_sha256`、`n_trials`、`n_channels`、`sfreq`、`unit`、`artifact_reviewed`、`synthetic`、`roi`、`pci_available`、`allow_unreviewed`。`roi` 是配置指定顺序的通道名称列表，不能仅给另一名称的同义字段。布尔值必须是 JSON boolean；`unit` 为 `V`；`input_sha256` 是输入 NPZ 的原始字节 SHA-256。

`natural_frequency_motor_max_profile_db` 是 NF 频率轮廓中有效频率的最大值；即使没有显著增强、`natural_frequency_motor_hz` 为 null，只要轮廓仍有有限值，该最大值也必须保留。完全没有有效频率时最大值为 null。`natural_frequency_motor_at_grid_boundary` 总是 boolean；NF 为 null 时为 false，否则仅 5 或 50 Hz 为 true。所有其他未定义标量与零信号规则继续遵守原卡。

验收采用任务所有者公开资源额度：1 个 CPU 逻辑核、4 GiB、每次调用最多180秒、整套600秒。原执行器60秒/1 GiB的历史结果不改写。完整验收包含14个数值调用、同环境重复和6类输入拒绝；通过数值检查后仍需独立源代码、方法说明和图表核验。

## SCI-PC-ALM

独立验收会复制只读源代码，副本没有 `.git`。可信父进程单独保存源树证明；不得为缺少 `.git` 中止训练或虚构提交。`run_manifest.json` 记录实际 Python、packages、data_sha256 和 smoke/anchor/grid 的正数耗时。不可见硬件信息写 unavailable。完整75格训练、官方受保护代码、冻结0.25pp/0.02容差、独立两格重放及源码/报告核验不变。

## SCI-EGL

正常 CLI `SystemExit(0)` 或 `None` 是成功退出，验收器仍会完成优化器实际使用计量；非零退出仍失败。每个EG训练必须实际调用提交的优化器，9次EG×600更新必须完整。清单中峰值内存使用带明确单位的 `peak_rss_kib`、`peak_rss_bytes` 或 `peak_rss_mib`，不接受猜测单位。summary 使用完整六组统计、ddof=1和三种维度的配对差；等价字段仅在重算一致后接受。18次训练、数值容差、独立权重/优化器检查与源码/报告/图表核验不变。
