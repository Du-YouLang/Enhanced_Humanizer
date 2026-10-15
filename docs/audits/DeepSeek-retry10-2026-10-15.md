# DeepSeek 网络重试增量

用户授权与范围见[ADR-0043](../decisions/ADR-0043.md)。这是未来DeepSeek transport的独立版本，不修改旧模型轨迹、判分、角色时限或累计预算。

实际零供应商控制：`formal-full-controls-20261015T020635Z`，receipt bc6b5b46e480433616fad8dc84709eee5353fb297cdb9c46f9fce8d5a8446a7d。官方Pi SDK的四profile、原11软件任务公开工具、3科学任务环境pin和原SDK错误控制均通过。新增真实本地HTTP九次503后成功：14次wire=9次失败+5次正常工具轮，COMPLETED；十次503停止：12次wire=2次正常工具轮+10次失败，INFRA_RETRY_PENDING。均使用fixture私有账本；实际API调用0，累计账本前后相同。控制中只跳过合成退避等待，2/4/8/16/30/45/60/60/60秒序列另有测试核对，不能称实测了285秒等待。

原生部署为新内容寻址目录，旧controller-full-add321ab及全部旧包装器不修改。新全计划v4 b90aabe5仅准备/控制，直接compare被拒绝；实际后缀续行v3 9f30f0a4绑定前三批26格，只选剩86格，并记录独立执行器契约与transport策略。`PASS_UNSTARTED_ONLY_CONTINUATION_CONTROLS`确认旧回执链、原源码与结果、账本前缀、时间/模型/数值标准均保留；实际paid启动须另取回执，准备不等于运行。

首次后缀准备因本地变量遮蔽把Path写进契约而失败，没有启动模型或改账本；修正命名后实际prepare/controls通过，原账本SHA 2a75d15fa684b186667c0e80b6d43304b36d34f42e89fceaedb1601608f3aa72保持。旧Black-5/P1仍为原INFRA_RETRY_PENDING；903.425秒角色时间已耗尽，不因为增加网络次数重新给900秒。

Windows255项（7平台skip）、原生255项（3平台skip）通过；新增控制覆盖九失败成功、第十失败停止、第五次警示、时间与预算提前阻断、权限/协议错误不重试、不能用transport配置替换账本预算、执行器升级不得改任务/模型/时限/预算。最终精确提交、CI和正式运行见私有交付回执与后续交接记录。

累计6850DS/210订阅/USD171.8074293是保守上界，实际现金不可见；39条未知用量预留不填0、不返还。没有对外发布或更改产品PR人工审核流程。
