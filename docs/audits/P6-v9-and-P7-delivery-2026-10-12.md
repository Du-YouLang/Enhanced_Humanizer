# v9 公开文件规则与本机交付

v9 协议 `a88638727d97212418484c8a88c58aae79913f17fb429070416f4d2664551c8d` 已在功能提交 `c935bb58297bdd197e25e60c30b8e345eec24b67` 独立冻结。用户已授权本机实验和累计 10000 次 API / USD100 Token 费用；本次没有重新申请、重置或结转额度。所有模型仍使用真实 Humanize/官方 Harness，115 秒角色、120 秒请求、1200 秒活动实验和私有科学计算限时保持不变。

v8 Requests-1963 的六个完成角色通过 112 项公开测试，却追加原测试文件而被拒绝。v9 明确原测试/fixture/依赖配置不可修改，回归测试只能使用新文件，覆盖嵌套路径；见 [ADR-0023](../decisions/ADR-0023.md)。两题的原 A–F/轨迹评分、第三题的停止样本、全部账本和源码快照保留。旧版不能进入新版本完成率。

四项真实零模型控制通过：参考修复保留原文件、新增独立测试文件均通过公开与隐藏验收；追加原测试文件、未修改基线均拒绝。控制前后账本 SHA 都是 `600aa23aa173dfdf0ddbb3934f92f04ea43ca348c57a87646ef3b8f1f2ec4080`。正式控制绑定三个实际部署模块及控制脚本哈希；早先旧部署控制另存不覆盖。原生 uid1000 / Python3.12.3 共132项测试全部通过，治理/86 ID/原基线完整性和Gitleaks通过。精确 c935bb5 的 CI run38209461335 三项SUCCESS，Windows132项（124 passed、8 skipped），Node8通过。

新有限矩阵索引 `.local-workbench/benchmark/main-batches/20261012T054629Z/batch-index.private.json`，依次16题 execute/sensitivity；当前运行状态以实际回执为准。没有基础设施自动重试或候选重抽样。完整 P6 尚未接受；科学通过仍须独立源码/报告/图形审阅，缺少可靠事件测量的细分耗时继续为 unavailable。

## 同一旧候选的完整轨迹敏感性

提交 `28f3abc` 补上只读配对报告，校验原证据池/轨迹池和候选ID一致，输出源码/轨迹哈希，不导出轨迹正文。Windows/原生各三项新回归通过；精确 head 的CI run38209980916 三项SUCCESS，Windows135项（127 passed、8 skipped）、Node8。报告读取真实旧样本，无模型调用、无候选重放。

| 旧任务/池 | LAV原首选→轨迹首选 | LAV排序对一致率 | Sol首选/排序变化 |
|---|---|---:|---|
| BIP-black-2，A/B/C | B→A | 1/3 | 首选A不变，排序一致率1 |
| Requests-1963，A/B/C | A→C | 2/3 | 首选A不变，排序一致率1 |
| BIP-black-2，加入M | M→M | 2/3 | 首选M不变，排序一致率1 |
| Requests-1963，加入M | A→M | 5/6 | 首选M不变，排序一致率1 |

这些池都没有合格候选，eligible selection 均为空；不能由首选变化算出更高选择准确率。Jev仍为地区限制，无替代身份。每种证据只有一次独立评分，观察到的变化也不能区分证据效应和评分随机性。新图表将 NOT_RUN/INDETERMINATE 独立画出，不把缺测变成零分；API费用上界与未知订阅美元费用分开。

## P7 精确 c935bb5 本机预览

P7-A01..A04 **PASS_LOCAL_PREVIEW**。新 ZIP `Enhanced_Humanizer-0.1.0-preview.1-c935bb58297b.zip`，SHA256 `1d86f8db05206c8b6cf0b542dfc1cd38da1160cec44651e3e6e51b75a9ac4884`，1,641,061 bytes，299成员；包内可达Git bundle SHA256 `c077a248cac4c5e8d11dc3db00bc6eb11d24ed9f0c5caec99d6120004158e5c9`。

新目录 `p7-v9-preview-20261012-v1`、独立Python3.13.5 venv和固定哈希依赖安装通过；doctor为LOCAL_UI_READY。8777真实HTTP owner/匿名/Host/跨站/Origin/CSRF检查、推理/发布禁用、零事件/运行、Git干净/无远端均通过。同目录端口复用、跨目录8772拒绝，以及ef085旧包并存恢复再次通过。安装/验收模型调用为0。全refs私有备份872,695 bytes、410 refs，SHA256 `92616e3364d83fc04ed5cb8f0f01854b09b14576bec86fc4fd089e86e8f6c339`，实际验证成功。

逐项最终回执 `.local-workbench/audits/p7-v9-accepted.private.json`；原14c/d051/ef085包、环境、回执保留。后续28f3abc和图表报告修订不冒充该精确安装版本。外部发布仍须确认名称/许可/平台/内容；真实人审生成的Draft PR30仍等待GitHub人工合并，开发PR31保持开放，本地/远端同名阶段分支同步。
