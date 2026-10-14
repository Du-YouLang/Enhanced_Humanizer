# 科研验收元数据契约 v2

本契约澄清原公开任务未穷举的字段命名，不改变数值任务、输入、精度、种子、容差或原成绩。旧卡片/原回执保留，历史兼容映射和补充裁决另存。参见 ADR-0037。

## EGL

正常CLI返回以及`SystemExit(0)`/`SystemExit(None)`都会执行可信训练使用计量收尾。其他退出和异常失败；少于九次EG训练共5400次接口调用仍失败。旧运行缺失计量不能用源码或权重验收推算为已测量次数；只能标记unavailable。

`summary.json`的规范字段：`groups`含6组`n/algorithm/mean_test_accuracy_pct/std_test_accuracy_pct`；`eg_minus_gd_mean_pp`包含`200/2000/20000`配对均值，单位pp，标准差用ddof=1。另一等价形式为`paired_differences`，逐组提供`n/per_seed_eg_minus_gd_pp/mean_eg_minus_gd_pp/std_eg_minus_gd_pp`，全部由独立原生曲线重新验证。兼容已有`per_n_algorithm/per_n/aggregates`结构仅限实现中的穷举映射；不覆盖其数字、不接受矛盾表示、不扩大精度容差。CSV最终精度可名为`test_accuracy_pct`或`final_test_accuracy_pct`；若两者并存必须一致。

清单规范字段为`files_sha256/python/dependencies/device/dtype/threads/seeds/command/elapsed_seconds/peak_rss_kib`。旧`file_sha256/code_sha256`、`python_version`、明确的线程/dtype/seed别名可转换。峰值内存仅接受明确KiB、bytes、MiB；不猜测“MB”是十进制还是二进制。历史单位经独立源码行号和精确源码摘要核实后，可通过父控制器的独立审阅记录转换，候选自报单位不能批准这种例外。

任何统计、CSV或清单的兼容映射均不绕过18组配置/曲线、50个signed/zero探针、保存权重独立验收、实际训练使用计量和源码/图表/报告审阅。新验收器的`retained_execution/retained_replay`仅供可信控制器复用精确绑定的旧回执，不能来自产品用户或候选输入。

## PC-ALM

评估副本有意不包含`.git`。可信父控制器独立计算源码文件清单与规范JSON树SHA256，绑定冻结候选、原执行副本和原回执；这不等于伪造候选Git commit。新执行将只读`workbench-source-provenance.json`放在输入目录，实际验收仍由父控制器重新计算，不信任候选拷贝。

候选清单记录`python`、`packages`、`data_sha256`（输入相对路径到SHA256）、`gate_elapsed_seconds`（smoke/anchor/grid，正的实测秒）。兼容现有environment/versions、gates/stages、明确wall_seconds/seconds/elapsed_seconds/elapsed_s/wall_s及data_files/input_files等结构；重复阶段、无效/缺失时间、数据hash冲突仍拒绝。硬件/驱动信息受隔离限制时如实填写unavailable，保留已知测量与控制器环境绑定，不能用当前测量填造历史值。完整环境审计与数值忠实性分别报告。

完整75格、原生config/metrics/summary、公开锚点、官方源码指纹、数据指纹、冻结0.25pp与0.02容差均保持。未完成的两格独立验收仍由原完整程序身份确定；完成的全网格、训练和旧独立验收不得重放。科学C1–C5与执行忠实性、环境计量完整性各自记录，不互相冒充。

## 修复结果和原成绩

本契约不授权自动调用模型或整题重跑。新验收器、兼容转换、缺失验收和Pi手工同步修复分别固定输入/源码/输出摘要；旧FAIL、INDETERMINATE及模型生成的原版本仍可追溯。补充结果不能代替原16题成绩，也不能证明等成本或普适性能优势。
