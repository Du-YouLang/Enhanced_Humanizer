# P6 v10 用户时间修订

用户选择公共角色15分钟、科研角色20分钟。新清单v10 SHA256 `c7342d9c22824edf5c47ead44a9ce2790e3d1546504d78fc8f6926c513e0ac82`，新预算授权SHA256 `f257a01daf7a4cd2ac5941cdbeb1d705deab50011befb509620feb284d572675`。16题、A–F共96单元、N3、seed42/repetition1；每任务每角色公共900秒/科研1200秒，整题模型活动7200/10800秒。隐藏判据/原任务/模型身份/单请求和累计费用上限不放宽，见[ADR-0024](../decisions/ADR-0024.md)。

时间控制 `/opt/workbench/benchmark/private/time-controls-20261012-v3/receipt.json` 十项PASS、模型调用0、账本不变，绑定实际部署模块。新文件策略控制v3四项PASS/FAIL符合预期，零模型且账本不变。预算锁内修订保留897DS/39订阅及API上界USD15.1468026；旧账本精确SHA `177f310fd52cc265162e296f4888755d145ca1b58cc57e8ea494ae010f59e605`，在原生state/amendments独立保存。原v9两题5/12 PASS及两题完整轨迹评分、第三题人类暂停样本保留，新版实际进度以后续batch/arm回执为准。

Windows本机138项检查中131 passed/7 skipped；新预算修订、任务/结果时限绑定三项回归通过。原生Linux整套检查与GitHub精确源码CI尚待实际运行，不预写成功。P7精确02243c7旧交付PASS_LOCAL_PREVIEW保留；本次新版功能源需要新包/独立安装验证。完整P6尚未接受，细分事件耗时缺口与科学审阅仍明示；外部发布及产品Draft PR30的GitHub人工合并继续等待用户。

入口字节在实际提交/打包前规范为仓库LF。初次零模型v10冻结be382c1489e8f6a76b30029eaecaa7550128006be3532ef8381555fa7c523eac及其精确源码另存保留；实际执行使用单独的`configs/benchmark-p6-v10-final.json`，c7342d9c22824edf5c47ead44a9ce2790e3d1546504d78fc8f6926c513e0ac82，并验证冻结入口与LF/Git包字节相同。没有改写旧清单或模型结果。
