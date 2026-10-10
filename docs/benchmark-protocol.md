# 首轮 Benchmark 冻结约定（P6 计划，尚未执行）

保持 16 项：BugsInPy×6、SWE-bench Lite×6、科学任务×4（PC_ALM、论文卒中诊断表/图、Exponential Gradient Learning 表/图、Granger CPU→CuPy GPU）。实例 ID、base SHA、论文/数据/金标准尚未冻结，不编造。

Codex 预先建立项目内按任务固定的 Conda env/container，所有系统共享同一实例环境/权限/硬件；旧依赖冲突允许不同实例使用不同已冻结环境。准备时间与失败单列，不归因模型；执行后工具/测试/调试时间计入模型任务墙钟。

A=DS原生DSH、B=DS×N+硬测试、C=DS-Enhanced、D=Sol原生Codex、E=DS+Sol Humanize、F=DS-Enhanced+Sol Humanize。可用时增加既有 CC/Codex 下 DS 速度参照，不能据不可用工具删除要求。J0/J1/J2/J3 在同一冻结候选池/证据/rubric 上对照；Best-of-N vs +M 单独计额外成本和时间。

任务合同包含 input/base/env_hash/可见测试/隐藏验收/数值容差/seed/预算/角色与权限。科学不变量按具体论文设定，不以图像相似或输出文件代替数值正确。Reviewer 不读取隐藏答案；禁止重复看最终分数调参或挑最佳 seed。

主指标：完成率、每成功任务总真实成本、端到端墙钟、人工干预次数/时间。保留 input/output/cache/reasoning Token、TTFT、首补丁、首通过、生成/排队/工具/测试/Judge/Reviewer/M/Sol/CI 分解、吞吐及 p50/p90。API 现金与订阅使用分别报告。

报告区分 PASS/FAIL/TIMEOUT/INFRA_FAIL/INDETERMINATE；缺论文/凭据/GPU 等准备问题是 NOT_RUN 或基础设施阻碍，不伪报能力失败。先 smoke 两项再跑主集。16 项只支持探索性结论，保留逐任务结果、负结果和区间，不预设增强/融合有效。
