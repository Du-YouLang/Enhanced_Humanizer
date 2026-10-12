# P6 v10 用户时间修订

用户选择公共角色15分钟、科研角色20分钟。新清单v10 SHA256 `c7342d9c22824edf5c47ead44a9ce2790e3d1546504d78fc8f6926c513e0ac82`，新预算授权SHA256 `f257a01daf7a4cd2ac5941cdbeb1d705deab50011befb509620feb284d572675`。16题、A–F共96单元、N3、seed42/repetition1；每任务每角色公共900秒/科研1200秒，整题模型活动7200/10800秒。隐藏判据/原任务/模型身份/单请求和累计费用上限不放宽，见[ADR-0024](../decisions/ADR-0024.md)。

时间控制 `/opt/workbench/benchmark/private/time-controls-20261012-v3/receipt.json` 十项PASS、模型调用0、账本不变，绑定实际部署模块。新文件策略控制v3四项PASS/FAIL符合预期，零模型且账本不变。预算锁内修订保留897DS/39订阅及API上界USD15.1468026；旧账本精确SHA `177f310fd52cc265162e296f4888755d145ca1b58cc57e8ea494ae010f59e605`，在原生state/amendments独立保存。原v9两题5/12 PASS及两题完整轨迹评分、第三题人类暂停样本保留，新版实际进度以后续batch/arm回执为准。

Windows本机138项检查中131 passed/7 skipped；新预算修订、任务/结果时限绑定三项回归通过。原生Linux整套检查与GitHub精确源码CI尚待实际运行，不预写成功。P7精确02243c7旧交付PASS_LOCAL_PREVIEW保留；本次新版功能源需要新包/独立安装验证。完整P6尚未接受，细分事件耗时缺口与科学审阅仍明示；外部发布及产品Draft PR30的GitHub人工合并继续等待用户。

入口字节在实际提交/打包前规范为仓库LF。初次零模型v10冻结be382c1489e8f6a76b30029eaecaa7550128006be3532ef8381555fa7c523eac及其精确源码另存保留；实际执行使用单独的`configs/benchmark-p6-v10-final.json`，c7342d9c22824edf5c47ead44a9ce2790e3d1546504d78fc8f6926c513e0ac82，并验证冻结入口与LF/Git包字节相同。没有改写旧清单或模型结果。

## 精确源码核验与正式启动

功能提交`96d461d4ad1730584f66ddd6999a59f8c9c350fb`已完成原生uid1000全140项PASS；GitHub CI run38215186553 integrity/secrets/linux-budget均SUCCESS，Windows140项（132 pass/8 skip），Node8。首轮新增native测试遗漏新checkout的临时父目录，已修复并独立重跑；失败日志保留，模型调用0。

首次新版batch20261012T065536Z在写Windows索引时被WinError5拒绝，尚未调用launch，主集仍897DS/39订阅/USD15.1468026；零模型证据独立记录。Windows控制器复用已有六次有限原子替换重试，仅重复写同一字节，不重做模型或事务；独立索引集成回归通过。新手动启动batch20261012T070108Z，manifest不变，首题run`p6-main-execute-BIP-black-2-20261012T070113Z`已实际运行，控制器总保护8760秒（公共模型活动7200+8份私有验收180+120），实际角色900秒。没有重试已启动模型失败，旧零模型索引保留。

已收束的首题四个DS角色（DS0和N3）实际为OUTPUT_LIMIT，70.383–192.337秒、没有MAIN_ROLE_DEADLINE；原生结构化终止证明为max-tokens。DS单次输出保护仍4096（原生DS该回合21请求，可见总输出18603，单请求最大4096），没有因加时放宽该保护。其余角色/私有独立验收尚待结果，不预写整题完成或通过率。时间额度、输出截断、请求保护、公开门、私有门和基础设施失败必须分别记录。

## P7 精确新版本机预览

功能源96d461d的P7-A01..A04 PASS_LOCAL_PREVIEW。ZIP `Enhanced_Humanizer-0.1.0-preview.1-96d461d4ad17.zip`，SHA256 `03c50c2ede184a652786390057b95f7f1653f6da0bd814500c004e64541d5c29`，1,725,205 bytes、309成员；可达Git bundle SHA `c845225e4713c1220a56f3f606c47a9f7e875f3651824bb4bcdfbb1cc413f60b`。新目录独立venv/固定哈希依赖/doctor通过，8779实际HTTP九门通过，推理/发布禁用，零事件/运行，Git干净无remote；同目录复用、跨目录8772拒绝、ef085旧包并存恢复再次通过。私有全refs备份916,007 bytes/410 refs，SHA `387abc80099ccbf0bd4abc76fa6983775036fe3d889e978d151405bde9f18050`，真实验证成功，无远程上传。最终回执`p7-time-final-accepted.private.json`；原022/c935/14c/ef085包、环境、回执保留。

后续仅审计文档的提交不改变已验收功能源，安装包不冒充后续Git HEAD。产品Draft PR30仍OPEN/Draft且head1ed608，外部发布未授权；开发PR31保持开放，同名阶段分支继续同步。
